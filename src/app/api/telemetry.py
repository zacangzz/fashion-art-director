import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status, Depends
from pydantic import BaseModel, Field

from app.config import get_settings
from app.auth.firebase_auth import get_current_user
from app.dependencies import get_db_manager
from app.db.database import FirestoreManager
from app.utils.telemetry import (
    query_audit_events,
    get_request_lifecycle_trace,
    get_telemetry_summary_stats,
    get_generation_runs,
)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class TelemetryEventsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    events: List[Dict[str, Any]]


class TelemetryRunsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    runs: List[Dict[str, Any]]


class TelemetryStatsResponse(BaseModel):
    total_events: int
    error_count: int
    success_rate: float
    total_cost_usd: Optional[float] = 0.0
    total_tokens: Optional[int] = 0
    cost_by_component: Optional[Dict[str, float]] = None
    components: Dict[str, int]
    event_types: Dict[str, int]
    average_latencies_ms: Dict[str, float]


class SystemLogsResponse(BaseModel):
    total_lines: int
    logs: List[str]


@router.get("/runs", response_model=TelemetryRunsResponse)
def list_generation_runs(
    component: Optional[str] = Query(None, description="Filter by component"),
    status: Optional[str] = Query(None, description="Filter by status (success, error)"),
    search: Optional[str] = Query(None, description="Search across request ID, prompt, models"),
    limit: int = Query(50, ge=1, le=200, description="Max runs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns grouped end-to-end generation runs with stage events, prompts, latencies, and images.
    """
    try:
        res = get_generation_runs(
            db=db_manager.db,
            component=component,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
        return TelemetryRunsResponse(**res)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load telemetry runs: {exc}",
        )


@router.get("/events", response_model=TelemetryEventsResponse)
def list_telemetry_events(
    component: Optional[str] = Query(None, description="Filter by component (e.g., generation, vision, wardrobe, inpaint, background, api)"),
    event: Optional[str] = Query(None, description="Filter by event name (e.g., fine_tune_request, vision_response)"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
    status: Optional[str] = Query(None, description="Filter by status (success, error, started)"),
    search: Optional[str] = Query(None, description="Text search query across audit records"),
    limit: int = Query(100, ge=1, le=500, description="Max number of events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Queries and filters structured audit events across Firestore telemetry collection.
    """
    try:
        res = query_audit_events(
            db=db_manager.db,
            component=component,
            event=event,
            request_id=request_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
        return TelemetryEventsResponse(**res)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query telemetry events: {exc}",
        )


@router.get("/events/{request_id}", response_model=List[Dict[str, Any]])
def get_request_trace(
    request_id: str,
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Fetches the full chronological lifecycle trace events for a specific request ID.
    """
    try:
        trace = get_request_lifecycle_trace(
            db=db_manager.db,
            request_id=request_id,
        )
        return trace
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load request trace for {request_id}: {exc}",
        )


@router.get("/stats", response_model=TelemetryStatsResponse)
def get_telemetry_stats(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns aggregated metrics and performance telemetry across logged operations.
    """
    try:
        stats_data = get_telemetry_summary_stats(db=db_manager.db)
        return TelemetryStatsResponse(**stats_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute telemetry statistics: {exc}",
        )


@router.get("/logs", response_model=SystemLogsResponse)
def get_system_logs(
    lines: int = Query(200, ge=10, le=1000, description="Number of tail log lines to fetch"),
    level: Optional[str] = Query(None, description="Filter lines containing a specific log level (INFO, WARNING, ERROR)"),
    user: dict = Depends(get_current_user),
):
    """
    Structured stdout logging in Cloud Run / console.
    """
    return SystemLogsResponse(
        total_lines=1,
        logs=["[INFO] Cloud Logging / stdout structured stream active. View Cloud Logging in GCP Console for full stream."],
    )


@router.get("/db/summary")
def get_database_summary(
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns collection metadata and document counts for Firestore collections.
    """
    try:
        summary = db_manager.get_tables_summary()
        return {"tables": summary}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to inspect database summary: {exc}",
        )


@router.get("/db/{table_name}")
def get_database_table_records(
    table_name: str,
    limit: int = Query(50, ge=1, le=200, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: dict = Depends(get_current_user),
    db_manager: FirestoreManager = Depends(get_db_manager),
):
    """
    Returns paginated documents from a specific Firestore collection.
    """
    try:
        data = db_manager.get_table_records(table_name, limit=limit, offset=offset)
        return data
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {exc}",
        )
