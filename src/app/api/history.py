from fastapi import APIRouter, HTTPException, status
from app.schemas.domain import (
    HistoryResponse,
    GenerationRecordResponse,
    LineageResponse,
)
from app.dependencies import get_db_manager

router = APIRouter(prefix="/api", tags=["history"])
db_manager = get_db_manager()


def _to_generation_response(r: dict) -> GenerationRecordResponse:
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
        master_image_url=f"/api/images/{r['id']}_master.png",
        aspect_ratio=r.get("aspect_ratio", "2:3"),
        resolution_width=r.get("resolution_width", 1440),
        resolution_height=r.get("resolution_height", 1440),
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """
    Returns full list of generations with lineage metadata and schema snapshots.
    """
    try:
        records = await db_manager.list_generations()
        return HistoryResponse(
            generations=[_to_generation_response(r) for r in records]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(exc)}",
        )


@router.get("/generations/{generation_id}", response_model=GenerationRecordResponse)
async def get_generation(generation_id: str):
    """
    Fetches single generation record by ID.
    """
    rec = await db_manager.get_generation(generation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' not found",
        )
    return _to_generation_response(rec)


@router.get("/generations/{generation_id}/lineage", response_model=LineageResponse)
async def get_generation_lineage(generation_id: str):
    """
    Returns ancestors and direct descendants for a generation.
    """
    lineage = await db_manager.get_lineage(generation_id)
    return LineageResponse(
        root_id=lineage["root_id"],
        ancestors=[_to_generation_response(r) for r in lineage["ancestors"]],
        descendants=[_to_generation_response(r) for r in lineage["descendants"]],
    )


@router.post("/generations/{generation_id}/restore", response_model=GenerationRecordResponse)
async def restore_generation(generation_id: str):
    """
    Returns state for workspace restoration.
    """
    rec = await db_manager.get_generation(generation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{generation_id}' not found",
        )
    return _to_generation_response(rec)
