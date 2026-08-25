import pytest
from app.config import get_settings

def test_config_defaults():
    settings = get_settings()
    assert settings.PORT == 7860
    assert settings.HOST == "127.0.0.1"
    assert settings.STORAGE_DIR is not None
