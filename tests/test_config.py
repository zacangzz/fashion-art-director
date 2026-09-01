import pytest
from app.config import Settings, get_settings

def test_config_defaults(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)
    assert settings.PORT == 7860
    assert settings.HOST == "127.0.0.1"
    assert settings.GCP_PROJECT_ID == "image-gen-studio-local"
    assert settings.GCS_BUCKET == "image-gen-studio-local-bucket"
    assert settings.DAILY_SPEND_CAP_USD == 20.0
    assert settings.ENVIRONMENT == "local"
    assert settings.VISION_MODEL == "gemini-3.5-flash-lite"
    assert settings.IMAGEN_MODEL == "gemini-3-pro-image"
    assert settings.INPAINT_MODEL == "gemini-3-pro-image"

def test_empty_env_model_fallback():
    settings = Settings(
        VISION_MODEL="",
        IMAGEN_MODEL="",
        INPAINT_MODEL="",
        _env_file=None,
    )
    assert settings.VISION_MODEL == "gemini-3.5-flash-lite"
    assert settings.IMAGEN_MODEL == "gemini-3-pro-image"
    assert settings.INPAINT_MODEL == "gemini-3-pro-image"
