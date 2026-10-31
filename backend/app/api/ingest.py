from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile
)

from app.config import get_settings

from app.engine.input_pipeline import prepare_input

from app.models.input import IngestionSummary

from app.tools.input_errors import InputProcessingError


router = APIRouter(
    prefix="/api",
    tags=["Input Ingestion"]
)


@router.post(
    "/ingest",
    response_model=IngestionSummary,
    summary="Validate and preprocess an offer"
)
async def ingest_input(

    file: Annotated[
        UploadFile | None,
        File(description="PNG, JPG, WEBP or PDF file")
    ] = None,

    text: Annotated[
        str | None,
        Form(description="Pasted internship/job offer")
    ] = None

):
    """
    Accept exactly one input:

    1. Screenshot/PDF through file.
    2. Pasted message through text.

    Returns a serializable preprocessing summary.

    This endpoint only validates and preprocesses input; use /api/extract for structured extraction.
    """

    # ------------------------------------
    # Validate input combination
    # ------------------------------------

    if file is not None and text is not None:

        raise HTTPException(
            status_code=400,
            detail="Provide either a file or text, not both."
        )

    if file is None and text is None:

        raise HTTPException(
            status_code=422,
            detail="No input provided."
        )

    settings = get_settings()

    try:

        # --------------------------------
        # File input
        # --------------------------------

        if file is not None:

            max_bytes = (
                settings.max_upload_size_mb
                * 1024
                * 1024
            )

            try:

                # Read only one byte beyond the limit.
                content = await file.read(
                    max_bytes + 1
                )

                filename = file.filename

            finally:

                await file.close()

            if len(content) > max_bytes:

                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Maximum file size is "
                        f"{settings.max_upload_size_mb} MB."
                    )
                )

            prepared = prepare_input(
                file_data=content,
                filename=filename,
                settings=settings
            )

        # --------------------------------
        # Pasted text input
        # --------------------------------

        else:

            prepared = prepare_input(
                text=text,
                settings=settings
            )

        return prepared.to_summary()

    except InputProcessingError as exc:

        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail
        ) from exc