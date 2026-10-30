
from io import BytesIO
from pathlib import PurePosixPath
import warnings

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError
)

from app.models.extraction import InputType
from app.models.input import (
    PreparedInput,
    VisualAsset
)
from app.tools.input_errors import InputProcessingError


# -------------------------------------------------
# APPLICATION SAFETY LIMITS
# -------------------------------------------------

MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_SIDE = 2200

SUPPORTED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp"
}

EXPECTED_EXTENSIONS = {
    "JPEG": {".jpg", ".jpeg"},
    "PNG": {".png"},
    "WEBP": {".webp"}
}

ALL_SUPPORTED_EXTENSIONS = {
    extension
    for extensions in EXPECTED_EXTENSIONS.values()
    for extension in extensions
}


def get_file_extension(filename: str | None) -> str:
    """
    Safely obtain the file extension.
    """

    if not filename:
        return ""

    normalized = filename.replace("\\", "/")

    return PurePosixPath(normalized).suffix.lower()


def process_image(
    data: bytes,
    filename: str | None = None
) -> PreparedInput:
    """
    Validate and normalize an uploaded image.

    Supported formats:
        JPEG, PNG, WEBP

    Processing:
        1. Inspect actual image format.
        2. Verify image structure.
        3. Enforce pixel limits.
        4. Correct EXIF orientation.
        5. Flatten transparency against white.
        6. Resize oversized images.
        7. Convert to normalized JPEG.

    The resulting image is stored in memory
    as a VisualAsset for Gemini processing.
    """

    if not data:
        raise InputProcessingError(
            422,
            "Uploaded image is empty."
        )

    detected_format = None

    try:

        # Treat Pillow decompression warnings
        # as exceptions for safer processing.

        with warnings.catch_warnings():

            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning
            )

            # ---------------------------------
            # FIRST OPENING: Inspect and verify
            # ---------------------------------

            with Image.open(BytesIO(data)) as probe:

                detected_format = probe.format

                width, height = probe.size

                if detected_format not in SUPPORTED_FORMATS:
                    raise InputProcessingError(
                        415,
                        "Only JPEG, PNG and WEBP images "
                        "are supported."
                    )

                if width <= 0 or height <= 0:
                    raise InputProcessingError(
                        422,
                        "Image dimensions are invalid."
                    )

                if width * height > MAX_IMAGE_PIXELS:
                    raise InputProcessingError(
                        413,
                        "Image exceeds the maximum allowed "
                        "pixel count."
                    )

                probe.verify()

            # ---------------------------------
            # SECOND OPENING: Decode image
            # ---------------------------------

            with Image.open(BytesIO(data)) as source:

                source.load()

                # Correct EXIF orientation.
                image = ImageOps.exif_transpose(source)

                # ---------------------------------
                # Handle transparent images
                # ---------------------------------

                if (
                    "A" in image.getbands()
                    or "transparency" in image.info
                ):

                    rgba = image.convert("RGBA")

                    background = Image.new(
                        "RGBA",
                        rgba.size,
                        (255, 255, 255, 255)
                    )

                    background.alpha_composite(rgba)

                    normalized = background.convert("RGB")

                else:

                    normalized = image.convert("RGB")

                # ---------------------------------
                # Resize without enlarging images
                # ---------------------------------

                normalized.thumbnail(
                    (MAX_IMAGE_SIDE, MAX_IMAGE_SIDE),
                    Image.Resampling.LANCZOS
                )

                # ---------------------------------
                # Convert to normalized JPEG
                # ---------------------------------

                output = BytesIO()

                normalized.save(
                    output,
                    format="JPEG",
                    quality=90,
                    optimize=True
                )

                normalized_bytes = output.getvalue()

                final_width, final_height = normalized.size

    except InputProcessingError:
        raise

    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning
    ) as exc:

        raise InputProcessingError(
            413,
            "Image is too large or unsafe to decode."
        ) from exc

    except UnidentifiedImageError as exc:

        # Distinguish unsupported files from
        # corrupted files claiming to be images.

        extension = get_file_extension(filename)

        if extension in ALL_SUPPORTED_EXTENSIONS:

            raise InputProcessingError(
                422,
                "The uploaded image appears corrupted "
                "or cannot be decoded."
            ) from exc

        raise InputProcessingError(
            415,
            "The uploaded file is not a supported "
            "image format. Supported formats: "
            "JPEG, PNG and WEBP."
        ) from exc

    except (
        OSError,
        ValueError,
        SyntaxError
    ) as exc:

        raise InputProcessingError(
            422,
            "The uploaded image is corrupted "
            "or cannot be decoded."
        ) from exc

    # ---------------------------------
    # Check filename extension
    # against actual content
    # ---------------------------------

    warnings_list = []

    extension = get_file_extension(filename)

    expected_extensions = EXPECTED_EXTENSIONS[
        detected_format
    ]

    if extension and extension not in expected_extensions:

        warnings_list.append(
            "The filename extension does not match "
            "the detected image format. Processing "
            "used the actual detected format."
        )

    # ---------------------------------
    # Return unified PreparedInput
    # ---------------------------------

    return PreparedInput(
        input_type=InputType.IMAGE,

        source_filename=filename,

        mime_type="image/jpeg",

        text_content="",

        visual_assets=[
            VisualAsset(
                page_number=None,
                mime_type="image/jpeg",
                width=final_width,
                height=final_height,
                data=normalized_bytes
            )
        ],

        warnings=warnings_list
    )
