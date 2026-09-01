import os
from functools import lru_cache
from typing import Optional
from google import genai
from google.genai import types

from app.config import get_settings
from app.firebase_init import get_storage_bucket, get_firestore_client
from app.db.database import DatabaseManager, FirestoreManager
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from app.services.vision_service import VisionService
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.services.export_service import ExportService
from app.utils.telemetry import TelemetryLogger


@lru_cache()
def get_db_manager() -> FirestoreManager:
    settings = get_settings()
    client = get_firestore_client(settings.GCP_PROJECT_ID)
    return FirestoreManager(client)


@lru_cache()
def get_storage_service() -> StorageService:
    settings = get_settings()
    bucket = get_storage_bucket(settings.GCS_BUCKET)
    return StorageService(bucket=bucket, environment=settings.ENVIRONMENT, storage_dir=settings.STORAGE_DIR)


@lru_cache()
def get_gemini_client() -> genai.Client:
    settings = get_settings()
    timeout_ms = settings.GENAI_TIMEOUT_SECONDS * 1000
    http_opts = types.HttpOptions(timeout=timeout_ms)
    api_key = settings.GEMINI_API_KEY or "dummy_api_key_for_unconfigured_env"
    return genai.Client(api_key=api_key, http_options=http_opts)



@lru_cache()
def get_image_generator() -> ImageGenerator:
    settings = get_settings()
    client = get_gemini_client()
    telemetry = TelemetryLogger(
        component="generation",
    )
    return ImageGenerator(
        client=client,
        default_model=settings.IMAGEN_MODEL,
        telemetry=telemetry,
    )


@lru_cache()
def get_vision_service() -> VisionService:
    settings = get_settings()
    return VisionService(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.VISION_MODEL,
        client=get_gemini_client(),
    )


@lru_cache()
def get_wardrobe_service() -> WardrobeService:
    settings = get_settings()
    return WardrobeService(
        db_manager=get_db_manager(),
        storage_service=get_storage_service(),
        api_key=settings.GEMINI_API_KEY,
        vision_model=settings.VISION_MODEL,
        imagen_model=settings.IMAGEN_MODEL,
        client=get_gemini_client(),
        image_generator=get_image_generator(),
    )


@lru_cache()
def get_generation_service() -> GenerationService:
    settings = get_settings()
    ws = get_wardrobe_service()
    vs = get_vision_service()
    return GenerationService(
        db_manager=get_db_manager(),
        storage_service=get_storage_service(),
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.IMAGEN_MODEL,
        inpaint_model_name=settings.INPAINT_MODEL,
        wardrobe_service=ws,
        vision_service=vs,
        client=get_gemini_client(),
        image_generator=get_image_generator(),
    )


@lru_cache()
def get_export_service() -> ExportService:
    return ExportService(
        db_manager=get_db_manager(),
        storage_service=get_storage_service(),
        image_generator=get_image_generator(),
    )
