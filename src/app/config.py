import os
from functools import lru_cache
from typing import Any
from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    PORT: int = 7860
    HOST: str = "127.0.0.1"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./storage/studio.db"
    STORAGE_DIR: str = "./storage"
    VISION_MODEL: str = "gemini-3.5-flash-lite"
    IMAGEN_MODEL: str = "gemini-3-pro-image"
    INPAINT_MODEL: str = "gemini-3-pro-image"
    GENAI_TIMEOUT_SECONDS: int = 300

    @field_validator("VISION_MODEL", "IMAGEN_MODEL", "INPAINT_MODEL", mode="before")
    @classmethod
    def sanitize_model_name(cls, v: Any, info: ValidationInfo) -> str:
        defaults = {
            "VISION_MODEL": "gemini-3.5-flash-lite",
            "IMAGEN_MODEL": "gemini-3-pro-image",
            "INPAINT_MODEL": "gemini-3-pro-image",
        }
        if isinstance(v, str):
            v = v.split("#")[0].strip()
        if not v:
            return defaults.get(info.field_name, "")
        return v

    @field_validator("GEMINI_API_KEY", "DATABASE_URL", mode="before")
    @classmethod
    def sanitize_env_string(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.split("#")[0].strip()
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self) -> None:
        os.makedirs(os.path.join(self.STORAGE_DIR, "moodboards"), exist_ok=True)
        os.makedirs(os.path.join(self.STORAGE_DIR, "generations"), exist_ok=True)

@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
