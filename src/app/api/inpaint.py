from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status

from app.config import get_settings
from app.schemas.domain import InpaintResponse
from app.utils.error_handler import parse_and_raise_http_error
from app.dependencies import get_generation_service

router = APIRouter(prefix="/api", tags=["inpaint"])
settings = get_settings()
generation_service = get_generation_service()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


@router.post("/inpaint", response_model=InpaintResponse)
async def inpaint_image(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
    prompt: str = Form(...),
    generation_id: Optional[str] = Form(None),
    negative_prompt: Optional[str] = Form(None),
    seed: Optional[int] = Form(None),
    aspect_ratio: Optional[str] = Form(None),
):
    """
    Canvas Studio: Targeted inpainting using a source image, black & white mask, and natural language prompt.
    """
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inpaint prompt cannot be empty. Please describe the desired change.",
        )

    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{image.content_type}' for source image. Allowed formats: PNG, JPEG, WebP.",
        )

    if mask.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{mask.content_type}' for mask. Allowed formats: PNG, JPEG, WebP.",
        )

    try:
        image_bytes = await image.read()
        mask_bytes = await mask.read()

        result = await generation_service.inpaint_region(
            parent_id=generation_id or "",
            image_bytes=image_bytes,
            mask_bytes=mask_bytes,
            prompt=prompt.strip(),
            negative_prompt=negative_prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
        )
        return InpaintResponse(**result)
    except Exception as exc:
        parse_and_raise_http_error(exc, model_name=settings.INPAINT_MODEL, context="Canvas Studio Inpainting")
