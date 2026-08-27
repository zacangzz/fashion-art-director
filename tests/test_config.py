import pytest
from app.config import Settings, get_settings

def test_config_defaults():
    settings = get_settings()
    assert settings.PORT == 7860
    assert settings.HOST == "127.0.0.1"
    assert settings.STORAGE_DIR is not None
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

