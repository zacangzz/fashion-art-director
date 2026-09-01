import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from typing import Optional

from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    GarmentCard,
    WardrobeUploadResponse,
    WardrobeListResponse,
    DetectRegionsRequest,
    DetectRegionsResponse,
    ClothingRegion,
    WardrobeComposeRequest,
    WardrobeComposeResponse,
    UpscaleGarmentRequest,
    UpscaleGarmentResponse,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import (
    get_db_manager,
    get_wardrobe_service,
    get_generation_service,
    get_storage_service,
)
from app.db.database import FirestoreManager
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/wardrobe", tags=["wardrobe"])


@router.post("/upload", response_model=WardrobeUploadResponse)
def upload_wardrobe_sheet(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vision_model: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    wardrobe_service: WardrobeService = Depends(get_wardrobe_service),
):
    """
    Uploads a multi-garment sheet or lookbook image.
    Uses Gemini vision to detect bounding boxes and auto-segments into individual garment cards synchronously.
    Dispatches asynchronous 4K AI enhancement tasks in the background.
    """
    settings = get_settings()
    eff_vision_model = vision_model or settings.VISION_MODEL
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image (PNG, JPEG, WebP).",
            )
        contents = file.file.read()
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        items = wardrobe_service.segment_and_save_sheet(
            image_bytes=contents,
            original_filename=file.filename or "wardrobe_sheet.png",
            vision_model=eff_vision_model,
            user_id=user["uid"],
        )
        for item in items:
            background_tasks.add_task(
                wardrobe_service.upscale_garment,
                item_id=item["id"],
                user_id=user["uid"],
            )
        return WardrobeUploadResponse(items=[GarmentCard(**item) for item in items])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_vision_model, context="Wardrobe Segmentation")


@router.get("/items", response_model=WardrobeListResponse)
def list_wardrobe_items(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Lists all saved active wardrobe items for the authenticated user.
    """
    try:
        items = db_manager.list_wardrobe_items(user_id=user["uid"])
        return WardrobeListResponse(items=[GarmentCard(**item) for item in items])
    except Exception as exc:
        parse_and_raise_http_error(exc, context="List Wardrobe Items")


@router.post("/items/{item_id}/upscale", response_model=UpscaleGarmentResponse)
def upscale_wardrobe_item(
    item_id: str,
    request: Optional[UpscaleGarmentRequest] = None,
    user: dict = Depends(get_current_user),
    wardrobe_service: WardrobeService = Depends(get_wardrobe_service),
):
    """
    Triggers AI upscaling and enhancement for a single wardrobe item.
    """
    settings = get_settings()
    eff_imagen_model = (request.imagen_model if request else None) or settings.IMAGEN_MODEL
    try:
        result = wardrobe_service.upscale_garment(
            item_id=item_id,
            user_id=user["uid"],
            imagen_model=eff_imagen_model,
        )
        return UpscaleGarmentResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Garment Upscale")


@router.delete("/items/{item_id}")
def delete_wardrobe_item(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Soft-deletes an individual wardrobe item.
    """
    try:
        deleted = db_manager.delete_wardrobe_item(item_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Wardrobe item '{item_id}' not found.",
            )
        return {"status": "deleted", "id": item_id}
    except HTTPException:
        raise
    except Exception as exc:
        parse_and_raise_http_error(exc, context="Delete Wardrobe Item")


@router.delete("/items")
def delete_all_wardrobe_items(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Soft-deletes all wardrobe items in the user library.
    """
    try:
        count = db_manager.delete_all_wardrobe_items(user_id=user["uid"])
        return {"status": "deleted", "count": count}
    except Exception as exc:
        parse_and_raise_http_error(exc, context="Delete All Wardrobe Items")


@router.get("/items/{item_id}/image")
def get_wardrobe_item_image(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the cropped garment thumbnail image via the unified StorageService.
    """
    item = db_manager.get_wardrobe_item(item_id)
    if not item or not item.get("cropped_image_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image for wardrobe item '{item_id}' not found.",
        )
    crop_path = item["cropped_image_path"]
    url = storage_service.get_signed_download_url(crop_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/items/{item_id}/upscaled-image")
def get_wardrobe_item_upscaled_image(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the high-definition AI-upscaled garment image via the unified StorageService.
    Falls back to cropped image if upscale is pending/in-progress.
    """
    item = db_manager.get_wardrobe_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wardrobe item '{item_id}' not found.",
        )
    target_path = item.get("upscaled_image_path") or item.get("cropped_image_path")
    if not target_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No image available for wardrobe item '{item_id}'.",
        )
    url = storage_service.get_signed_download_url(target_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/sources/{filename}")
def get_wardrobe_source_image(
    filename: str,
    user: dict = Depends(get_current_user),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the original source sheet image via the unified StorageService.
    """
    target_path = f"{user['uid']}/wardrobe/sources/{filename}"
    url = storage_service.get_signed_download_url(target_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/detect-regions", response_model=DetectRegionsResponse)
def detect_clothing_regions(
    request: DetectRegionsRequest,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    wardrobe_service: WardrobeService = Depends(get_wardrobe_service),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Analyzes the active generation image to detect target clothing regions for auto-mask overlay.
    """
    settings = get_settings()
    eff_vision_model = request.vision_model or settings.VISION_MODEL
    try:
        if not request.generation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="generation_id is required.",
            )
        gen = db_manager.get_generation(request.generation_id)
        if not gen or not gen.get("master_image_path"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation '{request.generation_id}' not found.",
            )
        img_path = gen["master_image_path"]
        img_bytes = storage_service.download_bytes(img_path)

        regions = wardrobe_service.detect_clothing_regions(
            img_bytes,
            vision_model=eff_vision_model,
        )
        return DetectRegionsResponse(regions=[ClothingRegion(**r) for r in regions])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_vision_model, context="Clothing Region Detection")


@router.post("/compose", response_model=WardrobeComposeResponse)
def compose_wardrobe(
    request: WardrobeComposeRequest,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Performs multi-image garment composition synchronously.
    Combines parent generation + selected wardrobe references into a single cohesive output.
    Appends result as a new conversation iteration.
    """
    settings = get_settings()
    eff_imagen_model = request.imagen_model or settings.IMAGEN_MODEL
    eff_vision_model = request.vision_model or settings.VISION_MODEL
    try:
        conv_id = request.conversation_id
        if not conv_id:
            conv_id = f"conv_{uuid.uuid4().hex[:8]}"
            db_manager.create_conversation(
                user_id=user["uid"],
                conv_id=conv_id,
                baseline_generation_id=request.parent_id,
            )

        result = generation_service.compose_wardrobe(
            parent_id=request.parent_id,
            assignments=request.assignments,
            seed=request.seed,
            aspect_ratio=request.aspect_ratio,
            negative_prompt=request.negative_prompt,
            conversation_id=conv_id,
            custom_instruction=request.custom_instruction,
            imagen_model=eff_imagen_model,
            vision_model=eff_vision_model,
            user_id=user["uid"],
        )
        return WardrobeComposeResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Wardrobe Composition")
