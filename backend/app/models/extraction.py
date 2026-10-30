
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InputType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"


class ExtractionStatus(str, Enum):
    """How the extraction result was produced."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FALLBACK = "deterministic_fallback"


class SourceExcerpt(BaseModel):
    """
    A verbatim excerpt from the submitted offer.

    Excerpts help connect extracted information
    to the original submitted material.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    field_name: str = Field(
        min_length=1,
        max_length=100,
        description=(
            "Name of the extracted field supported "
            "by this excerpt."
        )
    )

    quote: str = Field(
        min_length=1,
        max_length=1200,
        description=(
            "A short, verbatim quotation from the "
            "submitted offer. Never invent a quotation."
        )
    )

    page_number: int | None = Field(
        default=None,
        ge=1,
        description=(
            "PDF page number containing the quote, "
            "if applicable. Null for screenshots "
            "and pasted text."
        )
    )


class ExtractedOffer(BaseModel):
    """
    Structured information extracted from a
    suspicious internship or job offer.

    This model contains extracted claims only.
    It does not contain a fraud verdict or risk score.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    # -------------------------------------
    # Input information
    # -------------------------------------

    input_type: InputType = Field(
        description=(
            "Actual input type: text, image or pdf."
        )
    )

    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.COMPLETE,
        description=(
            "complete: all extraction tasks succeeded; partial: some tasks "
            "failed; deterministic_fallback: Gemini was unavailable and "
            "high-confidence text patterns were used instead."
        )
    )

    # -------------------------------------
    # Company information
    # -------------------------------------

    company_name: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Company or organization name explicitly "
            "mentioned in the offer."
        )
    )

    claimed_company_website: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Website address explicitly claimed to "
            "belong to the company."
        )
    )

    # -------------------------------------
    # Job information
    # -------------------------------------

    role_title: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Internship or job position title."
        )
    )

    salary_claim: str | None = Field(
        default=None,
        max_length=300,
        description=(
            "Salary, stipend or compensation exactly "
            "as claimed in the offer."
        )
    )

    claimed_issue_date: str | None = Field(
        default=None,
        description=(
            "Issue date claimed inside the offer, "
            "preserved as raw text."
        )
    )

    claimed_joining_date: str | None = Field(
        default=None,
        description=(
            "Joining date claimed inside the offer, "
            "preserved as raw text."
        )
    )

    # -------------------------------------
    # Recruiter information
    # -------------------------------------

    recruiter_name: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Recruiter or HR representative name."
        )
    )

    sender_email: str | None = Field(
        default=None,
        max_length=320,
        description=(
            "Recruitment email address exactly as "
            "displayed in the submitted material."
        )
    )

    sender_phone: str | None = Field(
        default=None,
        max_length=50,
        description=(
            "Primary recruiter contact number, "
            "if explicitly identified."
        )
    )

    # -------------------------------------
    # Technical identifiers
    # -------------------------------------

    domains: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Domains and hostnames explicitly appearing "
            "as websites or links in the offer. "
            "Do not derive domains from company names "
            "or invent likely websites."
        )
    )

    urls: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Complete URLs explicitly visible in the "
            "submitted material."
        )
    )

    phone_numbers: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "All visible telephone numbers, preserving "
            "their original formatting."
        )
    )

    upi_ids: list[str] = Field(
        default_factory=list,
        max_length=30,
        description=(
            "UPI payment identifiers explicitly "
            "present in the offer."
        )
    )

    # -------------------------------------
    # Financial information
    # -------------------------------------

    payment_demand: bool = Field(
        default=False,
        description=(
            "True only when the offer explicitly "
            "requests or requires a payment, deposit, "
            "registration fee, selection fee or similar "
            "payment."
        )
    )

    payment_amount: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Requested payment amount exactly as written. "
            "Null if no amount is specified."
        )
    )

    payment_demand_phrases: list[str] = Field(
        default_factory=list,
        max_length=30,
        description=(
            "Exact short excerpts containing the "
            "payment request or payment instructions."
        )
    )

    # -------------------------------------
    # Language indicators
    # -------------------------------------

    urgency_phrases: list[str] = Field(
        default_factory=list,
        max_length=30,
        description=(
            "Exact phrases indicating urgency, "
            "pressure, limited-time selection or "
            "threatened loss of an opportunity."
        )
    )

    # -------------------------------------
    # Original evidence
    # -------------------------------------

    evidence_excerpts: list[SourceExcerpt] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Short verbatim excerpts supporting "
            "important extracted claims."
        )
    )

    # -------------------------------------
    # Extraction limitations
    # -------------------------------------

    extraction_warnings: list[str] = Field(
        default_factory=list,
        max_length=30,
        description=(
            "Unreadable portions, ambiguity, incomplete "
            "information or other extraction limitations."
        )
    )
