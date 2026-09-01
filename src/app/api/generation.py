from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    FineTuneGenerationRequest,
    FineTuneGenerationResponse,
    GenerationRequest,
    GenerationResponse,
)
from app.services.generation_service import GenerationService, compile_prompt
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_generation_service

router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate/fine-tune", response_model=FineTuneGenerationResponse)
def fine_tune_generation(
    request: FineTuneGenerationRequest,
    user: dict = Depends(get_current_user),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Step 3: Seed-locked multimodal fine-tuning generation using Prompt Compiler synchronously.
    """
    settings = get_settings()
    eff_imagen_model = request.imagen_model or settings.IMAGEN_MODEL
    try:
        result = generation_service.fine_tune_generation(
            parent_id=request.parent_id or "",
            state=request.schema_data,
            narrative=request.narrative,
            categories=request.categories,
            baseline_narrative=request.baseline_narrative,
            baseline_categories=request.baseline_categories,
            locked_categories=request.locked_categories,
            prompt_override=request.prompt_override,
            seed=request.seed,
            use_image_reference=request.use_image_reference,
            aspect_ratio=request.aspect_ratio or "2:3",
            negative_prompt=request.negative_prompt,
            imagen_model=eff_imagen_model,
            user_id=user["uid"],
        )
        return FineTuneGenerationResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=eff_imagen_model, context="Seed-Locked Fine-Tuning")


def _serialize_legacy_input(request: GenerationRequest) -> str:
    if request.chips:
        categories_map: Dict[str, List[Dict[str, Any]]] = {}
        for chip in request.chips:
            cat = str(chip.category)
            if cat not in categories_map:
                categories_map[cat] = []
            categories_map[cat].append(chip.model_dump())
        return compile_prompt(categories=categories_map)
    if request.prompt_json and isinstance(request.prompt_json, dict):
        return compile_prompt(
            narrative=request.prompt_json.get("narrative"),
            categories=request.prompt_json.get("categories"),
        )
    return "A high-fashion cinematic scene with exquisite detail."


@router.post("/generate", response_model=GenerationResponse)
def generate_image(
    request: GenerationRequest,
    user: dict = Depends(get_current_user),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Backwards-compatible legacy single generation route.
    """
    settings = get_settings()
    compiled = _serialize_legacy_input(request)
    chips_snapshot = (
        request.schema_data
        if request.schema_data
        else (
            request.prompt_json
            if request.prompt_json
            else [chip.model_dump() for chip in (request.chips or [])]
        )
    )

    try:
        result = generation_service.generate_image(
            prompt=compiled,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
            aspect_ratio=request.aspect_ratio,
            parent_id=request.parent_generation_id,
            moodboard_id=request.moodboard_id,
            chips_snapshot=chips_snapshot,
            user_id=user["uid"],
        )
        return GenerationResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.IMAGEN_MODEL, context="Image Generation")
