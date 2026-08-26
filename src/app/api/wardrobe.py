import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db.database import DatabaseManager
from app.schemas.domain import (
    GarmentCard,
    WardrobeUploadResponse,
    WardrobeListResponse,
    DetectRegionsRequest,
    DetectRegionsResponse,
    ClothingRegion,
    WardrobeComposeRequest,
    WardrobeComposeResponse,
)
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.utils.error_handler import parse_and_raise_http_error

router = APIRouter(prefix="/api/wardrobe", tags=["wardrobe"])

settings = get_settings()
db_manager = DatabaseManager(settings.DATABASE_URL)
wardrobe_service = WardrobeService(
    db_manager=db_manager,
    api_key=settings.GEMINI_API_KEY,
    storage_dir=settings.STORAGE_DIR,
    vision_model=settings.VISION_MODEL,
    audit_path=os.path.join(settings.STORAGE_DIR, "logs", "wardrobe_audit.jsonl"),
)
generation_service = GenerationService(
    db_manager=db_manager,
    api_key=settings.GEMINI_API_KEY,
    storage_dir=settings.STORAGE_DIR,
    model_name=settings.IMAGEN_MODEL,
    audit_path=os.path.join(settings.STORAGE_DIR, "logs", "generation_audit.jsonl"),
    wardrobe_service=wardrobe_service,
)


@router.post("/upload", response_model=WardrobeUploadResponse)
async def upload_wardrobe_sheet(file: UploadFile = File(...)):
    """
    Uploads a multi-garment sheet or lookbook image.
    Uses Gemini vision to detect bounding boxes and auto-segments into individual garment cards.
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image (PNG, JPEG, WebP).",
            )
        contents = await file.read()
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        items = await wardrobe_service.segment_and_save_sheet(
            image_bytes=contents,
            original_filename=file.filename or "wardrobe_sheet.png",
        )
        return WardrobeUploadResponse(items=[GarmentCard(**item) for item in items])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.VISION_MODEL, context="Wardrobe Segmentation")


@router.get("/items", response_model=WardrobeListResponse)
async def list_wardrobe_items():
    """
    Lists all saved wardrobe items across sessions.
    """
    items = await wardrobe_service.list_items()
    return WardrobeListResponse(items=[GarmentCard(**item) for item in items])


@router.delete("/items/{item_id}")
async def delete_wardrobe_item(item_id: str):
    """
    Soft-deletes an individual wardrobe item.
    """
    deleted = await wardrobe_service.delete_item(item_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wardrobe item '{item_id}' not found.",
        )
    return {"status": "deleted", "id": item_id}


@router.delete("/items")
async def delete_all_wardrobe_items():
    """
    Soft-deletes all wardrobe items in the library.
    """
    count = await wardrobe_service.delete_all_items()
    return {"status": "deleted", "count": count}



@router.get("/items/{item_id}/image")
async def get_wardrobe_item_image(item_id: str):
    """
    Serves the cropped garment thumbnail image.
    """
    item = await db_manager.get_wardrobe_item(item_id)
    if not item or not item.get("cropped_image_path") or not os.path.exists(item["cropped_image_path"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image for wardrobe item '{item_id}' not found.",
        )
    return FileResponse(item["cropped_image_path"], media_type="image/png")


@router.get("/sources/{filename}")
async def get_wardrobe_source_image(filename: str):
    """
    Serves the original source sheet image.
    """
    filepath = os.path.join(settings.STORAGE_DIR, "wardrobe", "sources", filename)
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source image not found.",
        )
    return FileResponse(filepath)


@router.post("/detect-regions", response_model=DetectRegionsResponse)
async def detect_clothing_regions(request: DetectRegionsRequest):
    """
    Analyzes the active generation image to detect target clothing regions for auto-mask overlay.
    """
    try:
        if not request.generation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="generation_id is required.",
            )
        gen = await db_manager.get_generation(request.generation_id)
        if not gen or not gen.get("master_image_path") or not os.path.exists(gen["master_image_path"]):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation '{request.generation_id}' not found.",
            )
        with open(gen["master_image_path"], "rb") as f:
            img_bytes = f.read()

        regions = await wardrobe_service.detect_clothing_regions(img_bytes)
        return DetectRegionsResponse(regions=[ClothingRegion(**r) for r in regions])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.VISION_MODEL, context="Clothing Region Detection")


@router.post("/compose", response_model=WardrobeComposeResponse)
async def compose_wardrobe(request: WardrobeComposeRequest):
    """
    Performs multi-image garment composition.
    Combines parent generation + selected wardrobe references into a single cohesive output.
    Appends result as a new conversation iteration.
    """
    try:
        conv_id = request.conversation_id
        if not conv_id:
            conv_id = f"conv_{uuid.uuid4().hex[:8]}"
            await db_manager.create_conversation(
                conv_id=conv_id,
                baseline_generation_id=request.parent_id,
            )

        result = await generation_service.compose_wardrobe(
            parent_id=request.parent_id,
            assignments=request.assignments,
            seed=request.seed,
            aspect_ratio=request.aspect_ratio or "2:3",
            negative_prompt=request.negative_prompt,
            conversation_id=conv_id,
            custom_instruction=request.custom_instruction,
        )
        return WardrobeComposeResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.IMAGEN_MODEL, context="Wardrobe Composition")
