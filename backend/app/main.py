from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router


# Load centralized configuration
settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered evidence-based investigation "
        "of suspicious internship and job offers."
    ),
    version=settings.app_version
)


# Frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Register API routes
app.include_router(health_router)


@app.get("/")
async def home():

    return {
        "project": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "demo_mode": settings.demo_mode
    }