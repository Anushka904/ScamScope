import pymupdf

from app.config import get_settings
from app.models.extraction import InputType

from app.models.input import (
    PreparedInput,
    PDFMetadata,
    VisualAsset
)

from app.tools.input_errors import InputProcessingError

from app.tools.text_processor import normalize_text


# PDF preprocessing limits.

MAX_PDF_RENDER_SIDE = 1800

MAX_PDF_RENDER_SCALE = 1.5

# Pages below this extracted text length
# are considered candidates for visual rendering.

MIN_TEXT_CHARS_FOR_VISUAL = 80

MAX_EXTRACTED_TEXT_CHARS = 100_000


def clean_metadata_value(value):
    """
    Convert PDF metadata into a safe string.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value[:500]


def render_pdf_page(page, page_number: int) -> VisualAsset:
    """
    Render an individual PDF page into PNG bytes.

    Page rendering is performed in memory.
    """

    rect = page.rect

    longest_side = max(
        rect.width,
        rect.height
    )

    if longest_side <= 0:

        raise ValueError(
            "Invalid PDF page dimensions."
        )

    scale = min(
        MAX_PDF_RENDER_SCALE,
        MAX_PDF_RENDER_SIDE / longest_side
    )

    matrix = pymupdf.Matrix(
        scale,
        scale
    )

    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    image_bytes = pixmap.tobytes("png")

    return VisualAsset(
        page_number=page_number,
        mime_type="image/png",
        width=pixmap.width,
        height=pixmap.height,
        data=image_bytes
    )


def process_pdf(
    data: bytes,
    filename: str | None = None
) -> PreparedInput:
    """
    Process an uploaded PDF.

    Performs:
    1. PDF signature validation.
    2. Document opening.
    3. Encryption detection.
    4. Page count validation.
    5. Metadata extraction.
    6. Page text extraction.
    7. Rendering of pages with little/no selectable text.
    8. Text normalization and truncation.
    """

    if not data:

        raise InputProcessingError(
            422,
            "Uploaded PDF is empty."
        )

    # Validate the PDF header.
    # PDF headers generally occur near the beginning
    # of the file, not necessarily byte zero.

    if b"%PDF-" not in data[:1024]:

        raise InputProcessingError(
            422,
            "The uploaded file does not contain "
            "a valid PDF signature."
        )

    settings = get_settings()

    warnings_list = []

    visual_assets = []

    text_parts = []

    try:

        # Open PDF directly from memory.
        with pymupdf.open(
            stream=data,
            filetype="pdf"
        ) as document:

            # Password-protected PDFs are not processed
            # without an explicitly supplied password.

            if document.needs_pass:

                raise InputProcessingError(
                    422,
                    "Password-protected PDFs are not supported."
                )

            page_count = document.page_count

            if page_count < 1:

                raise InputProcessingError(
                    422,
                    "PDF contains no pages."
                )

            if page_count > settings.max_pdf_pages:

                raise InputProcessingError(
                    413,
                    f"PDF contains {page_count} pages. "
                    f"Maximum allowed: "
                    f"{settings.max_pdf_pages}."
                )

            # ---------------------------------
            # Extract document metadata
            # ---------------------------------

            raw_metadata = document.metadata or {}

            metadata = PDFMetadata(

                title=clean_metadata_value(
                    raw_metadata.get("title")
                ),

                author=clean_metadata_value(
                    raw_metadata.get("author")
                ),

                subject=clean_metadata_value(
                    raw_metadata.get("subject")
                ),

                creator=clean_metadata_value(
                    raw_metadata.get("creator")
                ),

                producer=clean_metadata_value(
                    raw_metadata.get("producer")
                ),

                creation_date_raw=clean_metadata_value(
                    raw_metadata.get("creationDate")
                ),

                modification_date_raw=clean_metadata_value(
                    raw_metadata.get("modDate")
                ),

                page_count=page_count,

                is_encrypted=bool(
                    document.is_encrypted
                )
            )

            # ---------------------------------
            # Process pages individually
            # ---------------------------------

            for index in range(page_count):

                page_number = index + 1

                page = document.load_page(index)

                # Extract selectable text.
                raw_text = page.get_text(
                    "text",
                    sort=True
                ) or ""

                page_text = normalize_text(
                    raw_text,
                    allow_empty=True,
                    max_characters=None
                )

                # Retain page boundaries.
                if page_text:

                    text_parts.append(
                        f"[PAGE {page_number}]\n{page_text}"
                    )

                # ---------------------------------
                # Detect pages needing visual input
                # ---------------------------------

                if len(page_text) < MIN_TEXT_CHARS_FOR_VISUAL:

                    try:

                        visual_asset = render_pdf_page(
                            page,
                            page_number
                        )

                        visual_assets.append(
                            visual_asset
                        )

                    except Exception as exc:

                        warnings_list.append(
                            f"Page {page_number} could not "
                            f"be rendered: {type(exc).__name__}."
                        )

            # ---------------------------------
            # Combine all extracted text
            # ---------------------------------

            combined_text = normalize_text(
                "\n\n".join(text_parts),
                allow_empty=True,
                max_characters=None
            )

            # Keep a bounded text representation.
            if len(combined_text) > MAX_EXTRACTED_TEXT_CHARS:

                combined_text = (
                    combined_text[:MAX_EXTRACTED_TEXT_CHARS]
                )

                warnings_list.append(
                    "Extracted PDF text exceeded the "
                    "100,000-character processing limit "
                    "and was truncated."
                )

    except InputProcessingError:
        raise

    except Exception as exc:

        raise InputProcessingError(
            422,
            "PDF is invalid, corrupted, or could not "
            "be processed."
        ) from exc

    if not combined_text.strip():

        warnings_list.append(
            "No selectable PDF text was extracted. "
            "Rendered pages are available for visual analysis."
        )

    if visual_assets:

        warnings_list.append(
            f"{len(visual_assets)} page(s) were rendered "
            "as images because they contained little "
            "or no selectable text."
        )

    return PreparedInput(
        input_type=InputType.PDF,

        source_filename=filename,

        mime_type="application/pdf",

        text_content=combined_text,

        visual_assets=visual_assets,

        pdf_metadata=metadata,

        page_count=page_count,

        warnings=warnings_list
    )