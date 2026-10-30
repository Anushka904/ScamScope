from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root:
# ScamScope/
#     backend/
#         app/
#             config.py

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """
    Centralized application configuration.

    Values are loaded from:
    1. Environment variables
    2. Root .env file
    3. Default values defined below
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # -----------------------------------
    # Application configuration
    # -----------------------------------

    app_name: str = "ScamScope API"

    app_env: str = "development"

    app_version: str = "1.0.0"

    # -----------------------------------
    # Gemini configuration
    # -----------------------------------

    gemini_api_key: SecretStr | None = None

    gemini_model: str | None = None

    # -----------------------------------
    # External API credentials
    # -----------------------------------

    virustotal_api_key: SecretStr | None = None

    google_safe_browsing_api_key: SecretStr | None = None

    # -----------------------------------
    # Application behaviour
    # -----------------------------------

    demo_mode: bool = True

    # -----------------------------------
    # Upload restrictions
    # -----------------------------------

    max_upload_size_mb: int = Field(
        default=10,
        ge=1,
        le=25
    )

    max_pdf_pages: int = Field(
        default=5,
        ge=1,
        le=20
    )

    # -----------------------------------
    # External tool timeout
    # -----------------------------------

    tool_timeout_seconds: float = Field(
        default=8.0,
        gt=0,
        le=60
    )

    # -----------------------------------
    # Database configuration
    # -----------------------------------

    database_path: Path = (
        PROJECT_ROOT / "backend" / "scamscope.db"
    )

    # -----------------------------------
    # Frontend CORS configuration
    # -----------------------------------

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173"
        ]
    )

    @field_validator("gemini_model", mode="before")
    @classmethod
    def normalize_empty_model(cls, value):
        """
        Convert an empty model setting to None.
        """

        if isinstance(value, str) and not value.strip():
            return None

        return value

    @property
    def gemini_configured(self) -> bool:
        """
        True only when both the API key and
        a model identifier are configured.
        """

        key_available = (
            self.gemini_api_key is not None
            and bool(
                self.gemini_api_key.get_secret_value().strip()
            )
        )

        model_available = (
            self.gemini_model is not None
            and bool(self.gemini_model.strip())
        )

        return key_available and model_available


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached settings instance.

    This prevents repeatedly reading the .env file.
    """

    return Settings()