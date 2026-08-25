import os
import io
import uuid
import json
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
from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    INPAINT_SYSTEM_PROMPT,
    INPAINT_SUFFIX,
)


logger = get_logger("generation_service")

ASPECT_RATIO_RESOLUTIONS = {
    "1:1": (1440, 1440),
    "2:3": (1080, 1620),
    "3:2": (1620, 1080),
    "3:4": (1080, 1440),
    "4:3": (1440, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


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
                    chip_list.append({"label": item.strip(), "weight": 1.0, "enabled": True})
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
            weight = float(item.get("weight", 1.0))
            if lbl:
                if weight > 1.25:
                    labels.append(f"({lbl}:{weight:.1f})")
                else:
                    labels.append(lbl)
        elif hasattr(item, "label"):
            if getattr(item, "enabled", True) is False:
                continue
            lbl = str(getattr(item, "label", "")).strip()
            weight = float(getattr(item, "weight", 1.0))
            if lbl:
                if weight > 1.25:
                    labels.append(f"({lbl}:{weight:.1f})")
                else:
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
        "Apply the requested modifications below seamlessly, allowing all naturally interconnected visual elements—including lighting falloff, cast shadows, color bounce, material reactions, and environmental reflections—to adjust organically for realistic visual cohesion."
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

    # Convert to grayscale mode for threshold analysis
    gray_mask = mask_img.convert("L")
    pixels = list(gray_mask.get_flattened_data()) if hasattr(gray_mask, "get_flattened_data") else list(gray_mask.getdata())


    # White/active pixels (threshold > 127)
    masked_indices = [i for i, val in enumerate(pixels) if val > 127]
    masked_pixels = len(masked_indices)
    unmasked_pixels = total_pixels - masked_pixels
    coverage_pct = round((masked_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0

    bounding_box = None
    norm_bounding_box = None
    centroid = None

    if masked_pixels > 0:
        min_x = width
        min_y = height
        max_x = 0
        max_y = 0
        sum_x = 0
        sum_y = 0

        for idx in masked_indices:
            y = idx // width
            x = idx % width
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
            sum_x += x
            sum_y += y

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
        model_name: str = "gemini-3.1-flash-lite-image",
        inpaint_model_name: str = "imagen-3.0-capability-001",
        audit_path: Optional[Path] = None,
    ):
        self.db = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir
        self.model_name = model_name
        self.inpaint_model_name = inpaint_model_name
        self.client = genai.Client(api_key=self.api_key)
        self.audit_path = Path(audit_path or os.path.join(storage_dir, "logs", "generation_audit.jsonl"))

    def _audit(self, event: str, request_id: str, **details: Any) -> None:
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                    "request_id": request_id,
                    **details,
                }, ensure_ascii=False, default=str) + "\n")
        except Exception as audit_err:
            logger.warning(f"Could not write generation audit event: {audit_err}")

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
                response = self.client.models.generate_images(model=self.model_name, prompt=prompt, config=config)
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
                mime_type = "image/png"
                if reference_image_bytes.startswith(b"\xff\xd8"):
                    mime_type = "image/jpeg"
                elif reference_image_bytes.startswith(b"RIFF") and b"WEBP" in reference_image_bytes[:16]:
                    mime_type = "image/webp"
                contents.append(types.Part.from_bytes(data=reference_image_bytes, mime_type=mime_type))

            suffix = IMAGE_GENERATION_SUFFIX.format(
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
                            "negative_prompt": negative_prompt},
                    reference_image=reference)

            contents.append(full_prompt)

            try:
                response = self.client.models.generate_content(model=self.model_name, contents=contents)
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
        logger.info(f"Generating baseline candidate {gen_id} (seed={seed})...")

        image_bytes = await self._call_image_model(
            prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
        )

        gen_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(gen_dir, exist_ok=True)
        filename = f"{gen_id}_master.png"
        filepath = os.path.join(gen_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (1080, 1620))

        record = {
            "id": gen_id,
            "parent_id": None,
            "moodboard_id": moodboard_id,
            "is_baseline": True,
            "created_at": created_at,
            "schema_json": state_dict,
            "compiled_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "master_image_path": filepath,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
        }
        await self.db.create_generation(record)
        logger.info(f"Saved baseline record {gen_id} to database and disk at {filepath}")

        return {
            "id": gen_id,
            "seed": seed,
            "image_url": f"/api/images/{filename}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "compiled_prompt": positive_prompt,
        }

    async def generate_4_baselines(
        self,
        moodboard_id: str,
        state: Union[Dict[str, Any], SceneSchema],
        aspect_ratio: str = "2:3",
    ) -> List[Dict[str, Any]]:
        """
        Spawns 4 concurrent baseline generation tasks across 4 unique seeds.
        """
        state_dict = state.model_dump() if isinstance(state, SceneSchema) else state
        narrative = state_dict.get("narrative", "")
        categories = state_dict.get("categories", {})

        compiled_prompt = compile_prompt(narrative=narrative, categories=categories)
        neg_prompt = DEFAULT_NEGATIVE_PROMPT

        # Generate 4 distinct seeds
        seeds = random.sample(range(100000, 9999999), 4)
        logger.info(f"Spawning 4 concurrent baseline tasks for moodboard '{moodboard_id}' across seeds: {seeds}")

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

        results = await asyncio.gather(*tasks)
        logger.info(f"Successfully generated all 4 baseline candidates for moodboard '{moodboard_id}'")
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

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (1080, 1620))

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
            "resolution": {"width": width, "height": height},
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
            response = self.client.models.generate_content(
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

        # Save both master output image and the mask artifact to disk
        with open(filepath, "wb") as f:
            f.write(output_image_bytes)
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

        width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (1080, 1620))

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

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        width, height = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (1440, 1440))

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
            "resolution": {"width": width, "height": height},
        }
