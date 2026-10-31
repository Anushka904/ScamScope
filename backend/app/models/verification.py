from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.models.evidence import Evidence, EvidenceSeverity, EvidenceStatus
from app.models.extraction import ExtractedOffer


class VerificationCheckId(str, Enum):
    DOMAIN_AGE = "domain_age"
    WEBSITE_AVAILABILITY = "website_availability"
    SSL_CERTIFICATE = "ssl_certificate"
    SENDER_DOMAIN_MATCH = "sender_domain_match"
    PDF_METADATA = "pdf_metadata"
    PAYMENT_RED_FLAGS = "payment_red_flags"


class VerificationOverallStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"


class VerificationCheck(BaseModel):
    """One check result with explicit outcome and provenance."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    check_id: VerificationCheckId
    label: str = Field(min_length=2, max_length=100)
    status: EvidenceStatus
    severity: EvidenceSeverity = EvidenceSeverity.INFORMATIONAL
    finding: str = Field(min_length=3, max_length=700)
    observed_value: str | None = Field(default=None, max_length=1200)
    source_type: str = Field(min_length=2, max_length=50)
    source_url: str | None = Field(default=None, max_length=2048)
    checked_at: datetime
    limitation: str | None = Field(default=None, max_length=1200)
    details: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    """Independent check results; deliberately contains no fraud verdict/score."""

    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(
        default_factory=lambda: f"VER-{uuid4().hex[:10].upper()}"
    )
    checked_at: datetime
    overall_status: VerificationOverallStatus
    completed_checks: int = Field(ge=0)
    total_checks: int = Field(ge=1)
    coverage_percent: float = Field(ge=0, le=100)
    checks: list[VerificationCheck]
    evidence: list[Evidence] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class VerificationRequest(BaseModel):
    """Request body for POST /api/verify."""

    model_config = ConfigDict(extra="forbid")

    extracted: ExtractedOffer
