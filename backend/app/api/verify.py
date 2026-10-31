from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.engine.verification import verify_extracted_offer
from app.models.verification import VerificationReport, VerificationRequest

router = APIRouter(
    prefix="/api",
    tags=["Independent Verification"],
)


@router.post(
    "/verify",
    response_model=VerificationReport,
    summary="Run independent checks against extracted offer claims",
)
async def verify_offer(request: VerificationRequest) -> VerificationReport:
    """Run Phase 4 verification. This endpoint does not produce a fraud verdict."""
    return await run_in_threadpool(
        verify_extracted_offer,
        request.extracted,
        get_settings(),
    )
