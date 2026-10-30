
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
    tags=["Gemini Extraction"]
)


@router.post(
    "/extract",
    response_model=ExtractedOffer,
    summary="Extract offer information using Gemini"
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
    Accept exactly one input and extract its
    structured information using Gemini.
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
        # Run Gemini in thread pool
        # ---------------------------------

        extracted_offer = await run_in_threadpool(
            extract_offer,
            prepared
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
