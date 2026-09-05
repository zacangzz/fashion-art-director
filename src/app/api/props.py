import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from typing import Optional

from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    PropCard,
    PropUploadResponse,
    PropListResponse,
    UpscalePropRequest,
    UpscalePropResponse,
    PropComposeRequest,
    PropComposeResponse,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import (
    get_db_manager,
    get_prop_service,
    get_generation_service,
    get_storage_service,
)
from app.db.database import FirestoreManager
from app.services.prop_service import PropService
from app.services.generation_service import GenerationService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/props", tags=["props"])


@router.post("/upload-sheet", response_model=PropUploadResponse)
def upload_prop_sheet(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    vision_model: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    prop_service: PropService = Depends(get_prop_service),
):
    """
    Uploads a multi-prop catalog sheet image.
    Uses Gemini Vision to detect 2D bounding boxes and auto-segments individual prop items synchronously.
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
        items = prop_service.segment_and_save_sheet(
            image_bytes=contents,
            original_filename=file.filename or "prop_sheet.png",
            vision_model=eff_vision_model,
            user_id=user["uid"],
        )
        for item in items:
            background_tasks.add_task(
                prop_service.upscale_prop,
                item_id=item["id"],
                user_id=user["uid"],
            )
        return PropUploadResponse(items=[PropCard(**item) for item in items])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_vision_model, context="Prop Catalog Segmentation")


@router.post("/upload-single", response_model=PropUploadResponse)
def upload_single_prop(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    vision_model: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    prop_service: PropService = Depends(get_prop_service),
):
    """
    Directly uploads an isolated, single prop image.
    Runs material & finish feature extraction synchronously and triggers 4K upscale asynchronously.
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
        item = prop_service.upload_single_prop(
            image_bytes=contents,
            filename=file.filename or "prop_item.png",
            category=category or "decor",
            vision_model=eff_vision_model,
            user_id=user["uid"],
        )
        background_tasks.add_task(
            prop_service.upscale_prop,
            item_id=item["id"],
            user_id=user["uid"],
        )
        return PropUploadResponse(items=[PropCard(**item)])
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_vision_model, context="Single Prop Upload")


@router.get("/items", response_model=PropListResponse)
def list_prop_items(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Lists all saved active prop items for the authenticated user.
    """
    try:
        items = db_manager.list_prop_items(user_id=user["uid"])
        return PropListResponse(items=[PropCard(**item) for item in items])
    except Exception as exc:
        parse_and_raise_http_error(exc, context="List Prop Items")


@router.post("/items/{item_id}/upscale", response_model=UpscalePropResponse)
def upscale_prop_item(
    item_id: str,
    request: Optional[UpscalePropRequest] = None,
    user: dict = Depends(get_current_user),
    prop_service: PropService = Depends(get_prop_service),
):
    """
    Triggers AI upscaling and enhancement for a single prop item.
    """
    settings = get_settings()
    eff_imagen_model = (request.imagen_model if request else None) or settings.IMAGEN_MODEL
    try:
        result = prop_service.upscale_prop(
            item_id=item_id,
            user_id=user["uid"],
            imagen_model=eff_imagen_model,
        )
        return UpscalePropResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Prop Upscale")


@router.delete("/items/{item_id}")
def delete_prop_item(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Soft-deletes an individual prop item and cascades soft-deletion to its assignments.
    """
    try:
        deleted = db_manager.delete_prop_item(item_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prop item '{item_id}' not found.",
            )
        return {"status": "deleted", "id": item_id}
    except HTTPException:
        raise
    except Exception as exc:
        parse_and_raise_http_error(exc, context="Delete Prop Item")


@router.delete("/items")
def delete_all_prop_items(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Soft-deletes all prop items in the user library.
    """
    try:
        count = db_manager.delete_all_prop_items(user_id=user["uid"])
        return {"status": "deleted", "count": count}
    except Exception as exc:
        parse_and_raise_http_error(exc, context="Delete All Prop Items")


@router.get("/items/{item_id}/image")
def get_prop_item_image(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the cropped prop thumbnail image via the unified StorageService.
    """
    item = db_manager.get_prop_item(item_id)
    if not item or not item.get("cropped_image_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image for prop item '{item_id}' not found.",
        )
    crop_path = item["cropped_image_path"]
    url = storage_service.get_signed_download_url(crop_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/items/{item_id}/upscaled-image")
def get_prop_item_upscaled_image(
    item_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the high-definition AI-upscaled prop image via the unified StorageService.
    Falls back to cropped image if upscale is pending or not yet generated.
    """
    item = db_manager.get_prop_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prop item '{item_id}' not found.",
        )
    target_path = item.get("upscaled_image_path") or item.get("cropped_image_path")
    if not target_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No image available for prop item '{item_id}'.",
        )
    url = storage_service.get_signed_download_url(target_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/sources/{filename}")
def get_prop_source_image(
    filename: str,
    user: dict = Depends(get_current_user),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Serves the original prop catalog sheet image via the unified StorageService.
    """
    target_path = f"{user['uid']}/props/sources/{filename}"
    url = storage_service.get_signed_download_url(target_path)
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.post("/compose", response_model=PropComposeResponse)
def compose_props(
    request: PropComposeRequest,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Performs multi-image prop composition with Gemini Vision spatial scene grounding.
    Combines parent generation + selected prop references into a cohesive output image.
    Preserves model identity, garment integrity, and realistic contact shadows.
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

        result = generation_service.compose_props(
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
        return PropComposeResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Prop Composition")
