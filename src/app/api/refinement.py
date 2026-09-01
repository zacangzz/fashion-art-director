import os
import io
import math
import time
import uuid
from typing import List, Optional
from PIL import Image
from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File

from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    RefinementRequest,
    RefinementResponse,
    ConversationMessage,
    ConversationResponse,
    BackgroundReference,
    BackgroundUploadResponse,
    BackgroundListResponse,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_db_manager, get_generation_service, get_storage_service
from app.db.database import FirestoreManager
from app.services.storage_service import StorageService
from app.services.generation_service import GenerationService
from app.utils.telemetry import TelemetryLogger

router = APIRouter(prefix="/api", tags=["refinement"])
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


@router.post("/backgrounds/upload", response_model=BackgroundUploadResponse)
def upload_background_reference(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    storage_service: StorageService = Depends(get_storage_service),
):
    """
    Upload and save a reference background image to the user's background library.
    Generates thumbnail and extracts aspect ratio.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file.content_type}'. Allowed formats: PNG, JPEG, WebP.",
        )
    user_id = user["uid"]
    start_time = time.time()
    req_id = f"bgupload_{uuid.uuid4().hex[:8]}"
    bg_id = f"bg_{uuid.uuid4().hex[:10]}"

    try:
        data = file.file.read()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        img = Image.open(io.BytesIO(data))
        w, h = img.size
        gcd_val = math.gcd(w, h)
        aspect_ratio = f"{w // gcd_val}:{h // gcd_val}" if gcd_val > 0 else "16:9"

        # Generate lightweight thumbnail
        thumb = img.copy()
        thumb.thumbnail((320, 320))
        thumb_buf = io.BytesIO()
        thumb.save(thumb_buf, format="PNG")
        thumb_bytes = thumb_buf.getvalue()

        ext = (file.filename or "image.png").split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            ext = "png"
        filename = f"{bg_id}.{ext}"
        thumb_filename = f"{bg_id}_thumb.png"

        img_storage_path = storage_service.upload_bytes(
            user_id=user_id,
            category="backgrounds",
            filename=filename,
            data=data,
            content_type=file.content_type,
        )
        thumb_storage_path = storage_service.upload_bytes(
            user_id=user_id,
            category="backgrounds",
            filename=thumb_filename,
            data=thumb_bytes,
            content_type="image/png",
        )

        bg_record = db_manager.create_background_reference(
            user_id=user_id,
            bg_data={
                "id": bg_id,
                "original_filename": file.filename or "background_reference.png",
                "image_path": img_storage_path,
                "thumbnail_path": thumb_storage_path,
                "aspect_ratio": aspect_ratio,
                "tags": [],
            },
        )

        duration_ms = (time.time() - start_time) * 1000
        telemetry = TelemetryLogger(component="background")
        telemetry.record_event(
            event="background_upload",
            request_id=req_id,
            component="background",
            user_id=user_id,
            duration_ms=duration_ms,
            inputs={"filename": file.filename, "size_bytes": len(data), "width": w, "height": h},
            outputs={"bg_id": bg_id, "image_path": img_storage_path},
        )

        return BackgroundUploadResponse(
            id=bg_id,
            image_url=bg_record["image_url"],
            thumbnail_url=bg_record.get("thumbnail_url"),
            original_filename=bg_record.get("original_filename"),
            aspect_ratio=bg_record.get("aspect_ratio"),
            created_at=bg_record["created_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        parse_and_raise_http_error(exc, context="Background Reference Upload")


@router.get("/backgrounds", response_model=BackgroundListResponse)
def list_background_references(
    limit: int = 50,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    List user's stored reusable reference background library items.
    """
    user_id = user["uid"]
    items = db_manager.list_background_references(user_id=user_id, limit=limit)
    return BackgroundListResponse(
        items=[BackgroundReference(**item) for item in items],
        total=len(items),
    )


@router.delete("/backgrounds/{bg_id}")
def delete_background_reference(
    bg_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Soft-delete a stored reference background item.
    """
    user_id = user["uid"]
    success = db_manager.delete_background_reference(user_id=user_id, bg_id=bg_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background reference '{bg_id}' not found or access denied.",
        )
    telemetry = TelemetryLogger(component="background")
    telemetry.record_event(
        event="background_delete",
        component="background",
        user_id=user_id,
        inputs={"bg_id": bg_id},
    )
    return {"status": "deleted", "id": bg_id}


@router.post("/refine", response_model=RefinementResponse)
def refine_image(
    request: RefinementRequest,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Step 2: Conversation-based image refinement.
    Sends reference parent image + free-text prompt (+ optional background reference) to Gemini.
    """
    settings = get_settings()
    user_id = user["uid"]
    eff_imagen_model = request.imagen_model or settings.IMAGEN_MODEL
    try:
        conv_id = request.conversation_id
        if not conv_id:
            conv_id = f"conv_{uuid.uuid4().hex[:8]}"
            db_manager.create_conversation(
                user_id=user_id,
                conv_id=conv_id,
                baseline_generation_id=request.parent_id,
            )

        result = generation_service.refine_generation(
            parent_id=request.parent_id,
            prompt=request.prompt,
            seed=request.seed,
            aspect_ratio=request.aspect_ratio or "2:3",
            negative_prompt=request.negative_prompt,
            conversation_id=conv_id,
            imagen_model=eff_imagen_model,
            background_reference_id=request.background_reference_id,
            perspective_mode=request.perspective_mode,
            depth_of_field=request.depth_of_field,
            lighting_mode=request.lighting_mode,
            spatial_staging=request.spatial_staging,
            user_id=user_id,
        )
        return RefinementResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Refinement Generation")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation_history(
    conversation_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Fetch all refinement generations associated with a conversation thread.
    """
    conv = db_manager.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    generations = db_manager.list_conversation_messages(conversation_id)
    baseline_record = db_manager.get_generation(conv["baseline_generation_id"])
    messages: List[ConversationMessage] = []

    if baseline_record:
        img_path = baseline_record.get("master_image_path", "")
        messages.append(
            ConversationMessage(
                role="baseline",
                prompt=baseline_record.get("compiled_prompt") or baseline_record.get("prompt"),
                generation_id=baseline_record["id"],
                image_url=f"/api/images/{img_path}",
                seed=baseline_record.get("seed", 0),
                created_at=baseline_record.get("created_at", ""),
            )
        )

    for gen in generations:
        schema = gen.get("schema_json") or {}
        user_prompt = schema.get("refinement_prompt") if isinstance(schema, dict) else None
        img_path = gen.get("master_image_path", "")
        bg_ref_id = gen.get("background_reference_id")
        bg_ref_url = gen.get("background_reference_url")
        bg_meta = gen.get("background_harmonization_meta")

        messages.append(
            ConversationMessage(
                role="user",
                prompt=user_prompt or gen.get("compiled_prompt"),
                generation_id=gen["id"],
                image_url=f"/api/images/{img_path}",
                seed=gen.get("seed", 0),
                created_at=gen.get("created_at", ""),
                background_reference_id=bg_ref_id,
                background_reference_url=bg_ref_url,
                background_harmonization_meta=bg_meta,
            )
        )

    return ConversationResponse(
        conversation_id=conversation_id,
        baseline_generation_id=conv["baseline_generation_id"],
        messages=messages,
    )

