import io
from typing import Optional
from PIL import Image
from google.genai import types


def detect_image_mime_type(image_bytes: bytes) -> str:
    """
    Detects standard image MIME type based on header magic bytes.
    Defaults to 'image/png'.
    """
    if not image_bytes:
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if image_bytes.startswith(b"RIFF") and b"WEBP" in image_bytes[:16]:
        return "image/webp"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    if image_bytes.startswith(b"%PDF"):
        return "application/pdf"
    return "image/png"


def optimize_reference_image(
    image_bytes: bytes,
    max_dimension: int = 2048,
    target_format: str = "WEBP",
    quality: int = 90,
) -> tuple[bytes, str]:
    """
    Optimizes a conditioning reference image prior to sending over the network to Gemini/Imagen.
    Resizes oversized images (e.g. 4K/8K) to max_dimension keeping aspect ratio,
    and encodes to high-quality WebP, drastically reducing payload size (e.g. 50MB -> 1.5MB)
    while preserving full visual conditioning accuracy for the vision model.
    """
    if not image_bytes:
        return image_bytes, "image/png"

    # Skip optimization for PDFs
    if image_bytes.startswith(b"%PDF"):
        return image_bytes, "application/pdf"

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        orig_w, orig_h = pil_img.size

        # Resize if dimensions exceed max_dimension
        if orig_w > max_dimension or orig_h > max_dimension:
            pil_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Convert palette or RGBA with transparency if saving to JPEG, but WEBP supports RGBA
        if target_format.upper() == "JPEG" and pil_img.mode in ("RGBA", "LA", "P"):
            pil_img = pil_img.convert("RGB")
        elif pil_img.mode not in ("RGB", "RGBA"):
            pil_img = pil_img.convert("RGB")

        buf = io.BytesIO()
        pil_img.save(buf, format=target_format.upper(), quality=quality)
        optimized_bytes = buf.getvalue()

        # If optimized is somehow larger than original, keep original
        if len(optimized_bytes) < len(image_bytes):
            mime = f"image/{target_format.lower()}"
            return optimized_bytes, mime
        else:
            return image_bytes, detect_image_mime_type(image_bytes)
    except Exception:
        # Fallback to original bytes on any PIL processing error
        return image_bytes, detect_image_mime_type(image_bytes)


def to_image_part(
    image_bytes: bytes,
    mime_type: Optional[str] = None,
    optimize: bool = True,
    max_dimension: int = 2048,
) -> types.Part:
    """
    Wraps raw image bytes into a Google GenAI types.Part with auto-detected/optimized MIME type.
    When optimize=True, resizes and compresses conditioning inputs to avoid network timeouts.
    """
    if optimize:
        bytes_to_send, eff_mime = optimize_reference_image(
            image_bytes, max_dimension=max_dimension
        )
    else:
        bytes_to_send = image_bytes
        eff_mime = mime_type or detect_image_mime_type(image_bytes)

    return types.Part.from_bytes(data=bytes_to_send, mime_type=eff_mime)


import base64

VALID_INTERACTION_ASPECT_RATIOS = {
    "1:1",
    "16:9",
    "9:16",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "21:9",
    "1:4",
    "4:1",
    "1:8",
    "8:1",
}

ASPECT_RATIO_INTERACTION_MAP = {
    "1.8:1": "16:9",
    "1.85:1": "16:9",
    "1.78:1": "16:9",
    "2.35:1": "21:9",
    "2.39:1": "21:9",
}


def normalize_interaction_aspect_ratio(aspect_ratio: Optional[str]) -> str:
    """
    Maps application aspect ratios (including cinema ratios like '1.8:1') to valid Google GenAI
    Interactions API aspect ratios ('16:9', '2:3', '1:1', etc.).
    """
    if not aspect_ratio:
        return "16:9"
    ar_clean = str(aspect_ratio).strip().lower()
    if ar_clean in VALID_INTERACTION_ASPECT_RATIOS:
        return ar_clean
    if ar_clean in ASPECT_RATIO_INTERACTION_MAP:
        return ASPECT_RATIO_INTERACTION_MAP[ar_clean]
    # Fallback to closest valid standard
    return "16:9"


def to_interaction_image_input(
    image_bytes: bytes,
    optimize: bool = True,
    max_dimension: int = 2048,
) -> dict:
    """
    Formats image bytes into a dictionary payload for client.interactions.create with base64 data.
    """
    if optimize:
        bytes_to_send, eff_mime = optimize_reference_image(
            image_bytes, max_dimension=max_dimension
        )
    else:
        bytes_to_send = image_bytes
        eff_mime = detect_image_mime_type(image_bytes)

    return {
        "type": "image",
        "data": base64.b64encode(bytes_to_send).decode("utf-8"),
        "mime_type": eff_mime,
    }


