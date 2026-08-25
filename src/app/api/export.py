from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.config import get_settings
from app.db.database import DatabaseManager
from app.schemas.domain import ExportBundleRequest
from app.services.export_service import ExportService

router = APIRouter(prefix="/api/export", tags=["export"])

settings = get_settings()
db_manager = DatabaseManager(settings.DATABASE_URL)
export_service = ExportService(db_manager=db_manager)

@router.post("/bundle")
async def export_bundle(request: ExportBundleRequest):
    try:
        zip_bytes = await export_service.create_bundle_zip(request.generation_id)
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
