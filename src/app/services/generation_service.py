import os
import io
import uuid
import random
import asyncio
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from PIL import Image
from google import genai
from google.genai import types

from app.db.database import DatabaseManager
from app.schemas.domain import SceneSchema
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger
from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    INPAINT_SYSTEM_PROMPT,
    INPAINT_SUFFIX,
    REFINEMENT_SYSTEM_PROMPT,
    WARDROBE_COMPOSITION_SYSTEM_PROMPT,
)
from app.utils.image_utils import to_image_part


logger = get_logger("generation_service")

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


def detect_closest_aspect_ratio(width: int, height: int) -> str:
    """
    Given natural width and height of an image, calculates the ratio
    and returns the closest supported preset aspect ratio key.
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



def _normalize_categories_dict(cats: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    if not cats or not isinstance(cats, dict):
        return {}
    normalized = {}
    for cat_key, items in cats.items():
        chip_list = []
        if isinstance(items, list):
            for item in items:
                if hasattr(item, "model_dump"):
                    chip_list.append(item.model_dump())
                elif isinstance(item, dict):
                    chip_list.append(item)
                elif isinstance(item, str) and item.strip():
                    chip_list.append({"label": item.strip(), "enabled": True})
        normalized[cat_key] = chip_list
    return normalized


CATEGORY_DISPLAY_NAMES = {
    "subject_details": "Subject & Character Details",
    "wardrobe_hair": "Wardrobe & Hairstyle",
    "objects_props": "Objects & Key Props",
    "environment": "Environment & Setting",
    "layout_framing": "Layout & Framing",
    "camera_optics": "Camera & Optics",
    "lighting": "Lighting & Atmosphere",
    "color_profile": "Color Profile & Palette",
    "mood_era": "Mood, Vibe & Era",
    "custom": "Custom Details",
}


def extract_category_labels(cats: Optional[Dict[str, Any]], cat_key: str) -> List[str]:
    if not cats or not isinstance(cats, dict):
        return []
    items = cats.get(cat_key, [])
    labels = []
    for item in items:
        if isinstance(item, str) and item.strip():
            labels.append(item.strip())
        elif isinstance(item, dict):
            if item.get("enabled", True) is False:
                continue
            lbl = str(item.get("label", "")).strip()
            if lbl:
                labels.append(lbl)
        elif hasattr(item, "label"):
            if getattr(item, "enabled", True) is False:
                continue
            lbl = str(getattr(item, "label", "")).strip()
            if lbl:
                labels.append(lbl)
    return labels


def get_modified_categories(
    current_categories: Optional[Dict[str, Any]] = None,
    baseline_categories: Optional[Dict[str, Any]] = None,
    current_narrative: Optional[str] = None,
    baseline_narrative: Optional[str] = None,
) -> Dict[str, Any]:
    curr = current_categories or {}
    base = baseline_categories or {}
    modified = {}
    all_keys = set(curr.keys()).union(set(base.keys()))
    for key in all_keys:
        curr_labels = extract_category_labels(curr, key)
        base_labels = extract_category_labels(base, key)
        if curr_labels != base_labels:
            modified[key] = True

    curr_narrative_clean = (current_narrative or "").strip()
    base_narrative_clean = (baseline_narrative or "").strip()
    narrative_modified = curr_narrative_clean != base_narrative_clean

    return {
        "categories": modified,
        "narrative": narrative_modified,
        "has_changes": narrative_modified or bool(modified),
    }


def compile_prompt(
    narrative: Optional[str] = None,
    categories: Optional[Dict[str, Any]] = None,
    custom_tags: Optional[List[str]] = None,
    prompt_override: Optional[str] = None,
) -> str:
    """
    Compiles a highly reproducible, structured modular narrative prompt
    from the 9-category tag system.
    """
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    sections = []
    if narrative and narrative.strip():
        sections.append(narrative.strip())

    cats = categories or {}

    subject_labels = extract_category_labels(cats, "subject_details")
    wardrobe_labels = extract_category_labels(cats, "wardrobe_hair")
    object_labels = extract_category_labels(cats, "objects_props")
    env_labels = extract_category_labels(cats, "environment")
    framing_labels = extract_category_labels(cats, "layout_framing")
    camera_labels = extract_category_labels(cats, "camera_optics")
    lighting_labels = extract_category_labels(cats, "lighting")
    color_labels = extract_category_labels(cats, "color_profile")
    mood_labels = extract_category_labels(cats, "mood_era")
    custom_labels = [c.strip() for c in (custom_tags or []) if c and c.strip()]
    custom_cat_labels = extract_category_labels(cats, "custom")
    all_custom = custom_labels + custom_cat_labels

    if subject_labels or wardrobe_labels:
        parts = []
        if subject_labels:
            parts.append(", ".join(subject_labels))
        if wardrobe_labels:
            parts.append(f"wearing {', '.join(wardrobe_labels)}")
        sections.append(f"Subject: {', '.join(parts)}.")

    if env_labels or object_labels:
        parts = []
        if env_labels:
            parts.append(f"set in {', '.join(env_labels)}")
        if object_labels:
            parts.append(f"featuring {', '.join(object_labels)}")
        sections.append(f"Environment: {', '.join(parts)}.")

    if framing_labels or camera_labels:
        parts = []
        if framing_labels:
            parts.append(", ".join(framing_labels))
        if camera_labels:
            parts.append(f"shot on {', '.join(camera_labels)}")
        sections.append(f"Composition: {', '.join(parts)}.")

    if lighting_labels or color_labels:
        parts = []
        if lighting_labels:
            parts.append(f"illuminated with {', '.join(lighting_labels)}")
        if color_labels:
            parts.append(f"color palette of {', '.join(color_labels)}")
        sections.append(f"Lighting & Color: {', '.join(parts)}.")

    if mood_labels:
        sections.append(f"Aesthetic: {', '.join(mood_labels)}.")

    if all_custom:
        sections.append(f"Details: {', '.join(all_custom)}.")

    compiled = " ".join(sections).strip()
    return compiled or (narrative.strip() if narrative else "A high-fashion cinematic scene with exquisite detail.")


def compile_delta_prompt(
    narrative: Optional[str] = None,
    categories: Optional[Dict[str, Any]] = None,
    baseline_narrative: Optional[str] = None,
    baseline_categories: Optional[Dict[str, Any]] = None,
    locked_categories: Optional[List[str]] = None,
    custom_tags: Optional[List[str]] = None,
    prompt_override: Optional[str] = None,
) -> str:
    """
    Compiles an Image-to-Image Delta Prompt when fine-tuning from a baseline image reference.
    Strictly preserves the base image's subject identity, composition, pose, and background
    while directing targeted adjustments only to edited tags.
    """
    if prompt_override and prompt_override.strip():
        return prompt_override.strip()

    if not baseline_categories or not isinstance(baseline_categories, dict):
        return compile_prompt(
            narrative=narrative,
            categories=categories,
            custom_tags=custom_tags,
            prompt_override=prompt_override,
        )

    cats = categories or {}
    diff = get_modified_categories(
        current_categories=cats,
        baseline_categories=baseline_categories,
        current_narrative=narrative,
        baseline_narrative=baseline_narrative,
    )

    if not diff["has_changes"]:
        return (
            "Visual Continuity: Faithfully preserve the character identity, pose, framing, and environment "
            "from the input reference image while subtly refining overall render fidelity and atmospheric coherence."
        )

    sections = [
        "Visual Reference Foundation: Use the reference image as the structural, character, and stylistic anchor. "
        "Maintain raw photo fidelity, 1:1 original source sharpness, visible skin pores, natural skin texture, stray hairs, minor skin blemishes, fine film grain, natural light, and natural micro-contrast. "
        "Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—including lighting falloff, cast shadows, color bounce, material reactions, and environmental reflections—to adjust organically for realistic visual cohesion without waxy smoothing, artificial plastic finish, or compression degradation."
    ]

    adjustments = []
    if diff["narrative"] and narrative and narrative.strip():
        adjustments.append(f"Scene Direction: {narrative.strip()}")

    if diff["categories"].get("subject_details"):
        lbls = extract_category_labels(cats, "subject_details")
        if lbls:
            adjustments.append(f"Subject Details: {', '.join(lbls)}")

    if diff["categories"].get("wardrobe_hair"):
        lbls = extract_category_labels(cats, "wardrobe_hair")
        if lbls:
            adjustments.append(f"Wardrobe & Hairstyle: wearing {', '.join(lbls)}")

    if diff["categories"].get("objects_props"):
        lbls = extract_category_labels(cats, "objects_props")
        if lbls:
            adjustments.append(f"Objects & Props: featuring {', '.join(lbls)}")

    if diff["categories"].get("environment"):
        lbls = extract_category_labels(cats, "environment")
        if lbls:
            adjustments.append(f"Environment: set in {', '.join(lbls)}")

    if diff["categories"].get("layout_framing"):
        lbls = extract_category_labels(cats, "layout_framing")
        if lbls:
            adjustments.append(f"Framing & Layout: {', '.join(lbls)}")

    if diff["categories"].get("lighting"):
        lbls = extract_category_labels(cats, "lighting")
        if lbls:
            adjustments.append(f"Lighting: illuminated with {', '.join(lbls)}")

    if diff["categories"].get("color_profile"):
        lbls = extract_category_labels(cats, "color_profile")
        if lbls:
            adjustments.append(f"Color Profile: palette of {', '.join(lbls)}")

    if diff["categories"].get("camera_optics"):
        lbls = extract_category_labels(cats, "camera_optics")
        if lbls:
            adjustments.append(f"Camera & Optics: shot on {', '.join(lbls)}")

    if diff["categories"].get("mood_era"):
        lbls = extract_category_labels(cats, "mood_era")
        if lbls:
            adjustments.append(f"Aesthetic & Mood: {', '.join(lbls)}")

    if diff["categories"].get("custom"):
        lbls = extract_category_labels(cats, "custom")
        if lbls:
            adjustments.append(f"Custom Details: {', '.join(lbls)}")

    if adjustments:
        sections.append(f"Requested Modifications: {'. '.join(adjustments)}.")

    all_known_categories = [
        "subject_details",
        "wardrobe_hair",
        "objects_props",
        "environment",
        "layout_framing",
        "camera_optics",
        "lighting",
        "color_profile",
        "mood_era",
    ]
    locked_set = set(locked_categories or [])
    preserved_categories = [
        CATEGORY_DISPLAY_NAMES.get(k, k)
        for k in all_known_categories
        if k in locked_set
    ]

    if preserved_categories:
        sections.append(
            f"Consistent Anchors: Maintain the core design, identity, and styling of {', '.join(preserved_categories)}, while allowing them to interact realistically with the updated scene conditions."
        )

    return " ".join(sections).strip()


def analyze_mask_bytes(mask_bytes: bytes) -> Dict[str, Any]:
    """
    Analyzes mask PNG bytes to compute dimensions, pixel counts, coverage percentage,
    bounding box coordinates, normalized bounding box, centroid, and SHA-256 hash.
    """
    sha256_hash = hashlib.sha256(mask_bytes).hexdigest()
    mask_img = Image.open(io.BytesIO(mask_bytes))
    width, height = mask_img.size
    total_pixels = width * height

    # Convert to binary mask for fast bbox & pixel analysis
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


class GenerationService:
    def __init__(
        self,
        db_manager: DatabaseManager,
        api_key: str,
        storage_dir: str = "./storage",
        model_name: str = "gemini-3-pro-image",
        inpaint_model_name: str = "gemini-3-pro-image",
        audit_path: Optional[Path] = None,
        wardrobe_service: Optional[Any] = None,
        client: Optional[genai.Client] = None,
    ):
        self.db = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir
        self.model_name = model_name
        self.inpaint_model_name = inpaint_model_name
        self.client = client or genai.Client(api_key=self.api_key)
        self.audit_path = Path(audit_path or os.path.join(storage_dir, "logs", "generation_audit.jsonl"))
        self._wardrobe_service = wardrobe_service
        self.telemetry = TelemetryLogger(
            audit_path=self.audit_path,
            component="generation",
            storage_dir=self.storage_dir,
        )

    @property
    def wardrobe_service(self):
        if self._wardrobe_service is None:
            from app.services.wardrobe_service import WardrobeService
            self._wardrobe_service = WardrobeService(
                db_manager=self.db,
                api_key=self.api_key,
                storage_dir=self.storage_dir,
            )
        return self._wardrobe_service

    def _audit(self, event: str, request_id: str, **details: Any) -> None:
        try:
            self.telemetry.record_event(
                event=event,
                request_id=request_id,
                component="generation",
                **details,
            )
        except Exception as audit_err:
            logger.warning(f"Could not write generation audit event: {audit_err}")

    def _process_and_save_image(
        self,
        image_bytes: bytes,
        filepath: str,
        aspect_ratio: str,
    ) -> tuple[int, int]:
        """
        Ensures consistent 4K master output resolution across all generation endpoints.
        Scales up using Lanczos resampling if needed, embeds 600 DPI, and saves as PNG.
        """
        target_res = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (3840, 3840))
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGB")
            curr_w, curr_h = pil_img.size
            if curr_w < target_res[0] or curr_h < target_res[1]:
                logger.info(f"Upscaling generated image from {curr_w}x{curr_h} to 4K target {target_res[0]}x{target_res[1]}")
                pil_img = pil_img.resize(target_res, Image.Resampling.LANCZOS)
            pil_img.save(filepath, format="PNG", dpi=(600, 600))
            return pil_img.size
        except Exception as err:
            logger.warning(f"Error processing 4K image with PIL, saving raw bytes: {err}")
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            return target_res

    async def _call_image_model(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        aspect_ratio: str = "2:3",
        reference_image_bytes: Optional[bytes] = None,
        audit_request_id: Optional[str] = None,
        reference_image_path: Optional[str] = None,
    ) -> bytes:
        """
        Invokes Gemini or Imagen model to generate image bytes.
        """
        logger.info(f"Calling image model '{self.model_name}' (seed={seed}, aspect={aspect_ratio}, has_reference={bool(reference_image_bytes)})")

        started = time.perf_counter()
        if "imagen" in self.model_name.lower():
            config = types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
                aspect_ratio=aspect_ratio if aspect_ratio in ["1:1", "3:4", "4:3", "9:16", "16:9"] else "1:1",
                negative_prompt=negative_prompt if negative_prompt else None,
            )
            if audit_request_id:
                self._audit("image_model_request", audit_request_id, final_prompt=prompt, config={
                    "model": self.model_name, "seed": seed, "aspect_ratio": aspect_ratio,
                    "negative_prompt": negative_prompt,
                }, reference_image=None)
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_images,
                    model=self.model_name,
                    prompt=prompt,
                    config=config,
                )
            except Exception as model_err:
                if audit_request_id:
                    self._audit("image_model_error", audit_request_id, error=repr(model_err))
                raise
            if response.generated_images:
                image_bytes = response.generated_images[0].image.image_bytes
                logger.info(f"Received image bytes from Imagen model ({len(image_bytes)} bytes)")
                if audit_request_id:
                    self._audit("image_model_response", audit_request_id,
                        response_metadata=response.model_dump() if callable(getattr(response, "model_dump", None)) else None,
                        output={"sha256": hashlib.sha256(image_bytes).hexdigest(), "bytes": len(image_bytes)},
                        duration_ms=round((time.perf_counter() - started) * 1000, 1))
                return image_bytes
        else:
            # Modern multimodal generation call (e.g. gemini-3.1-flash-lite-image)
            contents = []
            if reference_image_bytes:
                contents.append(to_image_part(reference_image_bytes))

            res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "2:3", (2560, 3840))
            res_str = f"{res_tuple[0]}x{res_tuple[1]}"
            suffix = IMAGE_GENERATION_SUFFIX.format(
                RESOLUTION=res_str,
                ASPECT_RATIO=aspect_ratio or "unspecified",
                SEED=seed if seed is not None else "unspecified",
                NEGATIVE_PROMPT=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
            )
            full_prompt = f"{prompt.rstrip()} {suffix.strip()}"

            if audit_request_id:
                reference = None
                if reference_image_bytes is not None:
                    reference = {
                        "path": reference_image_path,
                        "sha256": hashlib.sha256(reference_image_bytes).hexdigest(),
                        "bytes": len(reference_image_bytes),
                    }
                self._audit("image_model_request", audit_request_id,
                    final_prompt=full_prompt,
                    config={"model": self.model_name, "seed": seed, "aspect_ratio": aspect_ratio,
                            "resolution": res_str, "negative_prompt": negative_prompt},
                    reference_image=reference)

            contents.append(full_prompt)

            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=contents,
                )
            except Exception as model_err:
                if audit_request_id:
                    self._audit("image_model_error", audit_request_id, error=repr(model_err))
                raise

            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        logger.info(f"Received inline image bytes from Gemini model ({len(part.inline_data.data)} bytes)")
                        if audit_request_id:
                            self._audit("image_model_response", audit_request_id,
                                response_metadata=response.model_dump() if callable(getattr(response, "model_dump", None)) else None,
                                output={"sha256": hashlib.sha256(part.inline_data.data).hexdigest(), "bytes": len(part.inline_data.data)},
                                duration_ms=round((time.perf_counter() - started) * 1000, 1))
                        return part.inline_data.data

        raise RuntimeError(f"No image bytes returned from Google GenAI API for model {self.model_name}.")

    async def _call_multi_image_model(
        self,
        contents: List[Any],
        seed: Optional[int] = None,
        aspect_ratio: str = "2:3",
        negative_prompt: str = "",
        audit_request_id: Optional[str] = None,
    ) -> bytes:
        """
        Invokes Gemini multimodal generation with multiple image parts + structured text.
        """
        logger.info(f"Calling multi-image model '{self.model_name}' (seed={seed}, aspect={aspect_ratio}, parts_count={len(contents)})")
        started = time.perf_counter()

        res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "2:3", (2560, 3840))
        res_str = f"{res_tuple[0]}x{res_tuple[1]}"
        suffix = IMAGE_GENERATION_SUFFIX.format(
            RESOLUTION=res_str,
            ASPECT_RATIO=aspect_ratio or "unspecified",
            SEED=seed if seed is not None else "unspecified",
            NEGATIVE_PROMPT=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        )
        contents.append(suffix.strip())

        if audit_request_id:
            self._audit("multi_image_model_request", audit_request_id,
                parts_count=len(contents),
                config={"model": self.model_name, "seed": seed, "aspect_ratio": aspect_ratio,
                        "negative_prompt": negative_prompt})

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
            )
        except Exception as model_err:
            if audit_request_id:
                self._audit("multi_image_model_error", audit_request_id, error=repr(model_err))
            raise

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    logger.info(f"Received inline image bytes from Gemini multi-image model ({len(part.inline_data.data)} bytes)")
                    if audit_request_id:
                        self._audit("multi_image_model_response", audit_request_id,
                            response_metadata=response.model_dump() if callable(getattr(response, "model_dump", None)) else None,
                            output={"sha256": hashlib.sha256(part.inline_data.data).hexdigest(), "bytes": len(part.inline_data.data)},
                            duration_ms=round((time.perf_counter() - started) * 1000, 1))
                    return part.inline_data.data

        raise RuntimeError(f"No image bytes returned from Google GenAI API for model {self.model_name}.")

    async def generate_single_baseline(
        self,
        moodboard_id: str,
        state_dict: Dict[str, Any],
        positive_prompt: str,
        negative_prompt: str,
        seed: int,
        aspect_ratio: str = "2:3",
    ) -> Dict[str, Any]:
        """
        Generates and saves a single baseline image.
        """
        gen_id = f"gen_base_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        req_id = f"baseline_single_{uuid.uuid4().hex[:10]}"
        logger.info(f"Generating baseline candidate {gen_id} (seed={seed})...")

        started = time.perf_counter()
        self._audit(
            "baseline_single_request",
            req_id,
            moodboard_id=moodboard_id,
            seed=seed,
            aspect_ratio=aspect_ratio,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            model=self.model_name,
        )

        try:
            image_bytes = await self._call_image_model(
                prompt=positive_prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                aspect_ratio=aspect_ratio,
                audit_request_id=req_id,
            )
        except Exception as err:
            self._audit(
                "baseline_single_error",
                req_id,
                moodboard_id=moodboard_id,
                seed=seed,
                error=str(err),
            )
            raise

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{gen_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        width, height = self._process_and_save_image(image_bytes, filepath, aspect_ratio)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)

        res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "2:3", (2560, 3840))
        res_str = f"{res_tuple[0]}x{res_tuple[1]}"
        suffix_str = IMAGE_GENERATION_SUFFIX.format(
            RESOLUTION=res_str,
            ASPECT_RATIO=aspect_ratio or "unspecified",
            SEED=seed if seed is not None else "unspecified",
            NEGATIVE_PROMPT=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        )
        full_baseline_prompt = f"{positive_prompt.rstrip()} {suffix_str.strip()}"

        record = {
            "id": gen_id,
            "parent_id": None,
            "moodboard_id": moodboard_id,
            "is_baseline": True,
            "created_at": created_at,
            "schema_json": state_dict,
            "compiled_prompt": full_baseline_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
        }
        await self.db.create_generation(record)
        self._audit(
            "baseline_single_response",
            req_id,
            generation_id=gen_id,
            moodboard_id=moodboard_id,
            seed=seed,
            duration_ms=duration_ms,
            output={"sha256": hashlib.sha256(image_bytes).hexdigest(), "bytes": len(image_bytes), "filename": filename},
        )
        logger.info(f"Saved baseline record {gen_id} to database and disk at {filepath}")

        return {
            "id": gen_id,
            "seed": seed,
            "image_url": f"/api/images/{filename}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "compiled_prompt": full_baseline_prompt,
        }

    async def register_uploaded_photo(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        custom_aspect_ratio: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Registers an uploaded user photo as a baseline generation record,
        allowing the user to skip art direction and immediately proceed to refinement.
        """
        gen_id = f"gen_upload_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        req_id = f"direct_upload_{uuid.uuid4().hex[:10]}"
        seed = random.randint(1000000, 9999999)

        # Open image to inspect dimensions
        pil_img = Image.open(io.BytesIO(image_bytes))
        if pil_img.mode not in ("RGB", "RGBA"):
            pil_img = pil_img.convert("RGB")
        orig_w, orig_h = pil_img.size

        # Determine aspect ratio: use custom if valid, otherwise detect closest
        if custom_aspect_ratio and custom_aspect_ratio in ASPECT_RATIO_RESOLUTIONS:
            eff_aspect_ratio = custom_aspect_ratio
        else:
            eff_aspect_ratio = detect_closest_aspect_ratio(orig_w, orig_h)

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        saved_filename = f"{gen_id}_master.png"
        filepath = os.path.join(gen_dir, saved_filename)

        # Save image as PNG (with DPI metadata)
        pil_img.save(filepath, format="PNG", dpi=(600, 600))
        final_w, final_h = pil_img.size

        compiled_prompt = "Uploaded Reference Image"
        negative_prompt = DEFAULT_NEGATIVE_PROMPT

        record = {
            "id": gen_id,
            "parent_id": None,
            "moodboard_id": None,
            "is_baseline": True,
            "created_at": created_at,
            "schema_json": {
                "source": "direct_upload",
                "original_filename": filename,
                "detected_aspect_ratio": eff_aspect_ratio,
            },
            "compiled_prompt": compiled_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": eff_aspect_ratio,
            "resolution_width": final_w,
            "resolution_height": final_h,
        }
        await self.db.create_generation(record)

        self._audit(
            "direct_photo_upload",
            req_id,
            generation_id=gen_id,
            seed=seed,
            aspect_ratio=eff_aspect_ratio,
            resolution={"width": final_w, "height": final_h},
            original_filename=filename,
            bytes=len(image_bytes),
        )

        logger.info(f"Registered uploaded photo as baseline {gen_id} ({final_w}x{final_h}, aspect={eff_aspect_ratio}) at {filepath}")

        return {
            "generation_id": gen_id,
            "image_url": f"/api/images/{saved_filename}",
            "seed": seed,
            "aspect_ratio": eff_aspect_ratio,
            "resolution": {"width": final_w, "height": final_h},
            "compiled_prompt": compiled_prompt,
            "created_at": created_at,
        }

    async def generate_4_baselines(
        self,
        moodboard_id: str,
        state: Union[Dict[str, Any], SceneSchema],
        aspect_ratio: str = "2:3",
        prompt_override: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Spawns 4 concurrent baseline generation tasks across 4 unique seeds.
        Uses the Vision Director's master_prompt directly (or prompt_override),
        only appending the technical quality suffix.
        """
        state_dict = state.model_dump() if isinstance(state, SceneSchema) else (state or {})
        narrative = state_dict.get("narrative", "")
        categories = state_dict.get("categories", {})
        master_prompt = state_dict.get("master_prompt", "")

        if prompt_override and prompt_override.strip():
            compiled_prompt = prompt_override.strip()
        elif master_prompt and str(master_prompt).strip():
            compiled_prompt = str(master_prompt).strip()
        else:
            compiled_prompt = compile_prompt(narrative=narrative, categories=categories)

        neg_prompt = DEFAULT_NEGATIVE_PROMPT

        # Generate 4 distinct seeds
        seeds = random.sample(range(100000, 9999999), 4)
        req_id = f"baseline_batch_{uuid.uuid4().hex[:10]}"
        logger.info(f"Spawning 4 concurrent baseline tasks for moodboard '{moodboard_id}' across seeds: {seeds}")

        started = time.perf_counter()
        self._audit(
            "baseline_batch_request",
            req_id,
            moodboard_id=moodboard_id,
            seeds=seeds,
            aspect_ratio=aspect_ratio,
            compiled_prompt=compiled_prompt,
            categories_count={k: len(v) if isinstance(v, list) else 0 for k, v in categories.items()} if isinstance(categories, dict) else {},
            model=self.model_name,
        )

        tasks = [
            self.generate_single_baseline(
                moodboard_id=moodboard_id,
                state_dict=state_dict,
                positive_prompt=compiled_prompt,
                negative_prompt=neg_prompt,
                seed=seed,
                aspect_ratio=aspect_ratio,
            )
            for seed in seeds
        ]

        try:
            results = await asyncio.gather(*tasks)
        except Exception as err:
            self._audit(
                "baseline_batch_error",
                req_id,
                moodboard_id=moodboard_id,
                seeds=seeds,
                error=str(err),
            )
            raise

        batch_duration_ms = round((time.perf_counter() - started) * 1000, 1)
        self._audit(
            "baseline_batch_response",
            req_id,
            moodboard_id=moodboard_id,
            seeds=seeds,
            generation_ids=[r["id"] for r in results],
            duration_ms=batch_duration_ms,
        )
        logger.info(f"Successfully generated all 4 baseline candidates for moodboard '{moodboard_id}' in {batch_duration_ms}ms")
        return list(results)

    async def fine_tune_generation(
        self,
        parent_id: str,
        state: Optional[Union[Dict[str, Any], SceneSchema]] = None,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        baseline_narrative: Optional[str] = None,
        baseline_categories: Optional[Dict[str, Any]] = None,
        locked_categories: Optional[List[str]] = None,
        prompt_override: Optional[str] = None,
        seed: int = 4289102,
        use_image_reference: bool = True,
        aspect_ratio: str = "2:3",
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-generates with seed locking and parent baseline image conditioning using the Prompt Compiler.
        """
        logger.info(f"Fine-tuning generation from parent '{parent_id}' with locked seed #{seed} (use_image_reference={use_image_reference})")

        state_dict = {}
        if state is not None:
            state_dict = state.model_dump() if isinstance(state, SceneSchema) else state

        eff_narrative = narrative if narrative is not None else state_dict.get("narrative", "")
        raw_categories = categories if categories is not None else state_dict.get("categories", {})
        eff_categories = _normalize_categories_dict(raw_categories)

        parent_record = await self.db.get_generation(parent_id) if parent_id else None
        moodboard_id = parent_record.get("moodboard_id") if parent_record else None

        # Resolve baseline state from arguments or fallback to parent record snapshot
        eff_base_narrative = baseline_narrative
        eff_base_categories = _normalize_categories_dict(baseline_categories) if baseline_categories else None
        if eff_base_categories is None and parent_record and isinstance(parent_record.get("schema_json"), dict):
            parent_schema = parent_record["schema_json"]
            if eff_base_narrative is None:
                eff_base_narrative = parent_schema.get("narrative", "")
            eff_base_categories = _normalize_categories_dict(parent_schema.get("categories", {}))

        # Compile delta prompt if referencing baseline image, else full modular scene
        if use_image_reference and eff_base_categories is not None:
            compiled_prompt = compile_delta_prompt(
                narrative=eff_narrative,
                categories=eff_categories,
                baseline_narrative=eff_base_narrative or "",
                baseline_categories=eff_base_categories,
                locked_categories=locked_categories,
                prompt_override=prompt_override,
            )
        else:
            compiled_prompt = compile_prompt(
                narrative=eff_narrative,
                categories=eff_categories,
                prompt_override=prompt_override,
            )

        final_neg_prompt = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT
        request_id = f"fine_tune_{uuid.uuid4().hex}"
        self._audit("fine_tune_request", request_id,
            parent_id=parent_id, narrative=eff_narrative, compiled_prompt=compiled_prompt,
            seed=seed, use_image_reference=use_image_reference,
            aspect_ratio=aspect_ratio, negative_prompt=final_neg_prompt,
            model=self.model_name)

        parent_bytes = None
        if use_image_reference and parent_record and parent_record.get("master_image_path"):
            if os.path.exists(parent_record["master_image_path"]):
                logger.info(f"Loading parent baseline image conditioning from: {parent_record['master_image_path']}")
                with open(parent_record["master_image_path"], "rb") as f:
                    parent_bytes = f.read()
            else:
                logger.warning(f"Parent image path '{parent_record.get('master_image_path')}' not found on disk. Proceeding without reference bytes.")

        child_id = f"gen_iter_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        image_bytes = await self._call_image_model(
            prompt=compiled_prompt,
            negative_prompt=final_neg_prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            reference_image_bytes=parent_bytes,
            audit_request_id=request_id,
            reference_image_path=parent_record.get("master_image_path") if parent_bytes and parent_record else None,
        )


        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{child_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        width, height = self._process_and_save_image(image_bytes, filepath, aspect_ratio)

        record_state = {
            "narrative": eff_narrative,
            "categories": eff_categories,
        }

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": record_state,
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
        }
        await self.db.create_generation(record)
        self._audit("fine_tune_response", request_id,
            generation_id=child_id, parent_id=parent_id,
            output_path=filepath, compiled_prompt=compiled_prompt,
            seed=seed, aspect_ratio=aspect_ratio, negative_prompt=final_neg_prompt)
        logger.info(f"Fine-tuned iteration {child_id} created successfully.")

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": seed,
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "image_url": f"/api/images/{filename}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
        }

    async def refine_generation(
        self,
        parent_id: str,
        prompt: str,
        seed: int = 4289102,
        aspect_ratio: str = "2:3",
        negative_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Conversation-based refinement: sends reference image + free-text instruction
        to the image model with seed locking. Each result is linked to a conversation thread.
        """
        logger.info(f"Refinement generation from parent '{parent_id}' with seed #{seed} (conversation={conversation_id})")

        parent_record = await self.db.get_generation(parent_id) if parent_id else None
        moodboard_id = parent_record.get("moodboard_id") if parent_record else None

        # Wrap user prompt with refinement system prompt
        compiled_prompt = REFINEMENT_SYSTEM_PROMPT.replace("{USER_PROMPT}", prompt.strip())

        final_neg_prompt = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT
        request_id = f"refine_{uuid.uuid4().hex}"
        self._audit("refinement_request", request_id,
            parent_id=parent_id, user_prompt=prompt, compiled_prompt=compiled_prompt,
            seed=seed, aspect_ratio=aspect_ratio, negative_prompt=final_neg_prompt,
            conversation_id=conversation_id, model=self.model_name)

        # Load parent image for reference conditioning
        parent_bytes = None
        if parent_record and parent_record.get("master_image_path"):
            img_path = parent_record["master_image_path"]
            if os.path.exists(img_path):
                logger.info(f"Loading reference image from: {img_path}")
                with open(img_path, "rb") as f:
                    parent_bytes = f.read()
            else:
                logger.warning(f"Reference image '{img_path}' not found on disk.")

        child_id = f"gen_refine_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        image_bytes = await self._call_image_model(
            prompt=compiled_prompt,
            negative_prompt=final_neg_prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            reference_image_bytes=parent_bytes,
            audit_request_id=request_id,
            reference_image_path=parent_record.get("master_image_path") if parent_bytes and parent_record else None,
        )

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{child_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        width, height = self._process_and_save_image(image_bytes, filepath, aspect_ratio)

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": {"refinement_prompt": prompt, "conversation_id": conversation_id},
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "conversation_id": conversation_id,
        }
        await self.db.create_generation(record)
        self._audit("refinement_response", request_id,
            generation_id=child_id, parent_id=parent_id,
            output_path=filepath, compiled_prompt=compiled_prompt,
            seed=seed, aspect_ratio=aspect_ratio, conversation_id=conversation_id)
        logger.info(f"Refinement {child_id} created successfully.")

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": seed,
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "image_url": f"/api/images/{filename}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "conversation_id": conversation_id,
        }

    async def compose_wardrobe(
        self,
        parent_id: str,
        assignments: List[Dict[str, Any]],
        seed: int = 4289102,
        aspect_ratio: str = "2:3",
        negative_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        custom_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Multi-image wardrobe composition: sends base reference image + 1 or more garment reference images
        with numbered pin directives to Gemini.
        """
        logger.info(f"Composing wardrobe from parent '{parent_id}' with {len(assignments)} garment assignments (seed={seed}, conv={conversation_id})")

        parent_record = await self.db.get_generation(parent_id) if parent_id else None
        moodboard_id = parent_record.get("moodboard_id") if parent_record else None

        if not parent_record or not parent_record.get("master_image_path") or not os.path.exists(parent_record["master_image_path"]):
            raise ValueError(f"Parent generation '{parent_id}' or its master image file does not exist.")

        # Load parent image
        parent_img_path = parent_record["master_image_path"]
        with open(parent_img_path, "rb") as f:
            parent_bytes = f.read()

        contents: List[Any] = [
            to_image_part(parent_bytes),
            "Primary Base Scene Image above (showing the current model/subject)."
        ]

        # 1. Gather all garment items and prepared metadata
        assignments_for_grounding = []
        loaded_items_temp = []

        for asgn_raw in assignments:
            assignment = asgn_raw.model_dump() if hasattr(asgn_raw, "model_dump") else (asgn_raw if isinstance(asgn_raw, dict) else {})
            item_id = assignment.get("wardrobe_item_id")
            pin_num = assignment.get("pin_number", 1)
            drop_pos = assignment.get("drop_position") or {}
            target_desc = assignment.get("target_description") or ""

            wardrobe_item = await self.db.get_wardrobe_item(item_id)
            if not wardrobe_item:
                logger.warning(f"Wardrobe item '{item_id}' not found in DB.")
                continue

            crop_path = wardrobe_item.get("cropped_image_path")
            if not crop_path or not os.path.exists(crop_path):
                logger.warning(f"Cropped image '{crop_path}' not found on disk.")
                continue

            with open(crop_path, "rb") as f:
                garment_bytes = f.read()

            label = wardrobe_item.get("label", f"Garment {pin_num}")
            category = wardrobe_item.get("category", "tops")

            loaded_items_temp.append({
                "pin_number": pin_num,
                "item_id": item_id,
                "label": label,
                "category": category,
                "drop_pos": drop_pos,
                "target_desc": target_desc,
                "garment_bytes": garment_bytes,
                "region_bbox": assignment.get("region_bbox"),
            })
            assignments_for_grounding.append({
                "pin_number": pin_num,
                "item_label": label,
                "category": category,
                "drop_position": drop_pos,
                "target_description": target_desc,
            })

        # 2. Execute Vision-Assisted Subject Grounding (Pre-pass)
        grounding_data = await self.wardrobe_service.ground_wardrobe_pins(
            image_bytes=parent_bytes,
            assignments=assignments_for_grounding,
        )
        grounded_by_pin = {
            g.get("pin_number"): g for g in grounding_data.get("grounded_pins", []) if isinstance(g, dict)
        }

        # 3. Build replacement instructions with grounded subject descriptions
        instruction_lines = []
        loaded_assignments = []

        for item in loaded_items_temp:
            pin_num = item["pin_number"]
            g_info = grounded_by_pin.get(pin_num, {})
            target_subject = g_info.get("target_subject") or "The target subject at this location"
            body_loc = g_info.get("body_location") or "the corresponding body area"
            spatial_anchor = g_info.get("spatial_anchor") or f"drop pin (x: {round(float(item['drop_pos'].get('x', 0.5))*100)}%, y: {round(float(item['drop_pos'].get('y', 0.5))*100)}%)"
            current_attire = g_info.get("current_attire") or "the existing clothing"

            instruction_lines.append(
                f"- [Garment Pin #{pin_num}] \"{item['label']}\" ({item['category']}):\n"
                f"  * Target Subject: {target_subject} at {body_loc} [{spatial_anchor}].\n"
                f"  * Replacement Action: Replace {current_attire} with the garment in Reference Garment #{pin_num}.\n"
                f"  * Tailoring & Fit: Harmonize naturally with this exact subject's body geometry, pose, and ambient scene lighting."
            )

            contents.append(f"Reference Garment #{pin_num} (Label: {item['label']}):")
            contents.append(to_image_part(item["garment_bytes"]))

            loaded_assignments.append({
                "id": f"asgn_{uuid.uuid4().hex[:8]}",
                "wardrobe_item_id": item["item_id"],
                "pin_number": pin_num,
                "drop_position": item["drop_pos"],
                "target_description": item["target_desc"],
                "region_bbox": item["region_bbox"],
                "grounded_subject": target_subject,
                "grounded_location": body_loc,
            })

        guardrail = grounding_data.get("unmodified_subjects_guardrail")
        if guardrail:
            instruction_lines.append(f"\nMULTI-SUBJECT INVARIANCE GUARDRAIL:\n- {guardrail.strip()}")

        if custom_instruction and custom_instruction.strip():
            instruction_lines.append(f"\nADDITIONAL STYLING DIRECTIVE:\n- {custom_instruction.strip()}")

        instructions_block = "\n".join(instruction_lines) if instruction_lines else "Swap outfit with provided reference garments."
        compiled_prompt = WARDROBE_COMPOSITION_SYSTEM_PROMPT.replace(
            "{COMPOSITION_INSTRUCTIONS}",
            instructions_block
        )
        contents.append(compiled_prompt)

        final_neg_prompt = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT
        request_id = f"compose_{uuid.uuid4().hex}"
        self._audit(
            "wardrobe_compose_request",
            request_id,
            parent_id=parent_id,
            assignments_count=len(loaded_assignments),
            grounded_subjects=[a.get("grounded_subject") for a in loaded_assignments],
            seed=seed,
            aspect_ratio=aspect_ratio,
            negative_prompt=final_neg_prompt,
            conversation_id=conversation_id,
        )

        child_id = f"gen_wardrobe_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        image_bytes = await self._call_multi_image_model(
            contents=contents,
            seed=seed,
            aspect_ratio=aspect_ratio,
            negative_prompt=final_neg_prompt,
            audit_request_id=request_id,
        )

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{child_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        width, height = self._process_and_save_image(image_bytes, filepath, aspect_ratio)

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": {
                "wardrobe_composition": True,
                "refinement_prompt": f"Wardrobe swap ({len(loaded_assignments)} item{'s' if len(loaded_assignments) != 1 else ''}): " + ", ".join([f"Pin #{a['pin_number']}" for a in loaded_assignments]),
                "conversation_id": conversation_id,
                "assignments": loaded_assignments,
            },
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "conversation_id": conversation_id,
        }
        await self.db.create_generation(record)

        # Save individual assignments to DB
        for asgn in loaded_assignments:
            await self.db.create_composition_assignment({
                "id": asgn["id"],
                "generation_id": child_id,
                "wardrobe_item_id": asgn["wardrobe_item_id"],
                "pin_number": asgn["pin_number"],
                "drop_position": asgn["drop_position"],
                "target_description": asgn["target_description"],
                "region_bbox": asgn.get("region_bbox"),
            })

        self._audit(
            "wardrobe_compose_response",
            request_id,
            generation_id=child_id,
            parent_id=parent_id,
            output_path=filepath,
            seed=seed,
            aspect_ratio=aspect_ratio,
            conversation_id=conversation_id,
        )
        logger.info(f"Wardrobe composition {child_id} created successfully.")

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": seed,
            "compiled_prompt": compiled_prompt,
            "negative_prompt": final_neg_prompt,
            "image_url": f"/api/images/{filename}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "conversation_id": conversation_id,
            "assignments": loaded_assignments,
        }

    async def inpaint_region(
        self,
        parent_id: str,
        image_bytes: bytes,
        mask_bytes: bytes,
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Canvas Studio: Targeted inpainting with a source image and black & white mask.
        Tracks full mask telemetry, persists mask artifacts, and audits adjustments.
        """
        parent_record = await self.db.get_generation(parent_id) if parent_id else None
        moodboard_id = parent_record.get("moodboard_id") if parent_record else None
        saved_state = parent_record.get("schema_json", {}) if parent_record else {}
        aspect_ratio = parent_record.get("aspect_ratio", "2:3") if parent_record else "2:3"
        parent_seed = parent_record.get("seed", 4289102) if parent_record else 4289102
        active_seed = seed if seed is not None else parent_seed

        neg_prompt = negative_prompt if negative_prompt is not None else DEFAULT_NEGATIVE_PROMPT
        request_id = f"inpaint_{uuid.uuid4().hex}"

        # Analyze mask metrics & source image telemetry
        mask_stats = analyze_mask_bytes(mask_bytes)
        base_image = Image.open(io.BytesIO(image_bytes))
        mask_image = Image.open(io.BytesIO(mask_bytes))

        source_stats = {
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
            "bytes": len(image_bytes),
            "width": base_image.width,
            "height": base_image.height,
            "format": base_image.format or "PNG",
        }

        # Structured audit of the incoming inpainting request
        self._audit(
            "inpaint_request",
            request_id,
            parent_id=parent_id,
            prompt=prompt,
            negative_prompt=neg_prompt,
            seed=active_seed,
            model=self.inpaint_model_name,
            aspect_ratio=aspect_ratio,
            source_image=source_stats,
            mask=mask_stats,
        )

        logger.info(
            f"Inpaint request [{request_id}]: parent={parent_id}, prompt='{prompt}', "
            f"mask={mask_stats['width']}x{mask_stats['height']} ({mask_stats['coverage_percentage']}% coverage, "
            f"bbox={mask_stats['bounding_box']}), seed={active_seed}, model={self.inpaint_model_name}"
        )

        started = time.perf_counter()

        # Formulate precise spatial instructions for the model
        spatial_prompt = INPAINT_SYSTEM_PROMPT.replace("{USER_PROMPT}", prompt.strip())
        if neg_prompt:
            suffix = INPAINT_SUFFIX.replace("{NEGATIVE_PROMPT}", neg_prompt)
            spatial_prompt = f"{spatial_prompt}\n\n{suffix}"

        contents = [base_image, mask_image, spatial_prompt]


        # Configure image generation modalities
        image_config = None
        if hasattr(types, "ImageConfig"):
            valid_ratios = {"1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2"}
            target_ratio = aspect_ratio if aspect_ratio in valid_ratios else "1:1"
            image_config = types.ImageConfig(aspect_ratio=target_ratio)

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=image_config,
        )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.inpaint_model_name,
                contents=contents,
                config=config,
            )
        except Exception as model_err:
            self._audit(
                "inpaint_error",
                request_id,
                parent_id=parent_id,
                error=repr(model_err),
                mask_summary={
                    "coverage_percentage": mask_stats["coverage_percentage"],
                    "dimensions": [mask_stats["width"], mask_stats["height"]],
                },
            )
            logger.error(f"Inpaint request [{request_id}] failed: {model_err}")
            raise

        output_image_bytes = None
        finish_reason = None
        text_notes = []

        if response.candidates and response.candidates[0].content:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        output_image_bytes = part.inline_data.data
                        break
                    elif hasattr(part, "as_image") and callable(part.as_image):
                        try:
                            img_obj = part.as_image()
                            if img_obj:
                                buf = io.BytesIO()
                                img_obj.save(buf, format="PNG")
                                output_image_bytes = buf.getvalue()
                                break
                        except Exception:
                            pass
                    if getattr(part, "text", None):
                        text_notes.append(part.text)

        if not output_image_bytes:
            reason_msg = f" Finish reason: {finish_reason}." if finish_reason else ""
            note_msg = f" Model response notes: {' '.join(text_notes)}" if text_notes else ""
            raise RuntimeError(
                f"No inpaint image bytes returned from Google GenAI API for model {self.inpaint_model_name}.{reason_msg}{note_msg}"
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        child_id = f"gen_inpaint_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{child_id}_master.png"
        filepath = os.path.join(gen_dir, filename)
        mask_filename = f"{child_id}_mask.png"
        mask_filepath = os.path.join(gen_dir, mask_filename)

        # Save both master output image (processed to 4K) and the mask artifact to disk
        width, height = self._process_and_save_image(output_image_bytes, filepath, aspect_ratio)
        with open(mask_filepath, "wb") as f:
            f.write(mask_bytes)

        # Structured audit of successful response and mask artifact
        self._audit(
            "inpaint_response",
            request_id,
            generation_id=child_id,
            parent_id=parent_id,
            output={
                "sha256": hashlib.sha256(output_image_bytes).hexdigest(),
                "bytes": len(output_image_bytes),
                "filename": filename,
            },
            mask_artifact={
                "filename": mask_filename,
                "mask_url": f"/api/images/{mask_filename}",
                "coverage_percentage": mask_stats["coverage_percentage"],
            },
            duration_ms=duration_ms,
        )

        # Store inpaint metadata in generation schema_json
        inpaint_meta = {
            "parent_id": parent_id or None,
            "prompt": prompt,
            "negative_prompt": neg_prompt,
            "mask_url": f"/api/images/{mask_filename}",
            "mask_path": mask_filepath,
            "mask_stats": mask_stats,
        }
        updated_state = dict(saved_state) if isinstance(saved_state, dict) else {}
        updated_state["inpaint_metadata"] = inpaint_meta

        record = {
            "id": child_id,
            "parent_id": parent_id or None,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": updated_state,
            "compiled_prompt": f"[Inpaint Edit] {prompt}",
            "negative_prompt": neg_prompt,
            "seed": active_seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
        }
        await self.db.create_generation(record)
        logger.info(
            f"Inpaint generation [{child_id}] completed in {duration_ms}ms: "
            f"master saved at {filepath}, mask artifact saved at {mask_filepath} "
            f"(coverage={mask_stats['coverage_percentage']}%)"
        )

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": active_seed,
            "compiled_prompt": f"[Inpaint Edit] {prompt}",
            "negative_prompt": neg_prompt,
            "image_url": f"/api/images/{filename}",
            "mask_url": f"/api/images/{mask_filename}",
            "mask_stats": mask_stats,
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
        }



    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 4289102,
        aspect_ratio: str = "1:1",
        parent_id: Optional[str] = None,
        moodboard_id: Optional[str] = None,
        chips_snapshot: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Legacy generation method for backwards compatibility.
        """
        gen_id = f"gen_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Legacy generation request: {gen_id} (seed={seed})")

        image_bytes = await self._call_image_model(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
        )

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{gen_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        width, height = self._process_and_save_image(image_bytes, filepath, aspect_ratio)

        record = {
            "id": gen_id,
            "parent_id": parent_id,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": chips_snapshot or {},
            "compiled_prompt": prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
        }
        await self.db.create_generation(record)
        logger.info(f"Legacy generation {gen_id} saved successfully.")

        return {
            "generation_id": gen_id,
            "created_at": created_at,
            "compiled_prompt": prompt,
            "seed": seed,
            "master_image_url": f"/api/images/{filename}",
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
        }
