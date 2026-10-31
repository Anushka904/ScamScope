from pathlib import Path

from app.config import (
    get_settings,
    Settings,
    PROJECT_ROOT,
    ENV_FILE
)


def test_project_root():

    assert PROJECT_ROOT.name == "ScamScope"


def test_env_file_location():

    assert ENV_FILE == PROJECT_ROOT / ".env"


def test_settings_load():

    settings = get_settings()

    assert settings.app_name == "ScamScope API"

    assert settings.app_version == "1.0.0"


def test_upload_limits():

    settings = get_settings()

    assert settings.max_upload_size_mb >= 1

    assert settings.max_upload_size_mb <= 25

    assert settings.max_pdf_pages >= 1

    assert settings.max_pdf_pages <= 20


def test_database_path():

    settings = get_settings()

    assert isinstance(settings.database_path, Path)

    assert settings.database_path.name == "scamscope.db"

def test_gemini_request_timeout_defaults_to_120_seconds():
    settings = Settings(_env_file=None)
    assert settings.gemini_timeout_seconds == 120.0


def test_gemini_is_disabled_by_default():
    settings = Settings(_env_file=None)
    assert settings.gemini_enabled is False
    assert settings.gemini_available is False


def test_gemini_requires_explicit_enable_and_credentials():
    disabled = Settings(_env_file=None, gemini_api_key="key")
    enabled = Settings(_env_file=None, gemini_enabled=True, gemini_api_key="key")
    missing_key = Settings(_env_file=None, gemini_enabled=True, gemini_api_key=None)
    assert disabled.gemini_available is False
    assert enabled.gemini_available is True
    assert missing_key.gemini_available is False


def test_new_domain_threshold_defaults_to_thirty_days():
    settings = Settings(_env_file=None)
    assert settings.new_domain_threshold_days == 30
