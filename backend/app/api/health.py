from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "project": "ScamScope",
        "message": "Backend running successfully"
    }