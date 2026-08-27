import uuid
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.schemas.domain import TagChip, TagCategory
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger, get_current_request_id
from app.utils.prompt_loader import (
    EXTRACTION_SYSTEM_PROMPT,
    USER_BASELINE_TEMPLATE,
    RESYNC_MASTER_PROMPT_SYSTEM,
    RESYNC_MASTER_PROMPT_TEMPLATE,
)
from app.utils.image_utils import to_image_part

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
        {"label": "striking expressive subject"},
        {"label": "natural authentic pose"},
    ],
    TagCategory.OBJECTS_PROPS.value: [
        {"label": "curated designer furniture"},
    ],
    TagCategory.WARDROBE_HAIR.value: [
        {"label": "tailored contemporary wardrobe"},
        {"label": "styled textured hair"},
    ],
    TagCategory.ENVIRONMENT.value: [
        {"label": "architectural spatial setting"},
        {"label": "refined ambient light"},
    ],
    TagCategory.LAYOUT_FRAMING.value: [
        {"label": "cinematic rule-of-thirds composition"},
    ],
    TagCategory.LIGHTING.value: [
        {"label": "directional soft natural key light"},
    ],
    TagCategory.COLOR_PROFILE.value: [
        {"label": "muted rich editorial palette"},
    ],
    TagCategory.CAMERA_OPTICS.value: [
        {"label": "85mm prime lens f/1.8 shallow depth"},
    ],
    TagCategory.MOOD_ERA.value: [
        {"label": "timeless candid vibe"},
    ],
}


class VisionService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash-lite",
        audit_path: Optional[Path] = None,
        client: Optional[genai.Client] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.client = client or genai.Client(api_key=self.api_key)
        self.audit_path = Path(audit_path or "storage/logs/vision_audit.jsonl")
        self.telemetry = TelemetryLogger(
            audit_path=self.audit_path,
            component="vision",
            storage_dir=self.audit_path.parent.parent if self.audit_path else "./storage",
        )

    def _audit(self, event: str, request_id: str, **details: Any) -> None:
        try:
            self.telemetry.record_event(
                event=event,
                request_id=request_id,
                component="vision",
                **details,
            )
        except Exception as audit_err:
            logger.warning(f"Could not write Vision audit event: {audit_err}")

    def _prepare_image_parts(self, image_bytes_list: List[bytes]) -> List[types.Part]:
        return [to_image_part(b) for b in image_bytes_list]

    async def _generate_content_async(self, contents: List[Any], config: types.GenerateContentConfig) -> Any:
        aio_client = getattr(self.client, "aio", None)
        if aio_client is not None:
            models = getattr(aio_client, "models", None)
            gen_func = getattr(models, "generate_content", None)
            if callable(gen_func) and asyncio.iscoroutinefunction(gen_func):
                return await gen_func(model=self.model_name, contents=contents, config=config)
        return await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=contents,
            config=config,
        )

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
        contents: List[Any] = self._prepare_image_parts(image_bytes_list)

        instruction = EXTRACTION_SYSTEM_PROMPT
        if prompt and prompt.strip():
            user_prompt_instruction = USER_BASELINE_TEMPLATE.replace("{USER_PROMPT}", prompt.strip())
            contents.append(user_prompt_instruction)

        request_id = get_current_request_id() or f"vision_{uuid.uuid4().hex}"

        self._audit(
            "vision_request",
            request_id,
            model=self.model_name,
            config={"response_mime_type": "application/json"},
            image_paths=image_paths or [],
            instruction=instruction,
            locked_categories=locked_categories or [],
        )

        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=instruction,
        )

        try:
            response = await self._generate_content_async(contents, gen_config)
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
                elif isinstance(tag, dict):
                    label_str = str(tag.get("label", "")).strip()
                else:
                    label_str = str(tag).strip()

                if not label_str:
                    continue

                chip_list.append({
                    "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                    "category": cat_key,
                    "label": label_str,
                    "enabled": True,
                    "locked": cat_key in locked_set,
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

    async def resync_master_prompt(
        self,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        previous_master_prompt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Re-synthesizes the Master Generation Prompt and narrative from updated 9-category visual levers.
        """
        request_id = get_current_request_id() or f"resync_{uuid.uuid4().hex}"
        logger.info(f"Re-syncing Master Generation Prompt using {self.model_name}...")

        clean_cats: Dict[str, List[str]] = {}
        if categories and isinstance(categories, dict):
            for cat_key, items in categories.items():
                chip_list = []
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            lbl = str(item.get("label", "")).strip()
                            if lbl:
                                chip_list.append(lbl)
                        elif hasattr(item, "label"):
                            lbl = str(getattr(item, "label", "")).strip()
                            if lbl:
                                chip_list.append(lbl)
                        elif isinstance(item, str) and item.strip():
                            chip_list.append(item.strip())
                clean_cats[cat_key] = chip_list

        cats_json_str = json.dumps(clean_cats, indent=2)

        user_content = (
            RESYNC_MASTER_PROMPT_TEMPLATE
            .replace("{CURRENT_NARRATIVE}", narrative.strip() if narrative else "Editorial portrait scene")
            .replace("{PREVIOUS_MASTER_PROMPT}", previous_master_prompt.strip() if previous_master_prompt else "None")
            .replace("{UPDATED_CATEGORIES_JSON}", cats_json_str)
        )

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_content)],
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=RESYNC_MASTER_PROMPT_SYSTEM,
            response_mime_type="application/json",
            temperature=0.4,
        )

        self._audit(
            "resync_prompt_request",
            request_id,
            model=self.model_name,
            narrative=narrative,
            categories_count={k: len(v) for k, v in clean_cats.items()},
        )

        response = await self._generate_content_async(contents=contents, config=config)
        raw_text = response.text or "{}"

        try:
            parsed = json.loads(raw_text)
        except Exception:
            logger.warning("Failed to parse JSON response for resync_master_prompt, falling back to raw text")
            parsed = {"master_prompt": raw_text.strip(), "narrative": narrative or ""}

        master_prompt = parsed.get("master_prompt", "").strip() or (previous_master_prompt or "")
        updated_narrative = parsed.get("narrative", "").strip() or (narrative or "")

        self._audit(
            "resync_prompt_response",
            request_id,
            master_prompt=master_prompt,
            narrative=updated_narrative,
        )

        return {
            "master_prompt": master_prompt,
            "narrative": updated_narrative,
        }
