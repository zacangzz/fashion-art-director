import io
import base64
import hashlib
from typing import Optional, Dict, Any, List, Union
from PIL import Image
from google.genai import types

ASPECT_RATIO_RESOLUTIONS: Dict[str, tuple[int, int]] = {
    "1:1": (3840, 3840),
    "16:9": (3840, 2160),
    "9:16": (2160, 3840),
    "21:9": (3840, 1645),
    "2:3": (2560, 3840),
    "3:2": (3840, 2560),
    "4:5": (3072, 3840),
    "5:4": (3840, 3072),
    "3:4": (2880, 3840),
    "4:3": (3840, 2880),
    "1.8:1": (3840, 2133),
    "1.85:1": (3840, 2075),
}

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


def detect_closest_aspect_ratio(width: int, height: int) -> str:
    """
    Calculates image aspect ratio and returns closest supported preset aspect ratio key.
    """
    if not width or not height or height <= 0:
        return "2:3"
    target_ratio = width / height
    ratios = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "21:9": 21 / 9,
        "2:3": 2 / 3,
        "3:2": 3 / 2,
        "4:5": 4 / 5,
        "5:4": 5 / 4,
        "3:4": 3 / 4,
        "4:3": 4 / 3,
        "1.8:1": 1.8,
    }
    return min(ratios.keys(), key=lambda k: abs(ratios[k] - target_ratio))


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
    return "16:9"


def optimize_reference_image(
    image_bytes: bytes,
    max_dimension: int = 2048,
    target_format: str = "WEBP",
    quality: int = 90,
) -> tuple[bytes, str]:
    """
    Optimizes a conditioning reference image prior to network transmission.
    Resizes oversized images to max_dimension and encodes to high-quality WebP.
    """
    if not image_bytes:
        return image_bytes, "image/png"

    if image_bytes.startswith(b"%PDF"):
        return image_bytes, "application/pdf"

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        orig_w, orig_h = pil_img.size

        if orig_w > max_dimension or orig_h > max_dimension:
            pil_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        if target_format.upper() == "JPEG" and pil_img.mode in ("RGBA", "LA", "P"):
            pil_img = pil_img.convert("RGB")
        elif pil_img.mode not in ("RGB", "RGBA"):
            pil_img = pil_img.convert("RGB")

        buf = io.BytesIO()
        pil_img.save(buf, format=target_format.upper(), quality=quality)
        optimized_bytes = buf.getvalue()

        if len(optimized_bytes) < len(image_bytes):
            mime = f"image/{target_format.lower()}"
            return optimized_bytes, mime
        else:
            return image_bytes, detect_image_mime_type(image_bytes)
    except Exception:
        return image_bytes, detect_image_mime_type(image_bytes)


def to_image_part(
    image_bytes: bytes,
    mime_type: Optional[str] = None,
    optimize: bool = True,
    max_dimension: int = 2048,
) -> types.Part:
    """
    Wraps raw image bytes into a Google GenAI types.Part with auto-detected/optimized MIME type.
    """
    if optimize:
        bytes_to_send, eff_mime = optimize_reference_image(
            image_bytes, max_dimension=max_dimension
        )
    else:
        bytes_to_send = image_bytes
        eff_mime = mime_type or detect_image_mime_type(image_bytes)

    return types.Part.from_bytes(data=bytes_to_send, mime_type=eff_mime)


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


def analyze_mask_bytes(mask_bytes: bytes) -> Dict[str, Any]:
    """
    Analyzes mask PNG bytes to compute dimensions, pixel counts, coverage percentage,
    bounding box coordinates, normalized bounding box, centroid, and SHA-256 hash.
    """
    sha256_hash = hashlib.sha256(mask_bytes).hexdigest()
    mask_img = Image.open(io.BytesIO(mask_bytes))
    width, height = mask_img.size
    total_pixels = width * height

    gray_mask = mask_img.convert("L")
    binary_mask = gray_mask.point(lambda p: 255 if p > 127 else 0)
    raw_bbox = binary_mask.getbbox()

    bounding_box = None
    norm_bounding_box = None
    centroid = None
    masked_pixels = 0

    if raw_bbox is not None:
        min_x, min_y, max_x_excl, max_y_excl = raw_bbox
        max_x = max_x_excl - 1
        max_y = max_y_excl - 1

        pixels = list(binary_mask.get_flattened_data()) if hasattr(binary_mask, "get_flattened_data") else list(binary_mask.getdata())
        masked_indices = [i for i, val in enumerate(pixels) if val > 0]
        masked_pixels = len(masked_indices)

        if masked_pixels > 0:
            sum_x = sum(idx % width for idx in masked_indices)
            sum_y = sum(idx // width for idx in masked_indices)

            bounding_box = {
                "min_x": int(min_x),
                "min_y": int(min_y),
                "max_x": int(max_x),
                "max_y": int(max_y),
                "width": int(max_x - min_x + 1),
                "height": int(max_y - min_y + 1),
            }
            norm_bounding_box = {
                "min_x": round(min_x / width, 4),
                "min_y": round(min_y / height, 4),
                "max_x": round(max_x / width, 4),
                "max_y": round(max_y / height, 4),
            }
            centroid = {
                "x": round(sum_x / masked_pixels, 1),
                "y": round(sum_y / masked_pixels, 1),
                "norm_x": round((sum_x / masked_pixels) / width, 4),
                "norm_y": round((sum_y / masked_pixels) / height, 4),
            }

    unmasked_pixels = total_pixels - masked_pixels
    coverage_pct = round((masked_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0

    return {
        "sha256": sha256_hash,
        "bytes": len(mask_bytes),
        "width": width,
        "height": height,
        "total_pixels": total_pixels,
        "masked_pixels": masked_pixels,
        "unmasked_pixels": unmasked_pixels,
        "coverage_percentage": coverage_pct,
        "bounding_box": bounding_box,
        "normalized_bounding_box": norm_bounding_box,
        "centroid": centroid,
    }


def normalize_bounding_box(
    bbox_raw: Any,
    img_w: int,
    img_h: int,
) -> Optional[List[float]]:
    """
    Normalizes any bounding box format into [ymin, xmin, ymax, xmax] floats in [0.0, 1.0].
    Handles 0..1000 integer ranges, absolute pixels, and dictionary structures.
    """
    if not bbox_raw:
        return None

    ymin, xmin, ymax, xmax = 0.0, 0.0, 1.0, 1.0

    if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) >= 4:
        try:
            ymin, xmin, ymax, xmax = [float(c) for c in bbox_raw[:4]]
        except Exception:
            return None
    elif isinstance(bbox_raw, dict):
        try:
            ymin = float(bbox_raw.get("ymin", bbox_raw.get("top", bbox_raw.get("y1", 0.0))))
            xmin = float(bbox_raw.get("xmin", bbox_raw.get("left", bbox_raw.get("x1", 0.0))))
            ymax = float(bbox_raw.get("ymax", bbox_raw.get("bottom", bbox_raw.get("y2", 1.0))))
            xmax = float(bbox_raw.get("xmax", bbox_raw.get("right", bbox_raw.get("x2", 1.0))))
        except Exception:
            return None
    else:
        return None

    max_coord = max(abs(ymin), abs(xmin), abs(ymax), abs(xmax))
    if max_coord > 1.0:
        if max_coord <= 1050.0:
            ymin /= 1000.0
            xmin /= 1000.0
            ymax /= 1000.0
            xmax /= 1000.0
        else:
            ymin /= float(img_h) if img_h > 0 else 1.0
            xmin /= float(img_w) if img_w > 0 else 1.0
            ymax /= float(img_h) if img_h > 0 else 1.0
            xmax /= float(img_w) if img_w > 0 else 1.0

    ymin = max(0.0, min(1.0, ymin))
    xmin = max(0.0, min(1.0, xmin))
    ymax = max(0.0, min(1.0, ymax))
    xmax = max(0.0, min(1.0, xmax))

    return [ymin, xmin, ymax, xmax]


def resize_and_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Resizes and center-crops an image to target dimensions without visual distortion.
    """
    src_width, src_height = image.size
    target_ratio = target_width / target_height
    src_ratio = src_width / src_height

    if src_ratio > target_ratio:
        crop_width = src_height * target_ratio
        crop_height = float(src_height)
        left = (src_width - crop_width) / 2.0
        top = 0.0
        right = left + crop_width
        bottom = crop_height
    elif src_ratio < target_ratio:
        crop_width = float(src_width)
        crop_height = src_width / target_ratio
        left = 0.0
        top = (src_height - crop_height) / 2.0
        right = crop_width
        bottom = top + crop_height
    else:
        left = 0.0
        top = 0.0
        right = float(src_width)
        bottom = float(src_height)

    crop_box = (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )
    cropped_image = image.crop(crop_box)
    return cropped_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
