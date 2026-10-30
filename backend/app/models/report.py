from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator
)

from app.models.extraction import (
    ExtractedOffer,
    InputType
)

from app.models.evidence import Evidence


class RiskBand(str, Enum):
    """
    Observed warning indicator bands.

    These are not fraud probabilities.
    """

    FEW_WARNING_INDICATORS = (
        "few_warning_indicators"
    )

    SOME_WARNING_INDICATORS = (
        "some_warning_indicators"
    )

    HIGH_RISK_INDICATORS = (
        "high_risk_indicators"
    )

    VERY_HIGH_RISK_INDICATORS = (
        "very_high_risk_indicators"
    )


class VerificationStatus(str, Enum):

    UNVERIFIED = "unverified"

    PARTIALLY_VERIFIED = "partially_verified"

    CHECKS_COMPLETED = "checks_completed"


class InvestigationMode(str, Enum):

    LIVE = "live"

    DEMO = "demo"


class InvestigationStatus(str, Enum):

    COMPLETED = "completed"

    PARTIAL = "partial"

    FAILED = "failed"


class RiskAssessment(BaseModel):
    """
    Deterministic risk assessment produced
    by the Python rules engine.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    # Risk score is an indicator score,
    # not a probability of fraud.
    risk_score: int = Field(
        ge=0,
        le=100
    )

    risk_band: RiskBand

    verification_status: VerificationStatus

    # Investigation coverage
    completed_checks: int = Field(
        ge=0
    )

    total_checks: int = Field(
        ge=0
    )

    coverage_percent: float = Field(
        ge=0,
        le=100
    )

    # Evidence supporting the risk assessment
    evidence_ids: list[str] = Field(
        default_factory=list
    )

    # Important caveats
    caveats: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_coverage(self):

        if self.completed_checks > self.total_checks:
            raise ValueError(
                "Completed checks cannot exceed total checks."
            )

        expected_coverage = (
            100 * self.completed_checks / self.total_checks
            if self.total_checks > 0
            else 0.0
        )

        if abs(
            self.coverage_percent - expected_coverage
        ) > 1.0:
            raise ValueError(
                "Coverage percentage does not match "
                "completed_checks / total_checks."
            )

        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError(
                "Duplicate evidence IDs are not allowed."
            )

        return self


class InvestigationReport(BaseModel):
    """
    Final structured report returned by ScamScope.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    # Identification
    investigation_id: str = Field(
        default_factory=lambda: (
            f"CASE-{uuid4().hex[:10].upper()}"
        )
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Input details
    input_type: InputType

    mode: InvestigationMode

    status: InvestigationStatus

    # Extracted information
    extracted: ExtractedOffer

    # Risk assessment
    risk: RiskAssessment

    # Individual evidence records
    evidence: list[Evidence] = Field(
        default_factory=list
    )

    # LLM-generated explanation
    explanation: str = Field(
        default="",
        max_length=6000
    )

    # Additional limitations/notes
    notes: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_report_integrity(self):

        # Ensure extraction and report refer
        # to the same input type.
        if self.input_type != self.extracted.input_type:
            raise ValueError(
                "Report input_type must match extracted input_type."
            )

        # Ensure evidence IDs are unique.
        evidence_ids = [
            item.evidence_id
            for item in self.evidence
        ]

        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "Duplicate evidence IDs found in report."
            )

        # Every evidence reference in the risk
        # assessment must actually exist.
        known_ids = set(evidence_ids)

        unknown_ids = (
            set(self.risk.evidence_ids) - known_ids
        )

        if unknown_ids:
            raise ValueError(
                f"Unknown evidence references: {unknown_ids}"
            )

        return self