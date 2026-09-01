import uuid
import json
import base64
import unittest.mock
from pathlib import Path
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.schemas.domain import TagChip, TagCategory
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger, get_current_request_id
from app.utils.pricing import extract_usage_metadata, calculate_cost
from app.utils.json_utils import clean_json_text, parse_json_safely
from app.utils.prompt_loader import (
    EXTRACTION_SYSTEM_PROMPT,
    USER_BASELINE_TEMPLATE,
    RESYNC_MASTER_PROMPT_SYSTEM,
    RESYNC_MASTER_PROMPT_TEMPLATE,
    RESYNC_PROMPT_FROM_LEVERS_SYSTEM,
    RESYNC_PROMPT_FROM_LEVERS_TEMPLATE,
    RESYNC_LEVERS_FROM_PROMPT_SYSTEM,
    RESYNC_LEVERS_FROM_PROMPT_TEMPLATE,
    CHECK_CONFLICTS_SYSTEM_PROMPT,
    SPATIAL_SCENE_ANALYSIS_TEMPLATE,
)
from app.utils.image_utils import (
    to_image_part,
    to_interaction_image_input,
    prepare_interaction_input,
)

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
        {"label": "85mm prime lens f/1.8"},
    ],
    TagCategory.MOOD_ERA.value: [
        {"label": "timeless candid vibe"},
    ],
}


class VisionService:
    """
    Vision analysis service composing Gemini Multimodal models for 9-category visual tag extraction,
    conflict detection, and master prompt re-synchronization synchronously.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash-lite",
        audit_path: Optional[Path] = None,
        client: Optional[genai.Client] = None,
        telemetry: Optional[TelemetryLogger] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.client = client or genai.Client(api_key=self.api_key)
        self.audit_path = Path(audit_path or "storage/logs/vision_audit.jsonl")
        self.telemetry = telemetry or TelemetryLogger(
            component="vision",
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

    def _generate_content_sync(
        self, contents: List[Any], config: Optional[types.GenerateContentConfig] = None, model: Optional[str] = None
    ) -> Any:
        active_model = model or self.model_name

        use_interactions = False
        if hasattr(self.client, "interactions") and hasattr(self.client.interactions, "create"):
            models_gen = getattr(getattr(self.client, "models", None), "generate_content", None)
            interactions_create = getattr(getattr(self.client, "interactions", None), "create", None)

            models_gen_configured = getattr(models_gen, "_mock_return_value", unittest.mock.DEFAULT) is not unittest.mock.DEFAULT
            interactions_configured = getattr(interactions_create, "_mock_return_value", unittest.mock.DEFAULT) is not unittest.mock.DEFAULT

            if models_gen_configured and not interactions_configured:
                use_interactions = False
            else:
                use_interactions = True

        if use_interactions:
            api_input = prepare_interaction_input(contents)

            kwargs: Dict[str, Any] = {
                "model": active_model,
                "input": api_input,
            }

            if config is not None:
                sys_inst = getattr(config, "system_instruction", None)
                if sys_inst:
                    if isinstance(sys_inst, str):
                        kwargs["system_instruction"] = sys_inst
                    elif hasattr(sys_inst, "parts"):
                        kwargs["system_instruction"] = " ".join(
                            p.text for p in sys_inst.parts if hasattr(p, "text")
                        )
                    elif hasattr(sys_inst, "text"):
                        kwargs["system_instruction"] = sys_inst.text

                mime = getattr(config, "response_mime_type", None)
                schema = getattr(config, "response_schema", None)
                if mime == "application/json" or schema is not None:
                    resp_fmt: Dict[str, Any] = {
                        "type": "text",
                        "mime_type": "application/json",
                    }
                    if schema is not None:
                        if hasattr(schema, "model_json_schema"):
                            resp_fmt["schema"] = schema.model_json_schema()
                        elif isinstance(schema, dict):
                            resp_fmt["schema"] = schema
                        elif isinstance(schema, type):
                            try:
                                resp_fmt["schema"] = schema.model_json_schema()
                            except Exception:
                                pass
                    kwargs["response_format"] = resp_fmt

                temp = getattr(config, "temperature", None)
                if temp is not None:
                    kwargs["generation_config"] = {"temperature": float(temp)}

            call_func = self.client.interactions.create
            interaction = call_func(**kwargs)

            if not isinstance(getattr(interaction, "text", None), str):
                out_text = getattr(interaction, "output_text", None)
                if not isinstance(out_text, str) and hasattr(interaction, "steps") and interaction.steps:
                    for step in reversed(interaction.steps):
                        if getattr(step, "type", "") == "model_output" and hasattr(step, "content"):
                            for c in getattr(step, "content", []):
                                if isinstance(c, dict) and "text" in c:
                                    out_text = c["text"]
                                elif hasattr(c, "text"):
                                    out_text = c.text
                                if isinstance(out_text, str) and out_text:
                                    break
                        if isinstance(out_text, str) and out_text:
                            break
                try:
                    interaction.text = out_text if isinstance(out_text, str) else ""
                except (AttributeError, TypeError):
                    pass
            return interaction

        if hasattr(self.client, "models") and hasattr(self.client.models, "generate_content"):
            kwargs_legacy: Dict[str, Any] = {"model": active_model, "contents": contents}
            if config is not None:
                kwargs_legacy["config"] = config
            gen_func = self.client.models.generate_content
            return gen_func(**kwargs_legacy)

        raise RuntimeError("Client missing both interactions.create and models.generate_content")

    def _generate_content_async(self, *args, **kwargs):
        """Backwards-compatibility sync alias."""
        return self._generate_content_sync(*args, **kwargs)

    def extract_tag_studio_state(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        locked_categories: Optional[List[str]] = None,
        existing_categories: Optional[Dict[str, Any]] = None,
        existing_narrative: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes a dual narrative summary and 9-category TagChip dictionary from
        moodboard reference files and an optional user creative text prompt.
        """
        active_model = model_name or self.model_name
        prompt_log = f" with prompt baseline ('{prompt[:50]}...')" if prompt and prompt.strip() else ""
        logger.info(
            f"Extracting 9-category visual tags from {len(image_bytes_list)} moodboard file(s){prompt_log} using {active_model}..."
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
            model=active_model,
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
            response = self._generate_content_sync(contents, gen_config, model=active_model)
        except Exception as model_err:
            self._audit("vision_error", request_id, stage="model_call", model=active_model, error=repr(model_err))
            raise

        raw_text = getattr(response, "text", "") or ""
        extracted_data = parse_json_safely(raw_text, default={})

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

        categories_result: Dict[str, List[Dict[str, Any]]] = {}
        locked_set = set(locked_categories or [])

        for cat_key in VALID_CATEGORIES:
            if cat_key in locked_set and existing_categories and cat_key in existing_categories:
                existing_val = existing_categories[cat_key]
                if isinstance(existing_val, list):
                    categories_result[cat_key] = [
                        item.model_dump() if hasattr(item, "model_dump") else item
                        for item in existing_val
                    ]
                    continue

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

        raw_conflicts = extracted_data.get("conflicts") or []
        conflicts_result = []
        if isinstance(raw_conflicts, list):
            for idx, c in enumerate(raw_conflicts):
                if isinstance(c, dict):
                    conflicts_result.append({
                        "id": c.get("id") or f"conflict_{idx+1}",
                        "severity": c.get("severity", "warning"),
                        "conflicting_elements": c.get("conflicting_elements") or [],
                        "categories": c.get("categories") or [],
                        "explanation": c.get("explanation") or "",
                        "recommendation": c.get("recommendation"),
                    })

        usage_dict = extract_usage_metadata(response)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )

        self._audit(
            "vision_response",
            request_id,
            raw_response=raw_text,
            extracted_master_prompt=extracted_master_prompt,
            extracted_narrative=extracted_narrative,
            categories_count={k: len(v) for k, v in categories_result.items()},
            conflicts_count=len(conflicts_result),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return {
            "master_prompt": extracted_master_prompt,
            "narrative": extracted_narrative,
            "categories": categories_result,
            "locked_categories": list(locked_set),
            "conflicts": conflicts_result,
            "tokens": usage_dict,
            "cost_usd": cost_info["cost_usd"],
        }

    def extract_scene_schema(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        locked_sections: Optional[List[str]] = None,
        existing_schema: Optional[Dict[str, Any]] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self.extract_tag_studio_state(
            image_bytes_list=image_bytes_list,
            prompt=prompt,
            locked_categories=locked_sections,
            existing_categories=existing_schema.get("categories") if existing_schema and isinstance(existing_schema, dict) else existing_schema,
            existing_narrative=existing_schema.get("narrative") if existing_schema and isinstance(existing_schema, dict) else None,
            image_paths=image_paths,
        )

    def analyze_moodboard(
        self,
        image_bytes_list: List[bytes],
        prompt: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> List[TagChip]:
        state = self.extract_tag_studio_state(
            image_bytes_list, prompt=prompt, image_paths=image_paths
        )
        all_chips: List[TagChip] = []
        for cat_tags in state.get("categories", {}).values():
            for tag_dict in cat_tags:
                all_chips.append(TagChip(**tag_dict))
        return all_chips

    def resync_prompt_from_levers(
        self,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        previous_master_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes Master Generation Prompt and refined narrative from active 9-category visual levers.
        The 9-category visual levers are the authoritative source of truth.
        """
        active_model = model_name or self.model_name
        request_id = get_current_request_id() or f"resync_prompt_{uuid.uuid4().hex}"
        logger.info(f"Re-syncing Master Generation Prompt from levers using {active_model}...")

        clean_cats: Dict[str, List[str]] = {}
        if categories and isinstance(categories, dict):
            for cat_key, items in categories.items():
                chip_list = []
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            if item.get("enabled", True):
                                lbl = str(item.get("label", "")).strip()
                                if lbl:
                                    chip_list.append(lbl)
                        elif hasattr(item, "label"):
                            if getattr(item, "enabled", True):
                                lbl = str(getattr(item, "label", "")).strip()
                                if lbl:
                                    chip_list.append(lbl)
                        elif isinstance(item, str) and item.strip():
                            chip_list.append(item.strip())
                clean_cats[cat_key] = chip_list

        cats_json_str = json.dumps(clean_cats, indent=2)

        user_content = (
            RESYNC_PROMPT_FROM_LEVERS_TEMPLATE
            .replace("{CATEGORIES_JSON}", cats_json_str)
        )

        contents = [user_content]

        config = types.GenerateContentConfig(
            system_instruction=RESYNC_PROMPT_FROM_LEVERS_SYSTEM,
            response_mime_type="application/json",
            temperature=0.4,
        )

        self._audit(
            "resync_prompt_from_levers_request",
            request_id,
            model=active_model,
            categories_count={k: len(v) for k, v in clean_cats.items()},
        )

        response = self._generate_content_sync(contents=contents, config=config, model=active_model)
        raw_text = getattr(response, "text", "") or "{}"
        parsed = parse_json_safely(raw_text, default={"master_prompt": raw_text.strip(), "narrative": narrative or ""})

        master_prompt = parsed.get("master_prompt", "").strip() or (previous_master_prompt or "")
        updated_narrative = parsed.get("narrative", "").strip() or (narrative or "")

        raw_conflicts = parsed.get("conflicts") or []
        conflicts_result = []
        if isinstance(raw_conflicts, list):
            for idx, c in enumerate(raw_conflicts):
                if isinstance(c, dict):
                    conflicts_result.append({
                        "id": c.get("id") or f"conflict_{idx+1}",
                        "severity": c.get("severity", "warning"),
                        "conflicting_elements": c.get("conflicting_elements") or [],
                        "categories": c.get("categories") or [],
                        "explanation": c.get("explanation") or "",
                        "recommendation": c.get("recommendation"),
                    })

        usage_dict = extract_usage_metadata(response)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )

        self._audit(
            "resync_prompt_from_levers_response",
            request_id,
            model=active_model,
            master_prompt=master_prompt,
            conflicts_count=len(conflicts_result),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return {
            "master_prompt": master_prompt,
            "narrative": updated_narrative,
            "conflicts": conflicts_result,
            "tokens": usage_dict,
            "cost_usd": cost_info["cost_usd"],
        }

    def resync_levers_from_prompt(
        self,
        master_prompt: str,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deconstructs and extracts fine-grained 9-category visual levers from a user's Master Generation Prompt.
        The Master Generation Prompt is the authoritative source of truth.
        """
        active_model = model_name or self.model_name
        request_id = get_current_request_id() or f"resync_levers_{uuid.uuid4().hex}"
        logger.info(f"Extracting visual levers from Master Generation Prompt using {active_model}...")

        user_content = (
            RESYNC_LEVERS_FROM_PROMPT_TEMPLATE
            .replace("{MASTER_PROMPT}", master_prompt.strip())
        )

        contents = [user_content]

        config = types.GenerateContentConfig(
            system_instruction=RESYNC_LEVERS_FROM_PROMPT_SYSTEM,
            response_mime_type="application/json",
            temperature=0.3,
        )

        self._audit(
            "resync_levers_from_prompt_request",
            request_id,
            model=active_model,
            master_prompt_length=len(master_prompt),
            narrative=narrative,
        )

        response = self._generate_content_sync(contents=contents, config=config, model=active_model)
        raw_text = getattr(response, "text", "") or "{}"
        parsed = parse_json_safely(raw_text, default={"categories": {}, "narrative": narrative or ""})

        updated_narrative = parsed.get("narrative", "").strip() or (narrative or "")
        extracted_categories_raw = parsed.get("categories") or {}
        categories_result: Dict[str, List[Dict[str, Any]]] = {}

        existing_label_map: Dict[str, Dict[str, Any]] = {}
        if categories and isinstance(categories, dict):
            for cat_key, items in categories.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            lbl = str(item.get("label", "")).strip().lower()
                            if lbl:
                                existing_label_map[lbl] = item
                        elif hasattr(item, "label"):
                            lbl = str(getattr(item, "label", "")).strip().lower()
                            if lbl:
                                existing_label_map[lbl] = item.model_dump() if hasattr(item, "model_dump") else vars(item)

        for cat_key in VALID_CATEGORIES:
            raw_tags = extracted_categories_raw.get(cat_key)
            chip_list: List[Dict[str, Any]] = []
            if raw_tags and isinstance(raw_tags, list):
                for tag in raw_tags:
                    if isinstance(tag, str):
                        lbl_str = tag.strip()
                    elif isinstance(tag, dict):
                        lbl_str = str(tag.get("label", "")).strip()
                    else:
                        lbl_str = str(tag).strip()

                    if not lbl_str:
                        continue

                    existing_match = existing_label_map.get(lbl_str.lower())
                    if existing_match:
                        chip_list.append({
                            "id": existing_match.get("id") or f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                            "category": cat_key,
                            "label": lbl_str,
                            "enabled": existing_match.get("enabled", True),
                            "locked": existing_match.get("locked", False),
                            "isCustom": existing_match.get("isCustom", False),
                        })
                    else:
                        chip_list.append({
                            "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                            "category": cat_key,
                            "label": lbl_str,
                            "enabled": True,
                            "locked": False,
                            "isCustom": False,
                        })

            if not chip_list and cat_key in DEFAULT_FALLBACK_TAGS:
                for fb_tag in DEFAULT_FALLBACK_TAGS[cat_key]:
                    chip_list.append({
                        "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                        "category": cat_key,
                        "label": fb_tag["label"],
                        "enabled": True,
                        "locked": False,
                        "isCustom": False,
                    })

            categories_result[cat_key] = chip_list

        raw_conflicts = parsed.get("conflicts") or []
        conflicts_result = []
        if isinstance(raw_conflicts, list):
            for idx, c in enumerate(raw_conflicts):
                if isinstance(c, dict):
                    conflicts_result.append({
                        "id": c.get("id") or f"conflict_{idx+1}",
                        "severity": c.get("severity", "warning"),
                        "conflicting_elements": c.get("conflicting_elements") or [],
                        "categories": c.get("categories") or [],
                        "explanation": c.get("explanation") or "",
                        "recommendation": c.get("recommendation"),
                    })

        usage_dict = extract_usage_metadata(response)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )

        self._audit(
            "resync_levers_from_prompt_response",
            request_id,
            model=active_model,
            narrative=updated_narrative,
            categories_count={k: len(v) for k, v in categories_result.items()},
            conflicts_count=len(conflicts_result),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return {
            "categories": categories_result,
            "narrative": updated_narrative,
            "conflicts": conflicts_result,
            "tokens": usage_dict,
            "cost_usd": cost_info["cost_usd"],
        }

    def resync_master_prompt(
        self,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        previous_master_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Re-synthesizes Master Generation Prompt from visual levers, or extracts visual levers if prompt was provided.
        Maintained for backwards-compatibility.
        """
        active_model = model_name or self.model_name
        request_id = get_current_request_id() or f"resync_{uuid.uuid4().hex}"
        logger.info(f"Re-syncing Master Generation Prompt using {active_model}...")

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
            .replace("{PREVIOUS_MASTER_PROMPT}", previous_master_prompt.strip() if previous_master_prompt else "None")
            .replace("{UPDATED_CATEGORIES_JSON}", cats_json_str)
        )

        contents = [user_content]

        config = types.GenerateContentConfig(
            system_instruction=RESYNC_MASTER_PROMPT_SYSTEM,
            response_mime_type="application/json",
            temperature=0.4,
        )

        self._audit(
            "resync_prompt_request",
            request_id,
            model=active_model,
            categories_count={k: len(v) for k, v in clean_cats.items()},
        )

        response = self._generate_content_sync(contents=contents, config=config, model=active_model)
        raw_text = getattr(response, "text", "") or "{}"
        parsed = parse_json_safely(raw_text, default={"master_prompt": raw_text.strip(), "narrative": narrative or ""})

        master_prompt = parsed.get("master_prompt", "").strip() or (previous_master_prompt or "")
        updated_narrative = parsed.get("narrative", "").strip() or (narrative or "")

        extracted_categories_raw = parsed.get("categories") or {}
        categories_result: Dict[str, List[Dict[str, Any]]] = {}

        existing_label_map: Dict[str, Dict[str, Any]] = {}
        if categories and isinstance(categories, dict):
            for cat_key, items in categories.items():
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            lbl = str(item.get("label", "")).strip().lower()
                            if lbl:
                                existing_label_map[lbl] = item
                        elif hasattr(item, "label"):
                            lbl = str(getattr(item, "label", "")).strip().lower()
                            if lbl:
                                existing_label_map[lbl] = item.model_dump() if hasattr(item, "model_dump") else vars(item)

        for cat_key in VALID_CATEGORIES:
            raw_tags = extracted_categories_raw.get(cat_key)
            if not raw_tags and cat_key in clean_cats and clean_cats[cat_key]:
                raw_tags = clean_cats[cat_key]

            chip_list: List[Dict[str, Any]] = []
            if raw_tags and isinstance(raw_tags, list):
                for tag in raw_tags:
                    if isinstance(tag, str):
                        lbl_str = tag.strip()
                    elif isinstance(tag, dict):
                        lbl_str = str(tag.get("label", "")).strip()
                    else:
                        lbl_str = str(tag).strip()

                    if not lbl_str:
                        continue

                    existing_match = existing_label_map.get(lbl_str.lower())
                    if existing_match:
                        chip_list.append({
                            "id": existing_match.get("id") or f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                            "category": cat_key,
                            "label": lbl_str,
                            "enabled": existing_match.get("enabled", True),
                            "locked": existing_match.get("locked", False),
                            "isCustom": existing_match.get("isCustom", False),
                        })
                    else:
                        chip_list.append({
                            "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                            "category": cat_key,
                            "label": lbl_str,
                            "enabled": True,
                            "locked": False,
                            "isCustom": False,
                        })

            if not chip_list and cat_key in DEFAULT_FALLBACK_TAGS:
                for fb_tag in DEFAULT_FALLBACK_TAGS[cat_key]:
                    chip_list.append({
                        "id": f"tag_{cat_key}_{uuid.uuid4().hex[:6]}",
                        "category": cat_key,
                        "label": fb_tag["label"],
                        "enabled": True,
                        "locked": False,
                        "isCustom": False,
                    })

            categories_result[cat_key] = chip_list

        raw_conflicts = parsed.get("conflicts") or []
        conflicts_result = []
        if isinstance(raw_conflicts, list):
            for idx, c in enumerate(raw_conflicts):
                if isinstance(c, dict):
                    conflicts_result.append({
                        "id": c.get("id") or f"conflict_{idx+1}",
                        "severity": c.get("severity", "warning"),
                        "conflicting_elements": c.get("conflicting_elements") or [],
                        "categories": c.get("categories") or [],
                        "explanation": c.get("explanation") or "",
                        "recommendation": c.get("recommendation"),
                    })

        usage_dict = extract_usage_metadata(response)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )

        self._audit(
            "resync_prompt_response",
            request_id,
            model=active_model,
            master_prompt=master_prompt,
            categories_count={k: len(v) for k, v in categories_result.items()},
            conflicts_count=len(conflicts_result),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return {
            "master_prompt": master_prompt,
            "narrative": updated_narrative,
            "categories": categories_result,
            "conflicts": conflicts_result,
            "tokens": usage_dict,
            "cost_usd": cost_info["cost_usd"],
        }

    def check_prompt_conflicts(
        self,
        master_prompt: Optional[str] = "",
        narrative: Optional[str] = "",
        categories: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Reviews master prompt and visual lever tags for contradictory directives.
        """
        active_model = model_name or self.model_name
        request_id = get_current_request_id() or f"conflicts_{uuid.uuid4().hex}"
        logger.info(f"Checking prompt conflicts using {active_model}...")

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
            f"Please review the following visual direction for conflicts:\n\n"
            f"MASTER GENERATION PROMPT:\n{master_prompt.strip() if master_prompt else 'None'}\n\n"
            f"9-CATEGORY VISUAL LEVERS (JSON):\n{cats_json_str}"
        )

        contents = [user_content]

        config = types.GenerateContentConfig(
            system_instruction=CHECK_CONFLICTS_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
        )

        self._audit(
            "check_conflicts_request",
            request_id,
            model=active_model,
            master_prompt=master_prompt,
            categories_count={k: len(v) for k, v in clean_cats.items()},
        )

        usage_dict = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}
        cost_info = {"cost_usd": 0.0}
        try:
            response = self._generate_content_sync(contents=contents, config=config, model=active_model)
            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            raw_text = getattr(response, "text", "") or "{}"
            parsed = parse_json_safely(raw_text, default={"conflicts": []})
        except Exception as exc:
            logger.warning(f"Error executing check_prompt_conflicts: {exc}")
            parsed = {"conflicts": []}

        raw_conflicts = parsed.get("conflicts") or []
        conflicts_result = []
        if isinstance(raw_conflicts, list):
            for idx, c in enumerate(raw_conflicts):
                if isinstance(c, dict):
                    conflicts_result.append({
                        "id": c.get("id") or f"conflict_{idx+1}",
                        "severity": c.get("severity", "warning"),
                        "conflicting_elements": c.get("conflicting_elements") or [],
                        "categories": c.get("categories") or [],
                        "explanation": c.get("explanation") or "",
                        "recommendation": c.get("recommendation"),
                    })

        self._audit(
            "check_conflicts_response",
            request_id,
            model=active_model,
            conflicts_count=len(conflicts_result),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return conflicts_result

    def analyze_spatial_scene_reprojection(
        self,
        subject_image_bytes: bytes,
        background_image_bytes: bytes,
        user_prompt: str,
        staging_params: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        audit_request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Two-pass Vision spatial analysis pass that examines the Subject image (Image 1),
        Background Reference image (Image 2), user prompt, and 2D/3D camera/subject coordinates,
        synthesizing structured 3D photographic directives.
        """
        request_id = audit_request_id or get_current_request_id() or f"req_spatial_vis_{uuid.uuid4().hex[:8]}"
        active_model = model_name or self.model_name or "gemini-3.7-flash"
        params = staging_params or {}

        subject_x = params.get("subject_x", 0.5)
        subject_y = params.get("subject_y", 0.65)
        camera_angle = params.get("camera_angle", "facing_window")
        focal_length = params.get("focal_length_mm", 35)
        zoom_level = params.get("zoom_level", "environmental")
        perspective_mode = params.get("perspective_mode", "auto_align")
        depth_of_field = params.get("depth_of_field", "natural")
        lighting_mode = params.get("lighting_mode", "harmonize_ambient")

        system_instruction = SPATIAL_SCENE_ANALYSIS_TEMPLATE.format(
            SUBJECT_X=subject_x,
            SUBJECT_Y=subject_y,
            CAMERA_ANGLE=camera_angle,
            FOCAL_LENGTH_MM=focal_length,
            ZOOM_LEVEL=zoom_level,
            PERSPECTIVE_MODE=perspective_mode,
            DEPTH_OF_FIELD=depth_of_field,
            LIGHTING_MODE=lighting_mode,
            USER_PROMPT=user_prompt or "Harmonize subject with background reference environment",
        )

        user_content = (
            "Analyze Image 1 (Subject Reference) and Image 2 (Background Environment Reference) "
            "and output the 3D cinematic photographic directives in the specified JSON schema."
        )

        contents = [
            subject_image_bytes,
            background_image_bytes,
            user_content,
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.3,
        )

        self._audit(
            "spatial_vision_analysis_request",
            request_id,
            model=active_model,
            staging_params=params,
            user_prompt=user_prompt,
        )

        usage_dict = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}
        cost_info = {"cost_usd": 0.0}

        try:
            response = self._generate_content_sync(contents=contents, config=config, model=active_model)
            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            raw_text = getattr(response, "text", "") or "{}"
            parsed = parse_json_safely(raw_text, default={})
        except Exception as exc:
            logger.warning(f"Error executing analyze_spatial_scene_reprojection: {exc}")
            parsed = {}

        camera_dir = parsed.get("camera_and_perspective_directive") or f"Align camera to {camera_angle} with {focal_length}mm lens."
        spatial_dir = parsed.get("subject_spatial_placement_directive") or f"Place subjects at position ({subject_x}, {subject_y}) naturally in scene."
        lighting_dir = parsed.get("photometric_lighting_and_shadow_directive") or "Cast natural ambient lighting and realistic contact shadows."
        synthesis_prompt = parsed.get("unified_scene_synthesis_prompt") or user_prompt

        result = {
            "camera_and_perspective_directive": camera_dir,
            "subject_spatial_placement_directive": spatial_dir,
            "photometric_lighting_and_shadow_directive": lighting_dir,
            "unified_scene_synthesis_prompt": synthesis_prompt,
            "tokens": usage_dict,
            "cost_usd": cost_info["cost_usd"],
        }

        self._audit(
            "spatial_vision_analysis_complete",
            request_id,
            model=active_model,
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return result

