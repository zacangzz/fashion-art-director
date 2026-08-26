import os
from functools import lru_cache
from typing import Optional
from google import genai

from app.config import get_settings
from app.db.database import DatabaseManager
from app.services.vision_service import VisionService
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.services.export_service import ExportService


@lru_cache()
def get_db_manager() -> DatabaseManager:
    settings = get_settings()
    return DatabaseManager(settings.DATABASE_URL)


@lru_cache()
def get_gemini_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)


@lru_cache()
def get_vision_service() -> VisionService:
    settings = get_settings()
    return VisionService(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.VISION_MODEL,
        audit_path=os.path.join(settings.STORAGE_DIR, "logs", "vision_audit.jsonl"),
        client=get_gemini_client(),
    )


@lru_cache()
def get_wardrobe_service() -> WardrobeService:
    settings = get_settings()
    return WardrobeService(
        db_manager=get_db_manager(),
        api_key=settings.GEMINI_API_KEY,
        storage_dir=settings.STORAGE_DIR,
        vision_model=settings.VISION_MODEL,
        audit_path=os.path.join(settings.STORAGE_DIR, "logs", "wardrobe_audit.jsonl"),
        client=get_gemini_client(),
    )


@lru_cache()
def get_generation_service() -> GenerationService:
    settings = get_settings()
    return GenerationService(
        db_manager=get_db_manager(),
        api_key=settings.GEMINI_API_KEY,
        storage_dir=settings.STORAGE_DIR,
        model_name=settings.IMAGEN_MODEL,
        inpaint_model_name=settings.INPAINT_MODEL,
        audit_path=os.path.join(settings.STORAGE_DIR, "logs", "generation_audit.jsonl"),
        wardrobe_service=get_wardrobe_service(),
        client=get_gemini_client(),
    )


@lru_cache()
def get_export_service() -> ExportService:
    settings = get_settings()
    return ExportService(
        db_manager=get_db_manager(),
        generation_service=get_generation_service(),
        storage_dir=settings.STORAGE_DIR,
    )
