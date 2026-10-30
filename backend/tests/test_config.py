from pathlib import Path

from app.config import (
    get_settings,
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