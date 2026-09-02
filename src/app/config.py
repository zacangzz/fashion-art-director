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
    GCP_PROJECT_ID: str = "image-gen-studio-local"
    GCS_BUCKET: str = "image-gen-studio-local-bucket"
    DAILY_SPEND_CAP_USD: float = 20.0
    ENVIRONMENT: str = "local"
    STORAGE_DIR: str = "./storage"
    VISION_MODEL: str = "gemini-3.5-flash-lite"
    IMAGEN_MODEL: str = "gemini-3-pro-image"
    INPAINT_MODEL: str = "gemini-3-pro-image"
    GENAI_TIMEOUT_SECONDS: int = 900
    ADMIN_EMAILS: str = ""

    def is_admin_email(self, email: str | None) -> bool:
        if not email:
            return False
        admin_list = [e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()]
        return email.strip().lower() in admin_list

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

    @field_validator("GEMINI_API_KEY", "GCP_PROJECT_ID", "GCS_BUCKET", "ENVIRONMENT", mode="before")
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

@lru_cache()
def get_settings() -> Settings:
    return Settings()
