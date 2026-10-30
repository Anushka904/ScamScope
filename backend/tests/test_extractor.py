import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agents import extractor
from app.agents.extractor import (
    ExtractionInputError,
    ExtractionNotConfiguredError,
    ExtractionOutputError,
    ExtractionProviderError,
    build_extraction_messages,
    build_extraction_tasks,
    classify_provider_error,
    create_gemini_client,
    deterministic_text_fallback,
    extract_offer,
    invoke_gemini,
    merge_extractions,
    normalize_extraction_payload,
    parse_json_response,
    should_use_fallback,
    split_text_into_chunks,
    validate_source_excerpts,
)
from app.config import Settings
from app.main import app
from app.models.extraction import (
    ExtractedOffer,
    ExtractionStatus,
    InputType,
    SourceExcerpt,
)
from app.models.input import PreparedInput, VisualAsset

client = TestClient(app)


# =====================================================
# HELPERS
# =====================================================


def make_offer(
    input_type=InputType.TEXT,
    company="ABC Technologies",
    role="Software Developer Intern",
):
    return ExtractedOffer(
        input_type=input_type,
        company_name=company,
        role_title=role,
        sender_email="hr@example.com",
        payment_demand=True,
        payment_amount="₹2,000",
        payment_demand_phrases=["Pay ₹2,000 as a registration fee."],
        evidence_excerpts=[
            SourceExcerpt(
                field_name="payment_demand",
                quote="Pay ₹2,000 as a registration fee.",
            )
        ],
    )


def make_text_input(
    text=(
        "ABC Technologies is hiring a Software Developer Intern. "
        "Pay ₹2,000 as a registration fee."
    ),
    warnings=None,
):
    return PreparedInput(
        input_type=InputType.TEXT,
        mime_type="text/plain",
        text_content=text,
        visual_assets=[],
        warnings=warnings or [],
    )


def make_image_input():
    asset = VisualAsset(
        page_number=None,
        mime_type="image/jpeg",
        width=640,
        height=480,
        data=b"fake-image-content",
    )
    return PreparedInput(
        input_type=InputType.IMAGE,
        mime_type="image/jpeg",
        text_content="",
        visual_assets=[asset],
    )


def make_settings(key="test-api-key"):
    return Settings(
        _env_file=None,
        gemini_api_key=key,
        gemini_model="gemini-3.8-flash",
        gemini_timeout_seconds=120,
    )


class FakeStructuredModel:
    """Offline fake that supports a sequence of outputs/exceptions."""

    def __init__(self, result):
        self.result = result
        self.messages = []

    def invoke(self, messages):
        self.messages.append(messages)
        if isinstance(self.result, list):
            item = self.result.pop(0)
        else:
            item = self.result
        if isinstance(item, Exception):
            raise item
        return item


# =====================================================
# PROMPT / TASK BUILDING
# =====================================================


def test_build_text_extraction_messages_marks_source_untrusted():
    prepared = make_text_input()
    messages = build_extraction_messages(prepared)
    assert "untrusted" in messages["system_instruction"].lower()
    assert "ABC Technologies" in messages["prompt"]
    assert messages["visual_assets"] == []


def test_build_multimodal_messages_keeps_visual_asset():
    prepared = make_image_input()
    messages = build_extraction_messages(prepared)
    assert len(messages["visual_assets"]) == 1
    assert messages["visual_assets"][0].data == b"fake-image-content"
    assert "uploaded screenshot" in messages["prompt"]


def test_build_tasks_creates_text_and_visual_tasks():
    asset = make_image_input().visual_assets[0]
    prepared = PreparedInput(
        input_type=InputType.PDF,
        mime_type="application/pdf",
        text_content="A" * 100,
        visual_assets=[asset],
        page_count=1,
    )
    tasks = build_extraction_tasks(prepared)
    assert [task["kind"] for task in tasks] == ["text", "visual"]
    assert tasks[1]["visual_assets"][0].page_number is None


def test_empty_prepared_input_is_rejected_by_message_builder():
    prepared = PreparedInput(input_type=InputType.TEXT, mime_type="text/plain")
    with pytest.raises(ExtractionInputError):
        build_extraction_messages(prepared)


# =====================================================
# CHUNKING
# =====================================================


def test_split_text_into_chunks_respects_max_size_and_overlap():
    text = ("A" * 4000) + "\n" + ("B" * 4000) + "\n" + ("C" * 12000)
    chunks = split_text_into_chunks(text, max_chars=8000, overlap=300)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 8000 for chunk in chunks)
    assert chunks[0][-100:] in chunks[1]


def test_chunking_preserves_all_non_whitespace_text():
    text = "alpha " * 8000
    chunks = split_text_into_chunks(text, max_chars=10000, overlap=200)
    assert len(chunks) > 1
    # Overlap may duplicate text but must not drop the source tail.
    assert chunks[-1].endswith("alpha")


def test_empty_text_returns_no_chunks():
    assert split_text_into_chunks("") == []
    assert split_text_into_chunks("  \n ") == []


def test_invalid_chunk_configuration_is_rejected():
    with pytest.raises(ValueError):
        split_text_into_chunks("text", max_chars=100, overlap=100)


def test_chunk_limit_is_enforced():
    with pytest.raises(ExtractionInputError) as exc:
        split_text_into_chunks("A" * (18_000 * 13))
    assert exc.value.status_code == 413


# =====================================================
# JSON / NORMALIZATION
# =====================================================


def test_parse_json_response_accepts_plain_json_and_fence():
    payload = {"company_name": "ABC"}
    assert parse_json_response(json.dumps(payload)) == payload
    assert parse_json_response("```json\n" + json.dumps(payload) + "\n```") == payload


def test_parse_json_response_rejects_invalid_json():
    with pytest.raises(ExtractionOutputError):
        parse_json_response("not json")


def test_normalization_uses_backend_input_type_and_nulls_empty_strings():
    prepared = make_text_input()
    payload = make_offer().model_dump(mode="json")
    payload["company_name"] = ""
    payload["payment_amount"] = ""
    payload["input_type"] = "pdf"
    payload["extraction_status"] = "fallback"
    result = normalize_extraction_payload(payload, prepared)
    assert result.company_name is None
    assert result.payment_amount is None
    assert result.input_type == InputType.TEXT
    assert result.extraction_status == ExtractionStatus.COMPLETE


def test_normalization_rejects_invalid_payment_boolean():
    payload = make_offer().model_dump(mode="json")
    payload["payment_demand"] = "maybe"
    with pytest.raises(ExtractionOutputError):
        normalize_extraction_payload(payload, make_text_input())


def test_normalization_discards_malformed_evidence_with_warning():
    payload = make_offer().model_dump(mode="json")
    payload["evidence_excerpts"] = [
        {"field_name": "", "quote": "", "page_number": ""}
    ]
    result = normalize_extraction_payload(payload, make_text_input())
    assert result.evidence_excerpts == []
    assert any("malformed evidence" in warning for warning in result.extraction_warnings)


def test_normalization_ignores_unknown_fields_with_warning():
    payload = make_offer().model_dump(mode="json")
    payload["risk_score"] = 99
    result = normalize_extraction_payload(payload, make_text_input())
    assert not hasattr(result, "risk_score")
    assert any("unsupported fields" in warning for warning in result.extraction_warnings)


# =====================================================
# MERGING
# =====================================================


def test_merge_fills_fields_from_later_chunks_and_deduplicates_lists():
    first = ExtractedOffer(
        input_type=InputType.TEXT,
        company_name="ABC Technologies",
        sender_email="hr@example.com",
        domains=["example.com"],
        payment_demand=False,
    )
    second = ExtractedOffer(
        input_type=InputType.TEXT,
        role_title="Software Developer Intern",
        sender_email="hr@example.com",
        domains=["example.com", "careers.example.com"],
        upi_ids=["abc@okaxis"],
        payment_demand=True,
        payment_amount="₹2,000",
    )
    merged = merge_extractions([first, second], InputType.TEXT)
    assert merged.company_name == "ABC Technologies"
    assert merged.role_title == "Software Developer Intern"
    assert merged.sender_email == "hr@example.com"
    assert merged.domains == ["example.com", "careers.example.com"]
    assert merged.upi_ids == ["abc@okaxis"]
    assert merged.payment_demand is True
    assert merged.payment_amount == "₹2,000"


def test_merge_reports_scalar_conflicts():
    merged = merge_extractions(
        [make_offer(company="ABC Technologies"), make_offer(company="XYZ Technologies")],
        InputType.TEXT,
    )
    assert merged.company_name == "ABC Technologies"
    assert any("Conflicting values" in warning for warning in merged.extraction_warnings)


def test_merge_drops_payment_amount_when_no_payment_is_demanded():
    offer = ExtractedOffer(
        input_type=InputType.TEXT,
        payment_demand=False,
        payment_amount="₹25,000",
    )
    merged = merge_extractions([offer], InputType.TEXT)
    assert merged.payment_amount is None


# =====================================================
# SOURCE QUOTE VALIDATION
# =====================================================


def test_text_quotes_are_checked_verbatim_after_whitespace_normalization():
    prepared = make_text_input("Pay   ₹2,000\n as a registration fee.")
    offer = make_offer()
    valid, warnings = validate_source_excerpts(offer, prepared)
    assert len(valid) == 1
    assert warnings == []


def test_unverifiable_text_quotes_are_removed():
    prepared = make_text_input("ABC Technologies is hiring interns.")
    valid, warnings = validate_source_excerpts(make_offer(), prepared)
    assert valid == []
    assert any("could not be matched" in warning for warning in warnings)


def test_visual_quotes_are_retained_but_marked_unverified():
    prepared = make_image_input()
    valid, warnings = validate_source_excerpts(make_offer(InputType.IMAGE), prepared)
    assert len(valid) == 1
    assert any("visual content" in warning for warning in warnings)


# =====================================================
# DETERMINISTIC FALLBACK
# =====================================================


def test_fallback_extracts_company_role_salary_payment_email_and_upi():
    text = (
        "ABC Technologies is hiring a Software Developer Intern. "
        "Monthly stipend: ₹25,000. Pay ₹2,000 as a registration fee "
        "to confirm selection. Contact: hr@example.com. UPI: abc@okaxis. "
        "Complete payment within 24 hours."
    )
    result = deterministic_text_fallback(
        make_text_input(text),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.company_name == "ABC Technologies"
    assert result.role_title == "Software Developer Intern"
    assert "₹25,000" in result.salary_claim
    assert result.payment_demand is True
    assert result.payment_amount == "₹2,000"
    assert result.sender_email == "hr@example.com"
    assert "abc@okaxis" in result.upi_ids
    assert result.urgency_phrases
    assert result.extraction_status == ExtractionStatus.FALLBACK


def test_fallback_does_not_extract_email_prefix_as_upi_id():
    text = (
        "Example Robotics is hiring a Software Developer Intern. "
        "Contact: hr@example.com. UPI ID: example@okaxis."
    )
    result = deterministic_text_fallback(
        make_text_input(text),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.sender_email == "hr@example.com"
    assert result.upi_ids == ["example@okaxis"]
    assert "hr@example" not in result.upi_ids


def test_fallback_does_not_extract_email_as_upi_when_no_upi_is_present():
    result = deterministic_text_fallback(
        make_text_input("Contact HR at hr@example.com for details."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.upi_ids == []


def test_fallback_keeps_a_valid_upi_even_when_an_email_is_also_present():
    result = deterministic_text_fallback(
        make_text_input("Email hr@example.com; UPI ID: recruiter@ybl."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.upi_ids == ["recruiter@ybl"]


def test_model_normalization_removes_upi_candidate_that_overlaps_email():
    payload = make_offer().model_dump(mode="json")
    payload["upi_ids"] = ["hr@example", "example@okaxis"]
    prepared = make_text_input(
        "Contact: hr@example.com. UPI ID: example@okaxis."
    )
    result = normalize_extraction_payload(payload, prepared)
    assert result.upi_ids == ["example@okaxis"]


def test_fallback_does_not_flag_salary_as_payment_demand():
    result = deterministic_text_fallback(
        make_text_input("The monthly stipend is ₹25,000 for this internship."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.payment_demand is False
    assert result.payment_amount is None


def test_fallback_domain_pattern_ignores_sentence_punctuation():
    result = deterministic_text_fallback(
        make_text_input("Visit https://careers.example.com. Contact hr@example.com."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert "careers.example.com" in result.domains
    assert result.claimed_company_website is None


def test_fallback_extracts_indian_phone_with_separator():
    result = deterministic_text_fallback(
        make_text_input("Contact: +91 98765 43210"),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.phone_numbers == ["+91 98765 43210"]


def test_fallback_does_not_mistake_employer_salary_payment_for_fee():
    result = deterministic_text_fallback(
        make_text_input("We will pay ₹25,000 per month as your internship stipend."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.payment_demand is False
    assert result.payment_amount is None


def test_fallback_respects_explicit_no_fee_statement():
    result = deterministic_text_fallback(
        make_text_input("No registration fee is required. Never pay anyone for selection."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.payment_demand is False
    assert result.payment_demand_phrases == []


def test_fallback_does_not_invent_company_or_role():
    result = deterministic_text_fallback(
        make_text_input("Pay ₹2,000 as a registration fee."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.company_name is None
    assert result.role_title is None
    assert result.payment_demand is True
    assert result.extraction_warnings


def test_fallback_only_uses_explicit_website_not_email_domain():
    result = deterministic_text_fallback(
        make_text_input("Contact hr@example.com for details."),
        ExtractionProviderError(503, "temporarily unavailable"),
    )
    assert result.claimed_company_website is None
    assert result.domains == []


# =====================================================
# PROVIDER CLASSIFICATION / FALLBACK POLICY
# =====================================================


def test_rate_limit_classification_allows_fallback():
    error = classify_provider_error(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert error.status_code == 429
    assert should_use_fallback(error)


def test_timeout_classification_allows_fallback():
    error = classify_provider_error(RuntimeError("504 DEADLINE_EXCEEDED"))
    assert error.status_code == 504
    assert should_use_fallback(error)


def test_service_unavailable_classification_allows_fallback():
    error = classify_provider_error(RuntimeError("503 SERVICE_UNAVAILABLE"))
    assert error.status_code == 503
    assert should_use_fallback(error)


def test_invalid_argument_does_not_trigger_fallback():
    error = classify_provider_error(RuntimeError("400 INVALID_ARGUMENT"))
    assert error.status_code == 502
    assert not should_use_fallback(error)


def test_authentication_error_does_not_trigger_fallback():
    error = classify_provider_error(RuntimeError("401 UNAUTHENTICATED"))
    assert error.status_code == 401
    assert not should_use_fallback(error)


# =====================================================
# SDK WIRING (MOCKED - NO NETWORK / NO API QUOTA)
# =====================================================


def test_create_gemini_client_uses_bounded_timeout_and_retry(monkeypatch):
    captured = {}

    class FakeTypes:
        @staticmethod
        def HttpRetryOptions(**kwargs):
            captured["retry"] = kwargs
            return kwargs

        @staticmethod
        def HttpOptions(**kwargs):
            captured["http"] = kwargs
            return kwargs

    class FakeGenAI:
        types = FakeTypes

        @staticmethod
        def Client(**kwargs):
            captured["client"] = kwargs
            return "fake-client"

    monkeypatch.setattr(extractor, "_load_google_genai", lambda: (FakeGenAI, FakeTypes))
    result = create_gemini_client(make_settings())
    assert result == "fake-client"
    assert captured["http"]["timeout"] == 120_000
    assert captured["retry"]["attempts"] == 2
    assert captured["retry"]["http_status_codes"] == [408, 429, 500, 502, 503, 504]


def test_invoke_gemini_uses_json_mode_low_thinking_and_no_schema(monkeypatch):
    captured = {}

    class FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"data": data, "mime_type": mime_type}

    class FakeTypes:
        Part = FakePart

        @staticmethod
        def ThinkingConfig(**kwargs):
            return kwargs

        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    class FakeGenAI:
        types = FakeTypes

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text=json.dumps(make_offer().model_dump(mode="json")))

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(extractor, "_load_google_genai", lambda: (FakeGenAI, FakeTypes))
    prepared = make_text_input()
    task = build_extraction_tasks(prepared)[0]
    result = invoke_gemini(fake_client, prepared, make_settings(), task)

    assert result["company_name"] == "ABC Technologies"
    assert captured["model"] == "gemini-3.8-flash"
    assert captured["config"]["response_mime_type"] == "application/json"
    assert captured["config"]["thinking_config"] == {"thinking_level": "low"}
    assert "response_schema" not in captured["config"]
    assert "temperature" not in captured["config"]


def test_invoke_gemini_attaches_image_parts(monkeypatch):
    captured = {}

    class FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"image_data": data, "mime_type": mime_type}

    class FakeTypes:
        Part = FakePart

        @staticmethod
        def ThinkingConfig(**kwargs):
            return kwargs

        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    class FakeGenAI:
        types = FakeTypes

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            captured["contents"] = contents
            return SimpleNamespace(text=json.dumps(make_offer(InputType.IMAGE).model_dump(mode="json")))

    monkeypatch.setattr(extractor, "_load_google_genai", lambda: (FakeGenAI, FakeTypes))
    prepared = make_image_input()
    result = invoke_gemini(
        SimpleNamespace(models=FakeModels()),
        prepared,
        make_settings(),
        build_extraction_tasks(prepared)[0],
    )
    assert result["company_name"] == "ABC Technologies"
    assert captured["contents"][1]["image_data"] == b"fake-image-content"


# =====================================================
# MAIN EXTRACTION PIPELINE
# =====================================================


def test_extraction_returns_valid_offer_and_complete_status():
    result = extract_offer(
        make_text_input(),
        structured_model=FakeStructuredModel(make_offer(InputType.PDF)),
    )
    assert isinstance(result, ExtractedOffer)
    assert result.input_type == InputType.TEXT
    assert result.company_name == "ABC Technologies"
    assert result.payment_demand is True
    assert result.extraction_status == ExtractionStatus.COMPLETE


def test_extraction_preserves_phase2_processing_warnings():
    result = extract_offer(
        make_text_input(warnings=["Phase 2 warning."]),
        structured_model=FakeStructuredModel(make_offer()),
    )
    assert "Phase 2 warning." in result.extraction_warnings


def test_extraction_rejects_invalid_model_output_without_fallback():
    with pytest.raises(ExtractionOutputError):
        extract_offer(
            make_text_input(),
            structured_model=FakeStructuredModel({"payment_demand": "maybe"}),
        )


def test_extraction_requires_gemini_credentials():
    settings = Settings(_env_file=None, gemini_api_key=None, gemini_model=None)
    with pytest.raises(ExtractionNotConfiguredError):
        extract_offer(make_text_input(), settings=settings)


def test_provider_failure_returns_explicit_deterministic_fallback(monkeypatch):
    class FakeClient:
        def close(self):
            pass

    def fail(*args, **kwargs):
        raise ExtractionProviderError(503, "Gemini temporarily unavailable.")

    monkeypatch.setattr(extractor, "create_gemini_client", lambda settings: FakeClient())
    monkeypatch.setattr(extractor, "invoke_gemini", fail)
    text = (
        "ABC Technologies is hiring a Software Developer Intern. "
        "Monthly stipend: ₹25,000. Pay ₹2,000 as a registration fee. "
        "Contact: hr@example.com. UPI: abc@okaxis."
    )
    result = extract_offer(make_text_input(text), settings=make_settings())
    assert result.extraction_status == ExtractionStatus.FALLBACK
    assert result.company_name == "ABC Technologies"
    assert result.role_title == "Software Developer Intern"
    assert result.payment_demand is True
    assert any("Deterministic text-pattern fallback" in w for w in result.extraction_warnings)


def test_image_only_provider_failure_is_returned_as_provider_error(monkeypatch):
    class FakeClient:
        def close(self):
            pass

    def fail(*args, **kwargs):
        raise ExtractionProviderError(503, "Gemini unavailable.")

    monkeypatch.setattr(extractor, "create_gemini_client", lambda settings: FakeClient())
    monkeypatch.setattr(extractor, "invoke_gemini", fail)
    with pytest.raises(ExtractionProviderError):
        extract_offer(make_image_input(), settings=make_settings())


def test_partial_chunk_failure_preserves_success_and_adds_fallback(monkeypatch):
    class FakeClient:
        def close(self):
            pass

    calls = {"count": 0}

    def fake_invoke(client, prepared, settings, task):
        calls["count"] += 1
        if calls["count"] == 1:
            return make_offer().model_dump(mode="json")
        raise ExtractionProviderError(503, "temporary provider failure")

    monkeypatch.setattr(extractor, "create_gemini_client", lambda settings: FakeClient())
    monkeypatch.setattr(extractor, "invoke_gemini", fake_invoke)

    long_text = ("ABC Technologies is hiring a Software Developer Intern. " + "Details. " * 2500)
    result = extract_offer(make_text_input(long_text), settings=make_settings())
    assert result.extraction_status == ExtractionStatus.PARTIAL
    assert result.company_name == "ABC Technologies"
    assert any("Partial extraction" in warning for warning in result.extraction_warnings)


def test_invalid_output_after_one_success_is_partial_not_fallback(monkeypatch):
    class FakeClient:
        def close(self):
            pass

    calls = {"count": 0}

    def fake_invoke(client, prepared, settings, task):
        calls["count"] += 1
        if calls["count"] == 1:
            return make_offer().model_dump(mode="json")
        raise ExtractionOutputError("bad JSON")

    monkeypatch.setattr(extractor, "create_gemini_client", lambda settings: FakeClient())
    monkeypatch.setattr(extractor, "invoke_gemini", fake_invoke)

    long_text = "ABC Technologies is hiring a Software Developer Intern. " + "Details. " * 2500
    result = extract_offer(make_text_input(long_text), settings=make_settings())
    assert result.extraction_status == ExtractionStatus.PARTIAL
    assert not any("Deterministic text-pattern fallback" in w for w in result.extraction_warnings)


def test_visual_input_does_not_trigger_text_fallback_when_provider_fails(monkeypatch):
    class FakeClient:
        def close(self):
            pass

    monkeypatch.setattr(extractor, "create_gemini_client", lambda settings: FakeClient())
    monkeypatch.setattr(
        extractor,
        "invoke_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(ExtractionProviderError(503, "offline")),
    )
    with pytest.raises(ExtractionProviderError):
        extract_offer(make_image_input(), settings=make_settings())


# =====================================================
# FASTAPI CONTRACT
# =====================================================


def test_extract_endpoint_success(monkeypatch):
    monkeypatch.setattr(
        "app.api.extract.extract_offer",
        lambda prepared: make_offer(prepared.input_type),
    )
    response = client.post(
        "/api/extract",
        data={"text": "ABC Technologies is hiring interns. Pay ₹2,000 as a registration fee."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_type"] == "text"
    assert body["company_name"] == "ABC Technologies"
    assert body["payment_demand"] is True
    assert body["extraction_status"] == "complete"
    assert "risk_score" not in body


def test_extract_endpoint_rejects_both_inputs():
    response = client.post(
        "/api/extract",
        data={"text": "Test offer"},
        files={"file": ("offer.png", b"not-an-image", "image/png")},
    )
    assert response.status_code == 400


def test_extract_endpoint_rejects_empty_input():
    response = client.post("/api/extract")
    assert response.status_code == 422


def test_extract_endpoint_maps_missing_credentials(monkeypatch):
    def fail(prepared):
        raise ExtractionNotConfiguredError()

    monkeypatch.setattr("app.api.extract.extract_offer", fail)
    response = client.post("/api/extract", data={"text": "Test recruitment offer"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_extract_endpoint_maps_provider_504(monkeypatch):
    def fail(prepared):
        raise ExtractionProviderError(504, "deadline")

    monkeypatch.setattr("app.api.extract.extract_offer", fail)
    response = client.post("/api/extract", data={"text": "Test recruitment offer"})
    assert response.status_code == 504
