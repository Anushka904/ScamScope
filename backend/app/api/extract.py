
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile
)

from starlette.concurrency import run_in_threadpool

from app.config import get_settings

from app.engine.input_pipeline import prepare_input

from app.agents.extractor import (
    extract_offer,
    ExtractionError
)

from app.models.extraction import ExtractedOffer

from app.tools.input_errors import InputProcessingError


router = APIRouter(
    prefix="/api",
    tags=["Offer Extraction"]
)


@router.post(
    "/extract",
    response_model=ExtractedOffer,
    summary="Extract structured claims from a recruitment offer"
)
async def extract_input(

    file: Annotated[
        UploadFile | None,
        File(
            description="PNG, JPEG, WEBP or PDF recruitment document"
        )
    ] = None,

    text: Annotated[
        str | None,
        Form(description="Pasted internship/job offer")
    ] = None

):
    """
    Accept exactly one input and extract structured claims.

    Rule-based extraction is the default and does not require API credentials.
    Optional Gemini extraction can be explicitly enabled in backend settings.
    """

    # -------------------------------------
    # Normalize optional inputs
    # -------------------------------------

    upload = (
        file
        if file is not None and file.filename
        else None
    )

    text_value = (
        text
        if text is not None and text.strip()
        else None
    )

    # -------------------------------------
    # Validate input combination
    # -------------------------------------

    if upload is not None and text_value is not None:

        if file is not None:
            await file.close()

        raise HTTPException(
            status_code=400,
            detail="Provide either a file or text, not both."
        )

    if upload is None and text_value is None:

        if file is not None:
            await file.close()

        raise HTTPException(
            status_code=422,
            detail="No usable input provided."
        )

    settings = get_settings()

    try:

        # ---------------------------------
        # File input
        # ---------------------------------

        if upload is not None:

            max_bytes = (
                settings.max_upload_size_mb
                * 1024
                * 1024
            )

            try:

                content = await upload.read(
                    max_bytes + 1
                )

            finally:

                await upload.close()

            if len(content) > max_bytes:

                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Maximum upload size is "
                        f"{settings.max_upload_size_mb} MB."
                    )
                )

            prepared = prepare_input(
                file_data=content,
                filename=upload.filename,
                settings=settings
            )

        # ---------------------------------
        # Pasted text input
        # ---------------------------------

        else:

            prepared = prepare_input(
                text=text_value,
                settings=settings
            )

        # ---------------------------------
        # Run extraction in the thread pool (local rules by default; optional Gemini).
        # ---------------------------------

        extracted_offer = await run_in_threadpool(
            extract_offer,
            prepared
        )

        # Carry PDF metadata into Phase 4 without exposing PDF binary data.
        if prepared.pdf_metadata is not None:
            extracted_offer = extracted_offer.model_copy(
                update={"pdf_metadata": prepared.pdf_metadata}
            )

        return extracted_offer

    except InputProcessingError as exc:

        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail
        ) from exc

    except ExtractionError as exc:

        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail
        ) from exc
