from pydantic import BaseModel, ConfigDict, Field

from app.models.extraction import InputType


class PDFMetadata(BaseModel):
    """
    Extracted PDF document metadata.

    All dates are retained as raw PDF metadata strings.
    They are not treated as proof of document authenticity.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = None

    author: str | None = None

    subject: str | None = None

    creator: str | None = None

    producer: str | None = None

    creation_date_raw: str | None = None

    modification_date_raw: str | None = None

    page_count: int = Field(ge=0)

    is_encrypted: bool = False


class VisualAsset(BaseModel):
    """
    Internal visual payload.

    Used to carry screenshots and rendered PDF pages
    to the later Gemini extraction module.

    Binary data is deliberately excluded from serialization.
    """

    model_config = ConfigDict(extra="forbid")

    page_number: int | None = Field(
        default=None,
        ge=1
    )

    mime_type: str

    width: int = Field(gt=0)

    height: int = Field(gt=0)

    data: bytes = Field(
        repr=False,
        exclude=True
    )


class PreparedInput(BaseModel):
    """
    Unified internal representation of every input type.

    This is passed from Phase 2 to Phase 3.
    """

    model_config = ConfigDict(extra="forbid")

    input_type: InputType

    source_filename: str | None = None

    mime_type: str

    # Extracted/normalized text.
    text_content: str = Field(
        default="",
        repr=False
    )

    # Original screenshot or rendered PDF pages.
    visual_assets: list[VisualAsset] = Field(
        default_factory=list
    )

    # Available only for PDF inputs.
    pdf_metadata: PDFMetadata | None = None

    page_count: int | None = None

    # Processing warnings, not fraud findings.
    warnings: list[str] = Field(
        default_factory=list
    )

    def to_summary(self):
        """
        Create a safe, serializable summary.

        Never returns the actual binary image data.
        """

        return IngestionSummary(
            input_type=self.input_type,
            source_filename=self.source_filename,
            mime_type=self.mime_type,
            text_characters=len(self.text_content),
            text_preview=self.text_content[:1200],
            page_count=self.page_count,
            pdf_metadata=self.pdf_metadata,
            visual_assets=[
                VisualAssetInfo(
                    page_number=asset.page_number,
                    mime_type=asset.mime_type,
                    width=asset.width,
                    height=asset.height
                )
                for asset in self.visual_assets
            ],
            warnings=self.warnings
        )


class VisualAssetInfo(BaseModel):
    """
    Public description of a visual asset.

    Does not expose binary content.
    """

    model_config = ConfigDict(extra="forbid")

    page_number: int | None = None

    mime_type: str

    width: int

    height: int


class IngestionSummary(BaseModel):
    """
    API response for Phase 2 ingestion.

    Only a summary is returned to the client.
    """

    model_config = ConfigDict(extra="forbid")

    input_type: InputType

    source_filename: str | None = None

    mime_type: str

    text_characters: int

    text_preview: str

    page_count: int | None = None

    pdf_metadata: PDFMetadata | None = None

    visual_assets: list[VisualAssetInfo] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )