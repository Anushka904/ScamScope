import pytest

from pydantic import ValidationError

from app.models.extraction import (
    InputType,
    ExtractedOffer,
    SourceExcerpt
)

from app.models.evidence import (
    Evidence,
    EvidenceStatus,
    EvidenceSeverity,
    EvidenceSourceType
)

from app.models.report import (
    RiskBand,
    VerificationStatus,
    InvestigationMode,
    InvestigationStatus,
    RiskAssessment,
    InvestigationReport
)


def create_sample_extracted_offer():

    return ExtractedOffer(
        input_type=InputType.TEXT,
        company_name="ABC Technologies",
        role_title="Software Developer Intern",
        sender_email="hr@example.com",
        payment_demand=True,
        payment_amount="₹2,000",
        payment_demand_phrases=[
            "Pay ₹2,000 as a registration fee."
        ],
        evidence_excerpts=[
            SourceExcerpt(
                field_name="payment_demand",
                quote="Pay ₹2,000 as a registration fee."
            )
        ]
    )


def create_sample_evidence():

    return Evidence(
        evidence_id="EV-001",
        check_name="registration_fee_check",
        status=EvidenceStatus.FLAG,
        severity=EvidenceSeverity.STRONG,
        finding="An upfront registration fee is demanded.",
        source_type=EvidenceSourceType.USER_CONTENT,
        source_excerpt="Pay ₹2,000 as a registration fee."
    )


def create_sample_risk():

    return RiskAssessment(
        risk_score=30,
        risk_band=RiskBand.SOME_WARNING_INDICATORS,
        verification_status=VerificationStatus.PARTIALLY_VERIFIED,
        completed_checks=1,
        total_checks=3,
        coverage_percent=33.3,
        evidence_ids=["EV-001"],
        caveats=["Additional verification is required."]
    )


def create_sample_report():

    return InvestigationReport(
        input_type=InputType.TEXT,
        mode=InvestigationMode.LIVE,
        status=InvestigationStatus.PARTIAL,
        extracted=create_sample_extracted_offer(),
        risk=create_sample_risk(),
        evidence=[create_sample_evidence()],
        explanation="An upfront payment demand was identified."
    )


# -------------------------------------------------
# EXTRACTION MODEL TESTS
# -------------------------------------------------


def test_extraction_model():

    offer = create_sample_extracted_offer()

    assert offer.company_name == "ABC Technologies"

    assert offer.payment_demand is True

    assert len(offer.evidence_excerpts) == 1


def test_extraction_defaults():

    offer1 = ExtractedOffer(
        input_type=InputType.TEXT
    )

    offer2 = ExtractedOffer(
        input_type=InputType.TEXT
    )

    offer1.domains.append("example.com")

    assert offer2.domains == []


def test_invalid_input_type():

    with pytest.raises(ValidationError):

        ExtractedOffer(
            input_type="video"
        )


# -------------------------------------------------
# EVIDENCE MODEL TESTS
# -------------------------------------------------


def test_evidence_model():

    evidence = create_sample_evidence()

    assert evidence.evidence_id == "EV-001"

    assert evidence.status == EvidenceStatus.FLAG


def test_invalid_evidence_id():

    with pytest.raises(ValidationError):

        Evidence(
            evidence_id="INVALID",
            check_name="test",
            status=EvidenceStatus.FLAG,
            finding="Test finding",
            source_type=EvidenceSourceType.RDAP
        )


def test_unavailable_evidence_is_allowed():

    evidence = Evidence(
        evidence_id="EV-002",
        check_name="rdap_check",
        status=EvidenceStatus.UNAVAILABLE,
        severity=EvidenceSeverity.INFORMATIONAL,
        finding="RDAP lookup could not be completed.",
        source_type=EvidenceSourceType.RDAP,
        limitation="Registry service unavailable."
    )

    assert evidence.status == EvidenceStatus.UNAVAILABLE


# -------------------------------------------------
# RISK MODEL TESTS
# -------------------------------------------------


def test_risk_assessment():

    risk = create_sample_risk()

    assert risk.risk_score == 30

    assert risk.total_checks == 3

    assert risk.evidence_ids == ["EV-001"]


def test_invalid_risk_score():

    with pytest.raises(ValidationError):

        RiskAssessment(
            risk_score=120,
            risk_band=RiskBand.VERY_HIGH_RISK_INDICATORS,
            verification_status=VerificationStatus.UNVERIFIED,
            completed_checks=0,
            total_checks=0,
            coverage_percent=0
        )


def test_invalid_coverage():

    with pytest.raises(ValidationError):

        RiskAssessment(
            risk_score=30,
            risk_band=RiskBand.SOME_WARNING_INDICATORS,
            verification_status=VerificationStatus.PARTIALLY_VERIFIED,
            completed_checks=1,
            total_checks=3,
            coverage_percent=80
        )


# -------------------------------------------------
# REPORT MODEL TESTS
# -------------------------------------------------


def test_complete_report():

    report = create_sample_report()

    assert report.investigation_id.startswith("CASE-")

    assert report.risk.risk_score == 30

    assert len(report.evidence) == 1


def test_report_rejects_missing_evidence_reference():

    risk = create_sample_risk()

    risk.evidence_ids = ["EV-999"]

    with pytest.raises(ValidationError):

        InvestigationReport(
            input_type=InputType.TEXT,
            mode=InvestigationMode.LIVE,
            status=InvestigationStatus.PARTIAL,
            extracted=create_sample_extracted_offer(),
            risk=risk,
            evidence=[create_sample_evidence()]
        )


def test_report_rejects_input_type_mismatch():

    with pytest.raises(ValidationError):

        InvestigationReport(
            input_type=InputType.PDF,
            mode=InvestigationMode.LIVE,
            status=InvestigationStatus.PARTIAL,
            extracted=create_sample_extracted_offer(),
            risk=create_sample_risk(),
            evidence=[create_sample_evidence()]
        )


def test_report_json_serialization():

    report = create_sample_report()

    result = report.model_dump(mode="json")

    assert result["input_type"] == "text"

    assert result["risk"]["risk_score"] == 30

    assert result["evidence"][0]["evidence_id"] == "EV-001"