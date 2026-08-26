import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.utils.telemetry import (
    query_audit_events,
    get_request_lifecycle_trace,
    get_telemetry_summary_stats,
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
settings = get_settings()


class TelemetryEventsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    events: List[Dict[str, Any]]


class TelemetryStatsResponse(BaseModel):
    total_events: int
    error_count: int
    success_rate: float
    components: Dict[str, int]
    event_types: Dict[str, int]
    average_latencies_ms: Dict[str, float]


class SystemLogsResponse(BaseModel):
    total_lines: int
    logs: List[str]


@router.get("/events", response_model=TelemetryEventsResponse)
async def list_telemetry_events(
    component: Optional[str] = Query(None, description="Filter by component (e.g., generation, vision, wardrobe, inpaint, api)"),
    event: Optional[str] = Query(None, description="Filter by event name (e.g., fine_tune_request, vision_response)"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
    status: Optional[str] = Query(None, description="Filter by status (success, error, started)"),
    search: Optional[str] = Query(None, description="Text search query across audit records"),
    limit: int = Query(100, ge=1, le=500, description="Max number of events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Queries and filters structured audit events across all local JSONL logs.
    """
    res = query_audit_events(
        storage_dir=settings.STORAGE_DIR,
        component=component,
        event=event,
        request_id=request_id,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return TelemetryEventsResponse(**res)


@router.get("/events/{request_id}", response_model=List[Dict[str, Any]])
async def get_request_trace(request_id: str):
    """
    Fetches the full chronological lifecycle trace events for a specific request ID.
    """
    trace = get_request_lifecycle_trace(
        request_id=request_id,
        storage_dir=settings.STORAGE_DIR,
    )
    return trace


@router.get("/stats", response_model=TelemetryStatsResponse)
async def get_telemetry_stats():
    """
    Returns aggregated metrics and performance telemetry across logged operations.
    """
    stats = get_telemetry_summary_stats(storage_dir=settings.STORAGE_DIR)
    return TelemetryStatsResponse(**stats)


@router.get("/logs", response_model=SystemLogsResponse)
async def get_system_logs(
    lines: int = Query(200, ge=10, le=1000, description="Number of tail log lines to fetch"),
    level: Optional[str] = Query(None, description="Filter lines containing a specific log level (INFO, WARNING, ERROR)"),
):
    """
    Fetches recent tail lines from the local rotating studio application log.
    """
    log_file = Path(settings.STORAGE_DIR) / "logs" / "studio.log"
    if not log_file.exists():
        return SystemLogsResponse(total_lines=0, logs=[])

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        
        filtered = all_lines
        if level:
            level_str = f"[{level.upper()}]"
            filtered = [ln for ln in all_lines if level_str in ln]

        tail_lines = [ln.rstrip() for ln in filtered[-lines:]]
        return SystemLogsResponse(total_lines=len(tail_lines), logs=tail_lines)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read studio log file: {exc}",
        )


@router.get("/db/summary")
async def get_database_summary():
    """
    Returns table metadata and row counts for the SQLite database.
    """
    from app.dependencies import get_db_manager
    db_manager = get_db_manager()
    summary = await db_manager.get_tables_summary()
    return {"tables": summary}


@router.get("/db/{table_name}")
async def get_database_table_records(
    table_name: str,
    limit: int = Query(50, ge=1, le=200, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Returns paginated rows from a specific database table.
    """
    from app.dependencies import get_db_manager
    db_manager = get_db_manager()
    try:
        data = await db_manager.get_table_records(table_name, limit=limit, offset=offset)
        return data
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {exc}",
        )

