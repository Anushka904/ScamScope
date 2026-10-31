from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app
from app.models.extraction import ExtractedOffer, InputType
from app.models.evidence import EvidenceStatus
from app.models.pdf import PDFMetadata
import app.tools.domain_checks as domain_checks
from app.tools.domain_checks import (
    DomainCheckError,
    UnsafeTargetError,
    _rdap_base_url,
    _resolve_public_host,
    is_reserved_domain,
    normalize_domain,
)
from app.engine import verification as verification_engine
from app.models.verification import VerificationRequest


client = TestClient(app)


def make_offer(**overrides):
    values = {
        "input_type": InputType.TEXT,
        "company_name": "Nexora Technologies Pvt. Ltd.",
        "domains": ["www.nexora-careers.example"],
        "sender_email": "rahul@nexora-careers.example",
        "payment_demand": True,
        "payment_amount": "₹2,499",
        "upi_ids": ["nexora.hr@okaxis"],
        "payment_demand_phrases": ["Pay ₹2,499 within 24 hours."],
        "urgency_phrases": ["within 24 hours"],
    }
    values.update(overrides)
    return ExtractedOffer(**values)


def by_id(report, check_id):
    return next(check for check in report.checks if check.check_id.value == check_id)


def test_nexora_example_domain_is_not_sent_to_live_network():
    report = verification_engine.verify_extracted_offer(make_offer())

    assert len(report.checks) == 6
    assert by_id(report, "domain_age").status == EvidenceStatus.NOT_APPLICABLE
    assert by_id(report, "website_availability").status == EvidenceStatus.NOT_APPLICABLE
    assert by_id(report, "ssl_certificate").status == EvidenceStatus.NOT_APPLICABLE
    assert by_id(report, "sender_domain_match").status == EvidenceStatus.CLEAR
    assert by_id(report, "payment_red_flags").status == EvidenceStatus.FLAG
    assert report.completed_checks == 2
    assert report.coverage_percent == 33.3
    assert len(report.evidence) == 6
    assert len({item.evidence_id for item in report.evidence}) == 6


def test_live_domain_checks_use_explicit_sources_and_do_not_assign_verdict(monkeypatch):
    monkeypatch.setattr(verification_engine, "lookup_domain_registration", lambda domain, timeout: {
        "domain": domain,
        "registration_date": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
        "age_days": 4,
        "rdap_url": "https://rdap.registry.test/domain/example.org",
        "handle": "EXAMPLE-1",
        "ldh_name": "example.org",
    })
    monkeypatch.setattr(verification_engine, "check_website_availability", lambda domain, timeout: {
        "url": f"https://{domain}/", "final_url": f"https://{domain}/", "http_status": 200,
        "reachable": True, "redirects": 0, "content_type": "text/html",
    })
    monkeypatch.setattr(verification_engine, "check_ssl_certificate", lambda domain, timeout: {
        "domain": domain, "valid": True, "not_after": "2027-05-01T00:00:00+00:00",
        "days_remaining": 182, "subject": "example.org", "issuer": "Example CA", "tls_version": "TLSv1.3",
    })

    offer = make_offer(
        domains=["example.org"],
        sender_email="hr@different.example",
        payment_demand=False,
        payment_amount=None,
        upi_ids=[],
        payment_demand_phrases=[],
        urgency_phrases=[],
    )
    report = verification_engine.verify_extracted_offer(offer, Settings(_env_file=None))

    assert by_id(report, "domain_age").status == EvidenceStatus.FLAG
    assert by_id(report, "website_availability").status == EvidenceStatus.CLEAR
    assert by_id(report, "ssl_certificate").status == EvidenceStatus.CLEAR
    assert by_id(report, "sender_domain_match").status == EvidenceStatus.FLAG
    assert by_id(report, "payment_red_flags").status == EvidenceStatus.CLEAR
    assert report.overall_status.value == "completed"
    assert not hasattr(report, "risk_score")


def test_external_provider_failures_become_unavailable_not_fake_flags(monkeypatch):
    def unavailable(*args, **kwargs):
        raise DomainCheckError("temporary provider outage")

    monkeypatch.setattr(verification_engine, "lookup_domain_registration", unavailable)
    monkeypatch.setattr(verification_engine, "check_website_availability", unavailable)
    monkeypatch.setattr(verification_engine, "check_ssl_certificate", unavailable)

    offer = make_offer(domains=["example.org"], payment_demand=False, payment_demand_phrases=[], urgency_phrases=[], upi_ids=[])
    report = verification_engine.verify_extracted_offer(offer, Settings(_env_file=None))

    assert by_id(report, "domain_age").status == EvidenceStatus.UNAVAILABLE
    assert by_id(report, "website_availability").status == EvidenceStatus.UNAVAILABLE
    assert by_id(report, "ssl_certificate").status == EvidenceStatus.UNAVAILABLE
    assert report.overall_status.value == "partial"


def test_pdf_metadata_chronology_inconsistency_is_a_weak_flag():
    metadata = PDFMetadata(
        title="Offer", author="HR", creator="Document editor", producer="PDF engine",
        creation_date_raw="D:20261031120000Z", modification_date_raw="D:20261030120000Z",
        page_count=2, is_encrypted=False,
    )
    offer = make_offer(input_type=InputType.PDF, pdf_metadata=metadata)
    report = verification_engine.verify_extracted_offer(offer)
    result = by_id(report, "pdf_metadata")

    assert result.status == EvidenceStatus.FLAG
    assert result.severity.value == "weak"
    assert "not proof of tampering" in result.limitation


def test_pdf_metadata_without_anomaly_is_clear():
    metadata = PDFMetadata(
        title="Offer", author="Recruitment", page_count=2, is_encrypted=False,
    )
    report = verification_engine.verify_extracted_offer(make_offer(input_type=InputType.PDF, pdf_metadata=metadata))
    assert by_id(report, "pdf_metadata").status == EvidenceStatus.CLEAR


def test_missing_pdf_metadata_is_unavailable_for_pdf_and_not_applicable_for_text():
    pdf_report = verification_engine.verify_extracted_offer(make_offer(input_type=InputType.PDF, pdf_metadata=None))
    text_report = verification_engine.verify_extracted_offer(make_offer(input_type=InputType.TEXT, pdf_metadata=None))
    assert by_id(pdf_report, "pdf_metadata").status == EvidenceStatus.UNAVAILABLE
    assert by_id(text_report, "pdf_metadata").status == EvidenceStatus.NOT_APPLICABLE


def test_payment_upi_without_explicit_demand_is_only_a_weak_flag():
    report = verification_engine.verify_extracted_offer(make_offer(
        payment_demand=False, payment_amount=None, payment_demand_phrases=[],
        urgency_phrases=[], upi_ids=["person@okaxis"],
    ))
    result = by_id(report, "payment_red_flags")
    assert result.status == EvidenceStatus.FLAG
    assert result.severity.value == "weak"
    assert "on its own" in result.limitation


def test_no_claimed_domain_does_not_trigger_network_calls(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError("External check should not run without a domain")
    monkeypatch.setattr(verification_engine, "lookup_domain_registration", should_not_run)
    monkeypatch.setattr(verification_engine, "check_website_availability", should_not_run)
    monkeypatch.setattr(verification_engine, "check_ssl_certificate", should_not_run)

    report = verification_engine.verify_extracted_offer(make_offer(domains=[], claimed_company_website=None))
    assert by_id(report, "domain_age").status == EvidenceStatus.UNAVAILABLE
    assert by_id(report, "website_availability").status == EvidenceStatus.UNAVAILABLE
    assert by_id(report, "ssl_certificate").status == EvidenceStatus.UNAVAILABLE


def test_rdap_bootstrap_uses_longest_matching_suffix():
    payload = {"services": [
        [["com"], ["https://rdap.verisign.com/com/v1/"]],
        [["co.uk"], ["https://rdap.nominet.uk/uk/rdap/"]],
    ]}
    assert _rdap_base_url("careers.example.co.uk", payload) == "https://rdap.nominet.uk/uk/rdap/"


def test_normalize_domain_and_reserved_domain_handling():
    assert normalize_domain("https://WWW.Example.com/job") == "www.example.com"
    assert normalize_domain("not a url") is None
    assert is_reserved_domain("example.test") is True
    assert is_reserved_domain("example.com") is False


def test_private_ip_targets_are_rejected(monkeypatch):
    monkeypatch.setattr("app.tools.domain_checks.socket.getaddrinfo", lambda *args, **kwargs: [
        (2, 1, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(UnsafeTargetError):
        _resolve_public_host("internal.example.com", 443)


def test_verify_api_returns_six_checks_and_evidence(monkeypatch):
    # Reserved .example input makes this endpoint test fully deterministic and offline.
    payload = make_offer().model_dump(mode="json")
    response = client.post("/api/verify", json={"extracted": payload})
    assert response.status_code == 200
    result = response.json()
    assert len(result["checks"]) == 6
    assert len(result["evidence"]) == 6
    assert result["checks"][-1]["check_id"] == "payment_red_flags"
    assert result["checks"][-1]["status"] == "flag"


def test_verify_api_rejects_extra_request_fields():
    with pytest.raises(ValidationError):
        VerificationRequest(extracted=make_offer(), unknown="no")


def test_website_url_rejects_credentials_and_nonstandard_ports():
    from app.tools.domain_checks import _validated_url

    with pytest.raises(UnsafeTargetError):
        _validated_url("https://user:pass@example.com")
    with pytest.raises(UnsafeTargetError):
        _validated_url("https://example.com:8443")


def test_website_redirect_to_loopback_is_blocked_before_following(monkeypatch):
    from app.tools import domain_checks

    class FakeResponse:
        status_code = 302
        headers = {"location": "http://127.0.0.1/admin"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            assert method == "HEAD"
            return FakeResponse()

    monkeypatch.setattr(domain_checks.httpx, "Client", FakeClient)
    monkeypatch.setattr(
        domain_checks,
        "_resolve_public_host",
        lambda host, port: ["93.184.216.34"] if host == "public.example" else _resolve_public_host(host, port),
    )

    with pytest.raises(UnsafeTargetError):
        domain_checks.check_website_availability("https://public.example", 2)


def test_rdap_lookup_retries_registered_parent_after_subdomain_400(monkeypatch):
    """A www host must resolve to the registered parent for RDAP."""
    calls = []
    bootstrap = {"services": [[["org"], ["https://rdap.publicinterestregistry.org/rdap/"]]]}
    monkeypatch.setattr(domain_checks, "_get_rdap_bootstrap", lambda client: bootstrap)

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                request = domain_checks.httpx.Request("GET", "https://registry.invalid")
                response = domain_checks.httpx.Response(self.status_code, request=request)
                raise domain_checks.httpx.HTTPStatusError("registry error", request=request, response=response)

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is True
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url):
            calls.append(url)
            if url.endswith("/domain/www.wikipedia.org"):
                return FakeResponse(400)
            if url.endswith("/domain/wikipedia.org"):
                return FakeResponse(200, {
                    "handle": "WIKIPEDIA-ORG",
                    "ldhName": "WIKIPEDIA.ORG",
                    "events": [{"eventAction": "registration", "eventDate": "2001-01-13T00:00:00Z"}],
                })
            raise AssertionError(f"Unexpected RDAP URL: {url}")

    monkeypatch.setattr(domain_checks.httpx, "Client", FakeClient)
    result = domain_checks.lookup_domain_registration("www.wikipedia.org", 5)

    assert calls == [
        "https://rdap.publicinterestregistry.org/rdap/domain/www.wikipedia.org",
        "https://rdap.publicinterestregistry.org/rdap/domain/wikipedia.org",
    ]
    assert result["domain"] == "wikipedia.org"
    assert result["input_domain"] == "www.wikipedia.org"
    assert result["ldh_name"] == "WIKIPEDIA.ORG"
    assert result["age_days"] > 9000


def test_rdap_does_not_fallback_after_rate_limit(monkeypatch):
    bootstrap = {"services": [[["org"], ["https://rdap.publicinterestregistry.org/rdap/"]]]}
    monkeypatch.setattr(domain_checks, "_get_rdap_bootstrap", lambda client: bootstrap)

    class FakeResponse:
        status_code = 429
        def raise_for_status(self):
            request = domain_checks.httpx.Request("GET", "https://registry.invalid")
            response = domain_checks.httpx.Response(429, request=request)
            raise domain_checks.httpx.HTTPStatusError("rate limited", request=request, response=response)

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url): return FakeResponse()

    monkeypatch.setattr(domain_checks.httpx, "Client", FakeClient)
    with pytest.raises(domain_checks.httpx.HTTPStatusError):
        domain_checks.lookup_domain_registration("www.wikipedia.org", 5)
