from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStatus(str, Enum):
    """
    Describes what happened during a check.

    FLAG:
        A risk-relevant indicator was observed.

    CLEAR:
        Check completed without observing
        the particular warning indicator.

    UNAVAILABLE:
        The check could not be performed because
        required information/provider was unavailable.

    ERROR:
        The check was attempted but failed.

    NOT_APPLICABLE:
        The check does not apply to this input.
    """

    FLAG = "flag"
    CLEAR = "clear"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class EvidenceSeverity(str, Enum):

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    INFORMATIONAL = "informational"


class EvidenceSourceType(str, Enum):

    USER_CONTENT = "user_content"
    PDF_METADATA = "pdf_metadata"

    RDAP = "rdap"
    DNS = "dns"
    TLS = "tls"

    URL_REPUTATION = "url_reputation"
    COMPANY_WEBSITE = "company_website"

    INTERNAL_CASE_DATABASE = "internal_case_database"
    MANUAL_REVIEW = "manual_review"


class Evidence(BaseModel):
    """
    Standardized result returned by every
    ScamScope investigation tool.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    # Unique evidence identifier
    evidence_id: str = Field(
        pattern=r"^EV-\d{3,}$"
    )

    # Tool that generated this evidence
    check_name: str = Field(
        min_length=2,
        max_length=100
    )

    # Check result
    status: EvidenceStatus

    severity: EvidenceSeverity = (
        EvidenceSeverity.INFORMATIONAL
    )

    # Human-readable finding
    finding: str = Field(
        min_length=3,
        max_length=500
    )

    # Actual observed information
    observed_value: str | None = Field(
        default=None,
        max_length=1000
    )

    # Source and provenance
    source_type: EvidenceSourceType

    source_name: str | None = Field(
        default=None,
        max_length=200
    )

    source_url: str | None = Field(
        default=None,
        max_length=2048
    )

    source_excerpt: str | None = Field(
        default=None,
        max_length=1500
    )

    page_number: int | None = Field(
        default=None,
        ge=1
    )

    # Time when evidence was obtained
    checked_at: datetime | None = None

    # Limitations and additional details
    limitation: str | None = Field(
        default=None,
        max_length=1000
    )

    details: dict[str, Any] = Field(
        default_factory=dict
    )