from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"


class SourceExcerpt(BaseModel):
    """
    A verbatim excerpt from the submitted offer.

    Used to connect extracted claims to their
    original source.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    field_name: str = Field(
        min_length=1,
        max_length=100
    )

    quote: str = Field(
        min_length=1,
        max_length=1200
    )

    page_number: int | None = Field(
        default=None,
        ge=1
    )


class ExtractedOffer(BaseModel):
    """
    Structured information extracted from a
    suspicious internship/job offer.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    # Input information
    input_type: InputType

    # Company information
    company_name: str | None = Field(
        default=None,
        max_length=200
    )

    claimed_company_website: str | None = Field(
        default=None,
        max_length=500
    )

    # Job information
    role_title: str | None = Field(
        default=None,
        max_length=200
    )

    salary_claim: str | None = Field(
        default=None,
        max_length=300
    )

    claimed_issue_date: str | None = None

    claimed_joining_date: str | None = None

    # Recruiter information
    recruiter_name: str | None = Field(
        default=None,
        max_length=200
    )

    sender_email: str | None = Field(
        default=None,
        max_length=320
    )

    sender_phone: str | None = Field(
        default=None,
        max_length=50
    )

    # Technical identifiers
    domains: list[str] = Field(
        default_factory=list,
        max_length=50
    )

    urls: list[str] = Field(
        default_factory=list,
        max_length=50
    )

    phone_numbers: list[str] = Field(
        default_factory=list,
        max_length=50
    )

    upi_ids: list[str] = Field(
        default_factory=list,
        max_length=30
    )

    # Financial information
    payment_demand: bool = False

    payment_amount: str | None = Field(
        default=None,
        max_length=100
    )

    payment_demand_phrases: list[str] = Field(
        default_factory=list,
        max_length=30
    )

    # Language indicators
    urgency_phrases: list[str] = Field(
        default_factory=list,
        max_length=30
    )

    # Original evidence from uploaded material
    evidence_excerpts: list[SourceExcerpt] = Field(
        default_factory=list,
        max_length=50
    )

    # Extraction limitations
    extraction_warnings: list[str] = Field(
        default_factory=list,
        max_length=30
    )