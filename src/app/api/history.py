from fastapi import APIRouter, HTTPException, status, Depends
from app.auth.firebase_auth import get_current_user
from app.schemas.domain import (
    HistoryResponse,
    GenerationRecordResponse,
    LineageResponse,
)
from app.dependencies import get_db_manager
from app.db.database import FirestoreManager

router = APIRouter(prefix="/api", tags=["history"])


def _to_generation_response(r: dict) -> GenerationRecordResponse:
    master_path = r.get("master_image_path", "")
    return GenerationRecordResponse(
        id=r["id"],
        parent_id=r.get("parent_id"),
        moodboard_id=r.get("moodboard_id"),
        is_baseline=bool(r.get("is_baseline", False)),
        created_at=r.get("created_at", ""),
        schema_json=r.get("schema_json") or {},
        compiled_prompt=r.get("compiled_prompt") or r.get("prompt", ""),
        negative_prompt=r.get("negative_prompt", "") or "",
        seed=r.get("seed", 0),
        master_image_url=f"/api/images/{master_path}" if master_path else f"/api/images/{r['id']}_master.png",
        mask_image_url=r.get("mask_image_url"),
        inpaint_metadata=r.get("inpaint_metadata"),
        aspect_ratio=r.get("aspect_ratio", "1:1"),
        resolution_width=r.get("resolution_width", 3840),
        resolution_height=r.get("resolution_height", 3840),
        model_name=r.get("model_name"),
        cost_usd=float(r.get("cost_usd") or 0.0),
        cost_sgd=float(r.get("cost_sgd") or 0.0),
        exchange_rate=r.get("exchange_rate"),
        tokens=int(r.get("tokens") or 0),
        accumulated_cost_usd=float(r.get("accumulated_cost_usd") or 0.0),
        accumulated_cost_sgd=float(r.get("accumulated_cost_sgd") or 0.0),
        accumulated_tokens=int(r.get("accumulated_tokens") or 0),
    )


@router.get("/history", response_model=HistoryResponse)
def get_history(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns full list of generations with lineage metadata and schema snapshots for authenticated user.
    """
    try:
        records = db_manager.list_generations(user_id=user["uid"])
        return HistoryResponse(
            generations=[_to_generation_response(r) for r in records]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(exc)}",
        )


@router.get("/generations/{generation_id}", response_model=GenerationRecordResponse)
def get_generation(
    generation_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Fetches single generation record by ID.
    """
    rec = db_manager.get_generation(generation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' not found",
        )
    return _to_generation_response(rec)


@router.get("/generations/{generation_id}/lineage", response_model=LineageResponse)
def get_generation_lineage(
    generation_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns ancestors and direct descendants for a generation.
    """
    lineage = db_manager.get_lineage(generation_id)
    return LineageResponse(
        root_id=lineage["root_id"],
        ancestors=[_to_generation_response(r) for r in lineage["ancestors"]],
        descendants=[_to_generation_response(r) for r in lineage["descendants"]],
    )


@router.post("/generations/{generation_id}/restore", response_model=GenerationRecordResponse)
def restore_generation(
    generation_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns state for workspace restoration.
    """
    rec = db_manager.get_generation(generation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' not found",
        )
    return _to_generation_response(rec)
