import os
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends

from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    RefinementRequest,
    RefinementResponse,
    ConversationMessage,
    ConversationResponse,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_db_manager, get_generation_service
from app.db.database import FirestoreManager
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/api", tags=["refinement"])


@router.post("/refine", response_model=RefinementResponse)
def refine_image(
    request: RefinementRequest,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
    generation_service: GenerationService = Depends(get_generation_service),
):
    """
    Step 2: Conversation-based image refinement.
    Sends reference parent image + free-text prompt to Gemini with locked seed synchronously.
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
        messages.append(
            ConversationMessage(
                role="user",
                prompt=user_prompt or gen.get("compiled_prompt"),
                generation_id=gen["id"],
                image_url=f"/api/images/{img_path}",
                seed=gen.get("seed", 0),
                created_at=gen.get("created_at", ""),
            )
        )

    return ConversationResponse(
        conversation_id=conversation_id,
        baseline_generation_id=conv["baseline_generation_id"],
        messages=messages,
    )
