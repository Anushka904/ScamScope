
from io import BytesIO

import pymupdf
import pytest

from PIL import Image, ImageDraw

from fastapi.testclient import TestClient

from app.main import app

from app.config import get_settings

from app.engine.input_pipeline import (
    prepare_input,
    prepare_text_input,
    prepare_file_input
)

from app.models.extraction import InputType

from app.tools.input_errors import InputProcessingError

from app.tools.text_processor import normalize_text


client = TestClient(app)


# =====================================================
# TEST HELPERS
# =====================================================

def make_image_bytes(
    width=640,
    height=480,
    image_format="PNG"
):
    """
    Generate an in-memory test image.
    """

    image = Image.new(
        "RGB",
        (width, height),
        color="white"
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (30, 30),
        "Software Developer Internship Offer",
        fill="black"
    )

    output = BytesIO()

    image.save(
        output,
        format=image_format
    )

    return output.getvalue()


def make_text_pdf(
    page_count=1,
    text=(
        "Software Developer Internship Offer. "
        "Responsibilities include coding, testing, "
        "team collaboration, project documentation "
        "and software development activities."
    )
):
    """
    Generate a selectable-text PDF.

    The default content is deliberately longer
    than the 80-character scanned-page threshold.
    """

    document = pymupdf.open()

    for index in range(page_count):

        page = document.new_page()

        page.insert_text(
            (72, 72),
            f"[Page {index + 1}] {text}"
        )

    pdf_bytes = document.tobytes()

    document.close()

    return pdf_bytes


def make_scanned_pdf():
    """
    Generate a PDF containing only a page image.

    Simulates a scanned document with no
    selectable text.
    """

    image_bytes = make_image_bytes()

    document = pymupdf.open()

    page = document.new_page(
        width=595,
        height=842
    )

    page.insert_image(
        page.rect,
        stream=image_bytes
    )

    pdf_bytes = document.tobytes()

    document.close()

    return pdf_bytes


# =====================================================
# TEXT PROCESSING TESTS
# =====================================================

def test_normalize_text():

    text = (
        "Congratulations!\r\n\r\n"
        "Pay   ₹2,000\t to confirm.\x00"
    )

    result = normalize_text(text)

    assert "\r" not in result

    assert "\x00" not in result

    assert "Pay ₹2,000 to confirm." in result


def test_normalize_text_preserves_paragraphs():

    text = "First paragraph.\n\nSecond paragraph."

    result = normalize_text(text)

    assert result == text


def test_normalize_text_rejects_empty():

    with pytest.raises(InputProcessingError):

        normalize_text("   \n   ")


def test_normalize_text_enforces_limit():

    text = "A" * 100_001

    with pytest.raises(InputProcessingError) as error:

        normalize_text(text)

    assert error.value.status_code == 413


# =====================================================
# TEXT INPUT PIPELINE TESTS
# =====================================================

def test_prepare_text_input():

    prepared = prepare_text_input(
        "Congratulations! Pay ₹2,000 to confirm."
    )

    assert prepared.input_type == InputType.TEXT

    assert prepared.mime_type == "text/plain"

    assert "₹2,000" in prepared.text_content

    assert prepared.visual_assets == []


def test_unified_pipeline_accepts_text():

    prepared = prepare_input(
        text="Software Developer Internship."
    )

    assert prepared.input_type == InputType.TEXT


def test_unified_pipeline_rejects_multiple_inputs():

    with pytest.raises(InputProcessingError) as error:

        prepare_input(
            text="Test message",
            file_data=b"some data"
        )

    assert error.value.status_code == 400


# =====================================================
# IMAGE PROCESSING TESTS
# =====================================================

def test_prepare_image_input():

    image_bytes = make_image_bytes()

    prepared = prepare_file_input(
        data=image_bytes,
        filename="offer.png"
    )

    assert prepared.input_type == InputType.IMAGE

    assert prepared.mime_type == "image/jpeg"

    assert len(prepared.visual_assets) == 1

    assert (
        prepared.visual_assets[0].mime_type
        == "image/jpeg"
    )

    assert prepared.visual_assets[0].width == 640

    assert prepared.visual_assets[0].height == 480

    # Confirm normalized bytes are valid JPEG.
    normalized_image = Image.open(
        BytesIO(prepared.visual_assets[0].data)
    )

    assert normalized_image.format == "JPEG"


def test_image_summary_does_not_expose_binary():

    prepared = prepare_file_input(
        data=make_image_bytes(),
        filename="offer.png"
    )

    summary = prepared.to_summary()

    output = summary.model_dump(mode="json")

    assert "data" not in output["visual_assets"][0]

    assert (
        output["visual_assets"][0]["mime_type"]
        == "image/jpeg"
    )


def test_invalid_image_rejected():

    # The filename claims this is a PNG,
    # but its contents are not a valid image.

    with pytest.raises(InputProcessingError) as error:

        prepare_file_input(
            data=b"this is not an image",
            filename="offer.png"
        )

    assert error.value.status_code == 422


def test_unsupported_image_file_rejected():

    # Unsupported extension and unrecognized content.

    with pytest.raises(InputProcessingError) as error:

        prepare_file_input(
            data=b"This is a text file.",
            filename="offer.txt"
        )

    assert error.value.status_code == 415


def test_image_extension_mismatch_warning():

    # Actual image is PNG, but filename says JPG.
    # The processor should trust actual content.

    prepared = prepare_file_input(
        data=make_image_bytes(image_format="PNG"),
        filename="offer.jpg"
    )

    assert prepared.input_type == InputType.IMAGE

    assert len(prepared.warnings) == 1

    assert "extension" in prepared.warnings[0].lower()


# =====================================================
# PDF PROCESSING TESTS
# =====================================================

def test_text_pdf_extraction():

    pdf_bytes = make_text_pdf()

    prepared = prepare_file_input(
        data=pdf_bytes,
        filename="offer.pdf"
    )

    assert prepared.input_type == InputType.PDF

    assert prepared.page_count == 1

    assert (
        "Software Developer Internship"
        in prepared.text_content
    )

    assert prepared.pdf_metadata is not None

    assert prepared.pdf_metadata.page_count == 1

    # A normal text-rich PDF page should not
    # require visual rendering.

    assert prepared.visual_assets == []


def test_scanned_pdf_rendering():

    pdf_bytes = make_scanned_pdf()

    prepared = prepare_file_input(
        data=pdf_bytes,
        filename="scanned_offer.pdf"
    )

    assert prepared.input_type == InputType.PDF

    assert prepared.page_count == 1

    assert len(prepared.visual_assets) == 1

    assert prepared.visual_assets[0].page_number == 1

    assert (
        prepared.visual_assets[0].mime_type
        == "image/png"
    )

    # Ensure rendered content is a valid image.

    image = Image.open(
        BytesIO(prepared.visual_assets[0].data)
    )

    assert image.format == "PNG"


def test_pdf_rejects_too_many_pages():

    settings = get_settings()

    pdf_bytes = make_text_pdf(
        page_count=settings.max_pdf_pages + 1
    )

    with pytest.raises(InputProcessingError) as error:

        prepare_file_input(
            data=pdf_bytes,
            filename="large_offer.pdf"
        )

    assert error.value.status_code == 413


def test_invalid_pdf_signature_rejected():

    with pytest.raises(InputProcessingError) as error:

        prepare_file_input(
            data=b"Not a valid PDF",
            filename="offer.pdf"
        )

    assert error.value.status_code == 422


# =====================================================
# FASTAPI ENDPOINT TESTS
# =====================================================

def test_ingest_text_endpoint():

    response = client.post(
        "/api/ingest",
        data={
            "text": (
                "Congratulations! "
                "Pay ₹2,000 to confirm your internship."
            )
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["input_type"] == "text"

    assert result["text_characters"] > 0

    assert "₹2,000" in result["text_preview"]


def test_ingest_image_endpoint():

    response = client.post(
        "/api/ingest",
        files={
            "file": (
                "offer.png",
                make_image_bytes(),
                "image/png"
            )
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["input_type"] == "image"

    assert result["mime_type"] == "image/jpeg"

    assert len(result["visual_assets"]) == 1


def test_ingest_pdf_endpoint():

    response = client.post(
        "/api/ingest",
        files={
            "file": (
                "offer.pdf",
                make_text_pdf(),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["input_type"] == "pdf"

    assert result["page_count"] == 1

    assert result["text_characters"] > 0


def test_ingest_rejects_both_inputs():

    response = client.post(
        "/api/ingest",
        data={"text": "Test"},
        files={
            "file": (
                "offer.png",
                make_image_bytes(),
                "image/png"
            )
        }
    )

    assert response.status_code == 400


def test_ingest_rejects_no_input():

    response = client.post(
        "/api/ingest"
    )

    assert response.status_code == 422


def test_ingest_rejects_unsupported_file():

    response = client.post(
        "/api/ingest",
        files={
            "file": (
                "offer.txt",
                b"This is an uploaded text file.",
                "text/plain"
            )
        }
    )

    assert response.status_code == 415


def test_extract_endpoint_carries_pdf_metadata_into_phase_four(monkeypatch):
    from app.models.extraction import ExtractedOffer, InputType

    monkeypatch.setattr(
        "app.api.extract.extract_offer",
        lambda prepared: ExtractedOffer(input_type=InputType.PDF),
    )
    response = client.post(
        "/api/extract",
        files={"file": ("offer.pdf", make_text_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_type"] == "pdf"
    assert body["pdf_metadata"]["page_count"] == 1
    assert "data" not in body["pdf_metadata"]
