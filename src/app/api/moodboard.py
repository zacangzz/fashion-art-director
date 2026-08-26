import os
import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.config import get_settings
from app.db.database import DatabaseManager
from app.schemas.domain import (
    AnalyzeAndBaselinesResponse,
    BaselineSummary,
    MoodboardAnalysisResponse,
    TagChip,
)
from app.services.vision_service import VisionService
from app.services.generation_service import GenerationService
from app.utils.error_handler import parse_and_raise_http_error

router = APIRouter(prefix="/api/moodboard", tags=["moodboard"])

settings = get_settings()
db_manager = DatabaseManager(settings.DATABASE_URL)
vision_service = VisionService(
    settings.GEMINI_API_KEY,
    model_name=settings.VISION_MODEL,
    audit_path=os.path.join(settings.STORAGE_DIR, "logs", "vision_audit.jsonl"),
)
generation_service = GenerationService(
    db_manager=db_manager,
    api_key=settings.GEMINI_API_KEY,
    storage_dir=settings.STORAGE_DIR,
    model_name=settings.IMAGEN_MODEL,
)

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

