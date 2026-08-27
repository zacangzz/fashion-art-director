import os
import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.config import get_settings
from app.schemas.domain import (
    AnalyzeAndBaselinesResponse,
    BaselineSummary,
    DirectPhotoUploadResponse,
    MoodboardAnalysisResponse,
    TagChip,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_db_manager, get_vision_service, get_generation_service

router = APIRouter(prefix="/api/moodboard", tags=["moodboard"])
settings = get_settings()

db_manager = get_db_manager()
vision_service = get_vision_service()
generation_service = get_generation_service()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "application/pdf"}


async def _process_and_save_upload_files(
    files: List[UploadFile], storage_dir: str
) -> tuple[str, List[bytes], List[str]]:
    if not files or len(files) < 1 or len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Between 1 and 5 files must be uploaded for analysis. Received 0 or more than 5.",
        )

    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format '{file.content_type}' for file '{file.filename}'. Allowed formats: PNG, JPEG, WebP, PDF.",
            )

    moodboard_id = f"mb_{uuid.uuid4().hex[:12]}"
    mb_dir = os.path.join(storage_dir, "moodboards")
    os.makedirs(mb_dir, exist_ok=True)

    image_bytes_list: List[bytes] = []
    saved_paths: List[str] = []

    for i, file in enumerate(files):
        content = await file.read()
        image_bytes_list.append(content)

        ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "png"
        file_path = os.path.join(mb_dir, f"{moodboard_id}_{i+1}.{ext}")
        with open(file_path, "wb") as f:
            f.write(content)
        saved_paths.append(file_path)

    await db_manager.create_moodboard(moodboard_id, saved_paths)
    return moodboard_id, image_bytes_list, saved_paths


@router.post("/analyze-and-baselines", response_model=AnalyzeAndBaselinesResponse)
async def analyze_and_baselines(
    files: List[UploadFile] = File(...),
    prompt: Optional[str] = Form(None),
    locked_sections: Optional[str] = Form(None),
    locked_categories: Optional[str] = Form(None),
    existing_schema: Optional[str] = Form(None),
    existing_categories: Optional[str] = Form(None),
    existing_narrative: Optional[str] = Form(None),
    aspect_ratio: Optional[str] = Form("1.8:1"),
):
    """
    Step 1: Analyzes 1-5 moodboard files + optional creative prompt baseline ->
    extracts 9-category visual tags & narrative -> triggers 4 concurrent baseline generations.
    """
    moodboard_id, image_bytes_list, saved_paths = await _process_and_save_upload_files(
        files, settings.STORAGE_DIR
    )

    # Parse locked categories (supports both locked_categories and locked_sections param)
    raw_locked = locked_categories or locked_sections
    parsed_locked = None
    if raw_locked:
        try:
            parsed_locked = json.loads(raw_locked) if isinstance(raw_locked, str) else raw_locked
        except Exception:
            parsed_locked = None

    raw_existing = existing_categories or existing_schema
    parsed_existing = None
    if raw_existing:
        try:
            parsed_existing = json.loads(raw_existing) if isinstance(raw_existing, str) else raw_existing
        except Exception:
            parsed_existing = None

    # 1. Vision Analysis -> Narrative & 9-category TagChip dictionary
    try:
        tag_state = await vision_service.extract_tag_studio_state(
            image_bytes_list,
            prompt=prompt,
            locked_categories=parsed_locked,
            existing_categories=parsed_existing.get("categories") if isinstance(parsed_existing, dict) and "categories" in parsed_existing else parsed_existing,
            existing_narrative=existing_narrative or (parsed_existing.get("narrative") if isinstance(parsed_existing, dict) else None),
            image_paths=[os.path.relpath(path) for path in saved_paths],
        )
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.VISION_MODEL, context="Vision Tag & Narrative Extraction")

    # 2. Concurrently Generate 4 Baselines
    eff_aspect_ratio = aspect_ratio or "1.8:1"
    try:
        baselines_raw = await generation_service.generate_4_baselines(
            moodboard_id=moodboard_id,
            state=tag_state,
            aspect_ratio=eff_aspect_ratio,
        )
        baselines = [
            BaselineSummary(
                id=b["id"],
                seed=b["seed"],
                image_url=b["image_url"],
                created_at=b["created_at"],
                aspect_ratio=b.get("aspect_ratio", eff_aspect_ratio),
                resolution=b.get("resolution"),
                compiled_prompt=b.get("compiled_prompt"),
            )
            for b in baselines_raw
        ]
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.IMAGEN_MODEL, context="Concurrent 4-Baseline Generation")

    # Construct strongly typed category tag models for response
    categories_resp = {}
    for cat_name, chip_list in tag_state.get("categories", {}).items():
        categories_resp[cat_name] = [
            TagChip(**c) if isinstance(c, dict) else c
            for c in chip_list
        ]

    return AnalyzeAndBaselinesResponse(
        moodboard_id=moodboard_id,
        master_prompt=tag_state.get("master_prompt"),
        narrative=tag_state.get("narrative", ""),
        categories=categories_resp,
        schema_data=tag_state,
        baselines=baselines,
    )


@router.post("/analyze", response_model=MoodboardAnalysisResponse)
async def analyze_moodboard(
    files: List[UploadFile] = File(...),
    prompt: Optional[str] = Form(None),
):
    """
    Backwards-compatible analysis endpoint.
    """
    moodboard_id, image_bytes_list, saved_paths = await _process_and_save_upload_files(
        files, settings.STORAGE_DIR
    )

    try:
        chips = await vision_service.analyze_moodboard(
            image_bytes_list,
            prompt=prompt,
            image_paths=[os.path.relpath(path) for path in saved_paths],
        )
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.VISION_MODEL, context="Moodboard Analysis")

    return MoodboardAnalysisResponse(
        moodboard_id=moodboard_id,
        extracted_chips=chips,
        extracted_json=None,
    )


@router.post("/upload-direct-photo", response_model=DirectPhotoUploadResponse)
async def upload_direct_photo(
    file: UploadFile = File(...),
    aspect_ratio: Optional[str] = Form(None),
):
    """
    Direct Photo Ingestion: Allows users to skip Step 1 Art Direction by uploading
    their own photo. Saves the photo directly as a baseline record with auto-detected/selected
    aspect ratio, ready for immediate conversation-based refinement.
    """
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{file.content_type}' for photo upload. Allowed formats: PNG, JPEG, WebP.",
        )

    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        result = await generation_service.register_uploaded_photo(
            image_bytes=content,
            filename=file.filename,
            custom_aspect_ratio=aspect_ratio,
        )
        return DirectPhotoUploadResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name="DirectPhotoIngestion", context="Direct Photo Ingestion")

