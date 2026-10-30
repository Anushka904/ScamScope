from app.config import Settings, get_settings

from app.models.extraction import InputType
from app.models.input import PreparedInput

from app.tools.input_errors import InputProcessingError

from app.tools.text_processor import normalize_text
from app.tools.image_processor import process_image
from app.tools.pdf_forensics import process_pdf


def sanitize_filename(filename: str | None) -> str:
    """
    Remove path components and non-printable characters.

    Uploaded filenames are never used as filesystem paths.
    """

    if not filename:
        return "uploaded_file"

    # Normalize Windows and Unix separators.
    filename = filename.replace("\\", "/")

    # Keep only the final filename.
    filename = filename.split("/")[-1]

    filename = "".join(
        char
        for char in filename
        if char.isprintable()
        and char not in "/\\"
    )

    filename = filename.strip(" .")

    return filename[:255] or "uploaded_file"


def prepare_text_input(
    text: str,
    settings: Settings | None = None
) -> PreparedInput:
    """
    Prepare directly pasted recruitment text.
    """

    settings = settings or get_settings()

    if len(text.encode("utf-8")) > (
        settings.max_upload_size_mb * 1024 * 1024
    ):

        raise InputProcessingError(
            413,
            "Pasted text exceeds the maximum "
            "allowed input size."
        )

    normalized_text = normalize_text(text)

    return PreparedInput(
        input_type=InputType.TEXT,

        source_filename=None,

        mime_type="text/plain",

        text_content=normalized_text,

        visual_assets=[],

        pdf_metadata=None,

        page_count=None,

        warnings=[]
    )


def prepare_file_input(
    data: bytes,
    filename: str | None = None,
    settings: Settings | None = None
) -> PreparedInput:
    """
    Identify, validate and preprocess an uploaded file.

    File content is inspected instead of trusting
    client-provided MIME headers.
    """

    settings = settings or get_settings()

    if not data:

        raise InputProcessingError(
            422,
            "Uploaded file is empty."
        )

    max_bytes = (
        settings.max_upload_size_mb * 1024 * 1024
    )

    if len(data) > max_bytes:

        raise InputProcessingError(
            413,
            f"File exceeds the maximum allowed size "
            f"of {settings.max_upload_size_mb} MB."
        )

    safe_name = sanitize_filename(filename)

    extension = safe_name.lower().rsplit(
        ".",
        1
    )[-1] if "." in safe_name else ""

    is_pdf_signature = (
        b"%PDF-" in data[:1024]
    )

    # If the filename says PDF, require an actual PDF header.
    if extension == "pdf" and not is_pdf_signature:

        raise InputProcessingError(
            422,
            "The file has a .pdf extension but "
            "does not contain a valid PDF header."
        )

    # PDF processing.
    if is_pdf_signature:

        prepared = process_pdf(
            data=data,
            filename=safe_name
        )

        if extension and extension != "pdf":

            prepared.warnings.append(
                "Filename extension does not match "
                "the detected PDF format."
            )

        return prepared

    # Otherwise attempt image processing.
    # Pillow independently detects the actual format.
    return process_image(
        data=data,
        filename=safe_name
    )


def prepare_input(
    *,
    text: str | None = None,
    file_data: bytes | None = None,
    filename: str | None = None,
    settings: Settings | None = None
) -> PreparedInput:
    """
    Unified public entry point.

    Exactly one of text or file_data must be supplied.
    """

    if (text is None) == (file_data is None):

        raise InputProcessingError(
            400,
            "Provide exactly one input: either text "
            "or an uploaded file."
        )

    if text is not None:

        return prepare_text_input(
            text=text,
            settings=settings
        )

    return prepare_file_input(
        data=file_data,
        filename=filename,
        settings=settings
    )