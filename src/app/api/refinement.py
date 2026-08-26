import os
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.schemas.domain import (
    RefinementRequest,
    RefinementResponse,
    ConversationMessage,
    ConversationResponse,
)
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_db_manager, get_generation_service

router = APIRouter(prefix="/api", tags=["refinement"])
settings = get_settings()

db_manager = get_db_manager()
generation_service = get_generation_service()


@router.post("/refine", response_model=RefinementResponse)
async def refine_image(request: RefinementRequest):
    """
    Step 2: Conversation-based image refinement.
    Sends reference parent image + free-text prompt to Gemini with locked seed.
    """
    try:
        conv_id = request.conversation_id
        if not conv_id:
            conv_id = f"conv_{uuid.uuid4().hex[:8]}"
            await db_manager.create_conversation(
                conv_id=conv_id,
                baseline_generation_id=request.parent_id,
            )

        result = await generation_service.refine_generation(
            parent_id=request.parent_id,
            prompt=request.prompt,
            seed=request.seed,
            aspect_ratio=request.aspect_ratio or "2:3",
            negative_prompt=request.negative_prompt,
            conversation_id=conv_id,
        )
        return RefinementResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.IMAGEN_MODEL, context="Refinement Generation")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_history(conversation_id: str):
    """
    Fetch all refinement generations associated with a conversation thread.
    """
    conv = await db_manager.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    generations = await db_manager.list_conversation_messages(conversation_id)

    # Also fetch baseline record to include as initial message
    baseline_record = await db_manager.get_generation(conv["baseline_generation_id"])
    messages: List[ConversationMessage] = []

    if baseline_record:
        filename = os.path.basename(baseline_record["master_image_path"])
        messages.append(
            ConversationMessage(
                role="baseline",
                prompt=baseline_record.get("compiled_prompt") or baseline_record.get("prompt"),
                generation_id=baseline_record["id"],
                image_url=f"/api/images/{filename}",
                seed=baseline_record.get("seed", 0),
                created_at=baseline_record.get("created_at", ""),
            )
        )

    for gen in generations:
        schema = gen.get("schema_json") or {}
        user_prompt = schema.get("refinement_prompt") if isinstance(schema, dict) else None
        filename = os.path.basename(gen["master_image_path"])
        messages.append(
            ConversationMessage(
                role="user",
                prompt=user_prompt or gen.get("compiled_prompt"),
                generation_id=gen["id"],
                image_url=f"/api/images/{filename}",
                seed=gen.get("seed", 0),
                created_at=gen.get("created_at", ""),
            )
        )

    return ConversationResponse(
        conversation_id=conversation_id,
        baseline_generation_id=conv["baseline_generation_id"],
        messages=messages,
    )
