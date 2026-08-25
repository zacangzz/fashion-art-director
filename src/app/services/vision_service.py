import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
from google import genai
from google.genai import types

from app.schemas.domain import (
    TagChip,
    TagCategory,
    TagStudioState,
    SceneSchema,
)
from app.utils.logger import get_logger
from app.utils.prompt_loader import EXTRACTION_SYSTEM_PROMPT, USER_BASELINE_TEMPLATE

logger = get_logger("vision_service")

VALID_CATEGORIES = [
    TagCategory.SUBJECT_DETAILS.value,
    TagCategory.OBJECTS_PROPS.value,
    TagCategory.WARDROBE_HAIR.value,
    TagCategory.ENVIRONMENT.value,
    TagCategory.LAYOUT_FRAMING.value,
    TagCategory.LIGHTING.value,
    TagCategory.COLOR_PROFILE.value,
    TagCategory.CAMERA_OPTICS.value,
    TagCategory.MOOD_ERA.value,
]

DEFAULT_FALLBACK_TAGS: Dict[str, List[Dict[str, Any]]] = {
    TagCategory.SUBJECT_DETAILS.value: [
        {"label": "striking expressive subject", "weight": 1.0},
        {"label": "natural authentic pose", "weight": 1.0},
    ],
    TagCategory.OBJECTS_PROPS.value: [
        {"label": "curated designer furniture", "weight": 1.0},
    ],
    TagCategory.WARDROBE_HAIR.value: [
        {"label": "tailored contemporary wardrobe", "weight": 1.0},
        {"label": "styled textured hair", "weight": 1.0},
    ],
    TagCategory.ENVIRONMENT.value: [
        {"label": "architectural spatial setting", "weight": 1.0},
    ],
    TagCategory.LAYOUT_FRAMING.value: [
        {"label": "cinematic medium shot", "weight": 1.0},
        {"label": "balanced dynamic composition", "weight": 1.0},
    ],
    TagCategory.LIGHTING.value: [
        {"label": "natural directional sunlight", "weight": 1.0},
        {"label": "soft ambient fill with gentle contrast", "weight": 1.0},
    ],
    TagCategory.COLOR_PROFILE.value: [
        {"label": "warm harmonious color palette", "weight": 1.0},
        {"label": "rich analog film tone", "weight": 1.0},
    ],
    TagCategory.CAMERA_OPTICS.value: [
        {"label": "35mm prime lens", "weight": 1.0},
        {"label": "shallow depth of field f/2.0", "weight": 1.0},
    ],
    TagCategory.MOOD_ERA.value: [
        {"label": "editorial luxury aesthetic", "weight": 1.0},
        {"label": "timeless candid vibe", "weight": 1.0},
    ],
}


class VisionService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.1-flash-lite",
        audit_path: Optional[Path] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)
        self.audit_path = Path(audit_path or "storage/logs/vision_audit.jsonl")

    def _audit(self, event: str, request_id: str, **details: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "request_id": request_id,
            **details,
        }
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as audit_err:
            logger.warning(f"Could not write Vision audit event: {audit_err}")

    def _prepare_image_parts(self, image_bytes_list: List[bytes]) -> List[Any]:
        contents = []
        for img_bytes in image_bytes_list:
            mime_type = "image/png"
            if img_bytes.startswith(b"\xff\xd8"):
                mime_type = "image/jpeg"
            elif img_bytes.startswith(b"RIFF") and b"WEBP" in img_bytes[:16]:
                mime_type = "image/webp"
            elif img_bytes.startswith(b"%PDF"):
                mime_type = "application/pdf"

            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
        return contents

    async def extract_tag_studio_state(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        locked_categories: Optional[List[str]] = None,
        existing_categories: Optional[Dict[str, Any]] = None,
        existing_narrative: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a dual narrative summary and 9-category TagChip dictionary from
        moodboard reference files and an optional user creative text prompt.
        Preserves categories in locked_categories from existing_categories if supplied.
        """
        prompt_log = f" with prompt baseline ('{prompt[:50]}...')" if prompt and prompt.strip() else ""
        logger.info(
            f"Extracting 9-category visual tags from {len(image_bytes_list)} moodboard file(s){prompt_log} using {self.model_name}..."
        )
        contents = self._prepare_image_parts(image_bytes_list)

        instruction = EXTRACTION_SYSTEM_PROMPT
        if prompt and prompt.strip():
            instruction = (
                f"{instruction.rstrip()}\n\n"
                f'{USER_BASELINE_TEMPLATE.replace("{USER_PROMPT}", prompt.strip())}'
            )

        contents.append(instruction)

        request_id = f"vision_{uuid.uuid4().hex}"
        self._audit(
            "vision_request",
            request_id,
            model=self.model_name,
            config={"response_mime_type": "application/json"},
            image_paths=image_paths or [],
            instruction=instruction,
            locked_categories=locked_categories or [],
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except Exception as model_err:
            self._audit("vision_error", request_id, stage="model_call", error=repr(model_err))
            raise

        raw_text = getattr(response, "text", "") or ""
        extracted_data = {}
        clean_text = (raw_text or "{}").strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        try:
            extracted_data = json.loads(clean_text)
        except Exception as parse_err:
            logger.warning(f"Could not parse JSON from vision model response: {parse_err}. Falling back.")
            extracted_data = {}

        extracted_master_prompt = (
            extracted_data.get("master_prompt")
            or extracted_data.get("narrative")
            or (prompt.strip() if prompt and prompt.strip() else None)
        )
        extracted_narrative = (
            extracted_data.get("narrative")
            or (prompt.strip() if prompt and prompt.strip() else "A stunning cinematic visual composition capturing authentic emotion and refined aesthetic details.")
        )
        extracted_categories_raw = extracted_data.get("categories") or {}

        # Normalize and construct TagChip objects for all 9 categories
        categories_result: Dict[str, List[Dict[str, Any]]] = {}
        locked_set = set(locked_categories or [])

        for cat_key in VALID_CATEGORIES:
            # If locked and we have existing tags for this category, preserve them
            if cat_key in locked_set and existing_categories and cat_key in existing_categories:
                existing_val = existing_categories[cat_key]
                if isinstance(existing_val, list):
                    categories_result[cat_key] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in existing_val
                    ]
                    continue

            # Otherwise populate from extracted model tags or fallback
            raw_tags = extracted_categories_raw.get(cat_key) or DEFAULT_FALLBACK_TAGS.get(cat_key, [])
            chip_list: List[Dict[str, Any]] = []

            for idx, tag in enumerate(raw_tags):
                if isinstance(tag, str):
                    label_str = tag.strip()
                    weight_val = 1.0
                elif isinstance(tag, dict):
                    label_str = str(tag.get("label", "")).strip()
                    weight_val = float(tag.get("weight", 1.0))
                else:
                    label_str = str(tag).strip()
                    weight_val = 1.0

                if not label_str:
                    continue

                chip_list.append({
                    "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                    "category": cat_key,
                    "label": label_str,
                    "enabled": True,
                    "locked": cat_key in locked_set,
                    "weight": weight_val,
                    "isCustom": False,
                })

            if not chip_list:
                for fb_idx, fb_tag in enumerate(DEFAULT_FALLBACK_TAGS.get(cat_key, [])):
                    chip_list.append({
                        "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                        "category": cat_key,
                        "label": fb_tag["label"],
                        "enabled": True,
                        "locked": cat_key in locked_set,
                        "weight": fb_tag.get("weight", 1.0),
                        "isCustom": False,
                    })

            categories_result[cat_key] = chip_list

        self._audit(
            "vision_response",
            request_id,
            raw_response=raw_text,
            extracted_master_prompt=extracted_master_prompt,
            extracted_narrative=extracted_narrative,
            categories_count={k: len(v) for k, v in categories_result.items()},
        )

        return {
            "master_prompt": extracted_master_prompt,
            "narrative": extracted_narrative,
            "categories": categories_result,
            "locked_categories": list(locked_set),
        }

    async def extract_scene_schema(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        locked_sections: Optional[List[str]] = None,
        existing_schema: Optional[Dict[str, Any]] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Backwards-compatible wrapper calling extract_tag_studio_state.
        """
        res = await self.extract_tag_studio_state(
            image_bytes_list=image_bytes_list,
            prompt=prompt,
            locked_categories=locked_sections,
            existing_categories=existing_schema.get("categories") if existing_schema and isinstance(existing_schema, dict) else existing_schema,
            existing_narrative=existing_schema.get("narrative") if existing_schema and isinstance(existing_schema, dict) else None,
            image_paths=image_paths,
        )
        return res

    async def analyze_moodboard(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> List[TagChip]:
        state = await self.extract_tag_studio_state(
            image_bytes_list, prompt=prompt, image_paths=image_paths
        )
        all_chips: List[TagChip] = []
        for cat_tags in state.get("categories", {}).values():
            for tag_dict in cat_tags:
                all_chips.append(TagChip(**tag_dict))
        return all_chips
