from typing import List, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api/models", tags=["Models Configuration"])

AVAILABLE_VISION_MODELS: List[str] = [
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
]

AVAILABLE_IMAGEN_MODELS: List[str] = [
    "gemini-3.1-flash-lite-image",
    "gemini-3.1-flash-image",
    "gemini-3-pro-image",
]

FIXED_INPAINT_MODEL: str = "gemini-3-pro-image"


class ModelConfigResponse(BaseModel):
    available_vision_models: List[str]
    available_imagen_models: List[str]
    default_vision_model: str
    default_imagen_model: str
    inpaint_model: str


@router.get("/config", response_model=ModelConfigResponse)
async def get_models_config() -> Dict[str, Any]:
    """
    Returns available vision models and image generation models,
    as well as default models configured in the environment.
    """
    settings = get_settings()
    
    # Ensure current env default is included in available models if custom
    vision_models = list(AVAILABLE_VISION_MODELS)
    if settings.VISION_MODEL and settings.VISION_MODEL not in vision_models:
        vision_models.append(settings.VISION_MODEL)

    imagen_models = list(AVAILABLE_IMAGEN_MODELS)
    if settings.IMAGEN_MODEL and settings.IMAGEN_MODEL not in imagen_models:
        imagen_models.append(settings.IMAGEN_MODEL)

    return {
        "available_vision_models": vision_models,
        "available_imagen_models": imagen_models,
        "default_vision_model": settings.VISION_MODEL,
        "default_imagen_model": settings.IMAGEN_MODEL,
        "inpaint_model": FIXED_INPAINT_MODEL,
    }
