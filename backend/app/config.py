
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """
    Centralized configuration for ScamScope.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # -------------------------------------
    # Application
    # -------------------------------------

    app_name: str = "ScamScope API"

    app_env: str = "development"

    app_version: str = "1.0.0"

    # -------------------------------------
    # Gemini configuration
    # -------------------------------------

    # Gemini is an optional enhancement. Rule-based extraction is the default
    # so the application remains usable without provider quota or billing.
    gemini_enabled: bool = False

    gemini_api_key: SecretStr | None = None

    gemini_model: str | None = "gemini-3.8-flash"

    gemini_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        le=180,
        description="Maximum time in seconds to wait for one Gemini API request.",
    )

    # -------------------------------------
    # External APIs
    # -------------------------------------

    virustotal_api_key: SecretStr | None = None

    google_safe_browsing_api_key: SecretStr | None = None

    # -------------------------------------
    # Application settings
    # -------------------------------------

    demo_mode: bool = True

    # -------------------------------------
    # Upload limits
    # -------------------------------------

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

    # -------------------------------------
    # External tool timeout
    # -------------------------------------

    tool_timeout_seconds: float = Field(
        default=8.0,
        gt=0,
        le=60
    )

    new_domain_threshold_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Domains registered more recently than this are marked as a weak-to-medium warning indicator.",
    )

    # -------------------------------------
    # Database
    # -------------------------------------

    database_path: Path = (
        PROJECT_ROOT / "backend" / "scamscope.db"
    )

    # -------------------------------------
    # Frontend CORS
    # -------------------------------------

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173"
        ]
    )

    @field_validator("gemini_model", mode="before")
    @classmethod
    def normalize_empty_model(cls, value):

        if isinstance(value, str) and not value.strip():
            return None

        return value

    @property
    def gemini_configured(self) -> bool:

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

    @property
    def gemini_available(self) -> bool:
        """True only when the optional provider is explicitly enabled and configured."""
        return self.gemini_enabled and self.gemini_configured


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached application settings.
    """

    return Settings()
