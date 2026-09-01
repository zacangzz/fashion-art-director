from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import Response

from app.auth.firebase_auth import get_current_user
from app.schemas.domain import ExportBundleRequest, PrepareExportRequest, PrepareExportResponse
from app.dependencies import get_export_service
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/prepare", response_model=PrepareExportResponse)
def prepare_export(
    request: PrepareExportRequest,
    user: dict = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
):
    try:
        result = export_service.prepare_export_master(
            generation_id=request.generation_id,
            prompt_override=request.prompt_override,
            user_id=user["uid"],
        )
        return PrepareExportResponse(**result)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare export master: {str(exc)}",
        )


@router.post("/bundle")
def export_bundle(
    request: ExportBundleRequest,
    user: dict = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
):
    try:
        zip_bytes = export_service.bundle_export_presets(
            generation_id=request.generation_id,
            export_format=request.format or "PNG",
            jpeg_quality=request.jpeg_quality or 95,
            user_id=user["uid"],
        )
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="bundle_{request.generation_id}.zip"'
            },
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
