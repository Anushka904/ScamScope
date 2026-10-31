from pydantic import BaseModel, ConfigDict, Field


class PDFMetadata(BaseModel):
    """Embedded PDF metadata extracted from the uploaded document.

    Metadata is descriptive only and is not proof of document authenticity.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=500)
    creator: str | None = Field(default=None, max_length=500)
    producer: str | None = Field(default=None, max_length=500)
    creation_date_raw: str | None = Field(default=None, max_length=500)
    modification_date_raw: str | None = Field(default=None, max_length=500)
    page_count: int = Field(ge=0)
    is_encrypted: bool = False
