from typing import Optional
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


def to_image_part(image_bytes: bytes, mime_type: Optional[str] = None) -> types.Part:
    """
    Wraps raw image bytes into a Google GenAI types.Part with auto-detected MIME type.
    """
    eff_mime = mime_type or detect_image_mime_type(image_bytes)
    return types.Part.from_bytes(data=image_bytes, mime_type=eff_mime)
