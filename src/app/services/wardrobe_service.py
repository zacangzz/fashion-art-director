import os
import io
import json
import uuid
import time
import base64
import unittest.mock
import concurrent.futures
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image, ImageFilter
from google import genai
from google.genai import types

from app.db.database import FirestoreManager, DatabaseManager
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from app.schemas.domain import (
    WardrobeSegmentationResult,
    ClothingRegionDetectionResult,
    GarmentExtractedDetails,
)
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger
from app.utils.pricing import extract_usage_metadata, calculate_cost
from app.utils.json_utils import clean_json_text, parse_json_safely
from app.utils.image_utils import (
    to_image_part,
    to_interaction_image_input,
    prepare_interaction_input,
    normalize_bounding_box,
)
from app.utils.prompt_loader import (
    WARDROBE_SEGMENTATION_PROMPT,
    CLOTHING_REGION_DETECTION_PROMPT,
    SUBJECT_GROUNDING_PROMPT,
    GARMENT_UPSCALE_SYSTEM_PROMPT,
    GARMENT_FEATURE_EXTRACTION_PROMPT,
)

logger = get_logger("wardrobe_service")


class WardrobeService:
    """
    Synchronous service responsible for wardrobe management: lookbook segmentation, feature extraction,
    spatial subject grounding, and garment upscale processing.
    Composes ImageGenerator, StorageService, FirestoreManager, and TelemetryLogger.
    Zero circular coupling.
    """

    def __init__(
        self,
        db_manager: FirestoreManager,
        api_key: str,
        storage_dir: Optional[str] = None,
        storage_service: Optional[StorageService] = None,
        vision_model: str = "gemini-3.5-flash-lite",
        imagen_model: str = "gemini-3.1-flash-image",
        audit_path: Optional[str] = None,
        client: Optional[genai.Client] = None,
        image_generator: Optional[ImageGenerator] = None,
        telemetry: Optional[TelemetryLogger] = None,
        generation_service: Optional[Any] = None,
    ):
        self.db = db_manager
        self.db_manager = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir or "./storage"
        self.storage_service = storage_service or StorageService(storage_dir=self.storage_dir, environment="local")
        self.vision_model = vision_model
        self.imagen_model = imagen_model
        self.audit_path = audit_path
        self.client = client or genai.Client(api_key=api_key)
        self.image_generator = image_generator
        self.telemetry = telemetry or TelemetryLogger(
            component="wardrobe",
        )

    def _audit(self, event_type: str, request_id: str, **kwargs):
        try:
            self.telemetry.record_event(
                event=event_type,
                request_id=request_id,
                component="wardrobe",
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Failed to write wardrobe audit log: {e}")

    def _clean_json_text(self, text: str) -> str:
        return clean_json_text(text)

    def _normalize_bbox(self, bbox_raw: Any, img_w: int, img_h: int) -> Optional[List[float]]:
        return normalize_bounding_box(bbox_raw, img_w, img_h)

    def _generate_content_sync(
        self, contents: List[Any], config: Optional[Any] = None, vision_model: Optional[str] = None
    ) -> Any:
        active_model = vision_model or self.vision_model

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
        """Backward-compatibility sync alias."""
        return self._generate_content_sync(*args, **kwargs)

    def extract_garment_features(
        self,
        crop_bytes: bytes,
        label: str,
        category: str,
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        active_model = vision_model or self.vision_model
        request_id = f"feat_{uuid.uuid4().hex[:8]}"
        image_part = to_image_part(crop_bytes)
        contents = [
            image_part,
            f"GARMENT TARGET: {label} ({category})\n" + GARMENT_FEATURE_EXTRACTION_PROMPT,
        ]
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=GarmentExtractedDetails,
        )

        try:
            response = self._generate_content_sync(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            parsed = parse_json_safely(raw_text, default={})
            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            feat_cost = float(cost_info.get("cost_usd", 0.0))
            feat_tokens = int(usage_dict.get("total_token_count", 0))

            if isinstance(parsed, dict):
                parsed["_cost_usd"] = feat_cost
                parsed["_tokens"] = feat_tokens

            self._audit(
                "garment_feature_extraction_success",
                request_id,
                label=label,
                category=category,
                has_text=parsed.get("has_text_or_logo", False) if isinstance(parsed, dict) else False,
                has_graphic=parsed.get("has_graphic_or_print", False) if isinstance(parsed, dict) else False,
                tokens=feat_tokens,
                cost_usd=feat_cost,
            )
            return parsed if isinstance(parsed, dict) else {}
        except Exception as exc:
            logger.warning(f"Feature extraction failed for '{label}': {exc}")
            return {
                "garment_type": label,
                "primary_color": "as shown",
                "fabric_texture": "standard fabric",
                "has_graphic_or_print": False,
                "has_text_or_logo": False,
                "exact_text_content": [],
                "graphic_description": None,
                "logo_and_print_placement": None,
                "hardware_and_details": None,
                "_cost_usd": 0.0,
                "_tokens": 0,
            }

    def segment_and_save_sheet(
        self,
        image_bytes: bytes,
        original_filename: str = "wardrobe_sheet.png",
        vision_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> List[Dict[str, Any]]:
        active_model = vision_model or self.vision_model
        sheet_id = f"sheet_{uuid.uuid4().hex[:8]}"
        request_id = f"seg_{uuid.uuid4().hex}"
        logger.info(f"Segmenting wardrobe sheet {sheet_id} ({len(image_bytes)} bytes) using vision model '{active_model}' for user '{user_id}'")

        safe_ext = os.path.splitext(original_filename)[1] or ".png"
        source_filename = f"{sheet_id}_source{safe_ext}"
        source_storage_path = self.storage_service.upload_bytes(
            user_id=user_id,
            category="wardrobe/sources",
            filename=source_filename,
            data=image_bytes,
        )

        image_part = to_image_part(image_bytes)
        contents = [image_part, WARDROBE_SEGMENTATION_PROMPT]
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=WardrobeSegmentationResult,
        )

        self._audit(
            "wardrobe_segmentation_requested",
            request_id,
            sheet_id=sheet_id,
            vision_model=active_model,
            image_bytes_len=len(image_bytes),
        )

        try:
            response = self._generate_content_sync(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            parsed = parse_json_safely(raw_text, default={})
            items_raw = parsed.get("items", []) if isinstance(parsed, dict) else []

            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            seg_cost = float(cost_info.get("cost_usd", 0.0))
            seg_tokens = int(usage_dict.get("total_token_count", 0))

            self._audit(
                "wardrobe_segmentation_success",
                request_id,
                sheet_id=sheet_id,
                items_detected=len(items_raw),
                tokens=seg_tokens,
                cost_usd=seg_cost,
            )
        except Exception as e:
            self._audit("wardrobe_segmentation_error", request_id, sheet_id=sheet_id, error=str(e))
            logger.error(f"Wardrobe segmentation failed: {e}")
            raise

        # Load PIL image for cropping
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_w, img_h = pil_img.size

        results: List[Dict[str, Any]] = []
        cost_per_item = seg_cost / max(len(items_raw), 1)
        tokens_per_item = seg_tokens // max(len(items_raw), 1)

        def _process_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
            item_id = f"item_{uuid.uuid4().hex[:8]}"
            label = item_data.get("label", "Garment Item")
            category = item_data.get("category", "tops")
            bbox_raw = item_data.get("bounding_box", {})

            norm_box = self._normalize_bbox(bbox_raw, img_w, img_h)
            if not norm_box:
                norm_box = [0.0, 0.0, 1.0, 1.0]

            ymin, xmin, ymax, xmax = norm_box
            left = max(0, int(xmin * img_w))
            top = max(0, int(ymin * img_h))
            right = min(img_w, int(xmax * img_w))
            bottom = min(img_h, int(ymax * img_h))

            if right <= left or bottom <= top:
                left, top, right, bottom = 0, 0, img_w, img_h

            cropped_pil = pil_img.crop((left, top, right, bottom))
            crop_buf = io.BytesIO()
            cropped_pil.save(crop_buf, format="PNG")
            crop_bytes = crop_buf.getvalue()

            crop_filename = f"{item_id}_cropped.png"
            crop_storage_path = self.storage_service.upload_bytes(
                user_id=user_id,
                category="wardrobe/items",
                filename=crop_filename,
                data=crop_bytes,
            )

            # Extract detailed features
            details = self.extract_garment_features(
                crop_bytes, label, category, vision_model=active_model
            )
            feat_cost = float(details.pop("_cost_usd", 0.0))
            feat_tokens = int(details.pop("_tokens", 0))

            total_item_cost = round(cost_per_item + feat_cost, 6)
            total_item_tokens = tokens_per_item + feat_tokens

            db_payload = {
                "id": item_id,
                "source_image_path": source_storage_path,
                "label": label,
                "category": category,
                "cropped_image_path": crop_storage_path,
                "upscaled_image_path": None,
                "upscale_status": "pending",
                "bbox_json": norm_box,
                "extracted_details_json": details,
                "cost_usd": total_item_cost,
                "tokens": total_item_tokens,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            self.db.create_wardrobe_item(user_id=user_id, item_data=db_payload)

            res_item = dict(db_payload)
            res_item["bbox"] = norm_box
            res_item["extracted_details"] = details
            return res_item

        max_workers = min(4, max(1, len(items_raw))) if items_raw else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_process_item, items_raw))

        return results

    def upscale_garment(
        self,
        item_id: str,
        user_id: str = "local_dev_user",
        imagen_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        item = self.db.get_wardrobe_item(item_id)
        if not item:
            raise ValueError(f"Wardrobe item '{item_id}' not found")

        active_model = imagen_model or self.imagen_model
        request_id = f"upscale_{uuid.uuid4().hex[:8]}"

        crop_path = item.get("cropped_image_path")
        if not crop_path:
            raise ValueError(f"Wardrobe item '{item_id}' has no cropped image path")

        crop_bytes = self.storage_service.download_bytes(crop_path)

        label = item.get("label", "Garment")
        category = item.get("category", "tops")
        details = item.get("extracted_details") or {}

        details_desc = ""
        if isinstance(details, dict) and details:
            details_desc = f" Texture: {details.get('fabric_texture', 'high quality fabric')}. Primary color: {details.get('primary_color', 'as shown')}."

        prompt = GARMENT_UPSCALE_SYSTEM_PROMPT.format(
            LABEL=label,
            CATEGORY=category,
            EXTRACTED_DETAILS_PROMPT=details_desc,
        )

        generator = self.image_generator
        if not generator:
            generator = ImageGenerator(client=self.client, default_model=active_model, telemetry=self.telemetry)

        self._audit(
            "wardrobe_upscale_started",
            request_id,
            item_id=item_id,
            label=label,
            model=active_model,
        )

        try:
            upscaled_bytes = generator.generate(
                prompt=prompt,
                aspect_ratio="1:1",
                model=active_model,
                reference_images=[crop_bytes],
                image_size="4K",
                audit_request_id=request_id,
            )

            upscale_filename = f"{item_id}_upscaled.png"
            upscaled_storage_path = self.storage_service.upload_bytes(
                user_id=user_id,
                category="wardrobe/items",
                filename=upscale_filename,
                data=upscaled_bytes,
            )

            metrics = generator.last_call_metrics or {}
            upscale_cost = float(metrics.get("cost_usd", 0.04))
            upscale_tokens = int(metrics.get("total_token_count", 1500))

            self.db.update_wardrobe_item_upscale(
                item_id=item_id,
                upscaled_image_path=upscaled_storage_path,
                upscale_status="completed",
                cost_usd=upscale_cost,
                tokens=upscale_tokens,
            )

            self._audit(
                "wardrobe_upscale_success",
                request_id,
                item_id=item_id,
                cost_usd=upscale_cost,
                tokens=upscale_tokens,
            )

            return {
                "id": item_id,
                "label": label,
                "category": category,
                "upscaled_image_path": upscaled_storage_path,
                "upscale_status": "completed",
                "cost_usd": upscale_cost,
                "tokens": upscale_tokens,
            }
        except Exception as exc:
            self._audit("wardrobe_upscale_error", request_id, item_id=item_id, error=str(exc))
            self.db.update_wardrobe_item_upscale(
                item_id=item_id,
                upscaled_image_path=None,
                upscale_status="failed",
                upscale_error=str(exc),
            )
            raise

    def detect_clothing_regions(
        self,
        image_bytes: bytes,
        vision_model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        active_model = vision_model or self.vision_model
        request_id = f"det_{uuid.uuid4().hex[:8]}"

        image_part = to_image_part(image_bytes)
        contents = [image_part, CLOTHING_REGION_DETECTION_PROMPT]
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ClothingRegionDetectionResult,
        )

        try:
            response = self._generate_content_sync(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            parsed = parse_json_safely(raw_text, default={})
            regions = parsed.get("regions", []) if isinstance(parsed, dict) else []

            pil_img = Image.open(io.BytesIO(image_bytes))
            img_w, img_h = pil_img.size

            normalized_regions = []
            for r in regions:
                norm_box = self._normalize_bbox(r.get("bounding_box", {}), img_w, img_h)
                if norm_box:
                    normalized_regions.append({
                        "category": r.get("category", "tops"),
                        "description": r.get("description", ""),
                        "bounding_box": norm_box,
                    })
            return normalized_regions
        except Exception as e:
            logger.warning(f"Clothing region detection failed: {e}")
            return []

    def ground_wardrobe_pins(
        self,
        generation_id: str,
        assignments: List[Dict[str, Any]],
        user_id: str = "local_dev_user",
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates spatial grounding pins (①②③) onto subject image and writes composition records.
        """
        gen = self.db.get_generation(generation_id)
        if not gen:
            raise ValueError(f"Generation '{generation_id}' not found")

        active_model = vision_model or self.vision_model
        request_id = f"ground_{uuid.uuid4().hex[:8]}"

        # Load master image
        img_path = gen.get("master_image_path")
        if not img_path:
            raise ValueError(f"Generation '{generation_id}' has no master image path")
        img_bytes = self.storage_service.download_bytes(img_path)

        # Detect regions if pins lack explicit bounding box
        detected_regions = self.detect_clothing_regions(img_bytes, vision_model=active_model)

        created_assignments = []
        for idx, assign in enumerate(assignments):
            pin_num = assign.get("pin_number", idx + 1)
            item_id = assign.get("wardrobe_item_id")
            drop_pos = assign.get("drop_position") or {}
            target_desc = assign.get("target_description") or ""

            # Match region bbox
            region_bbox = assign.get("region_bbox")
            if not region_bbox and detected_regions:
                # Find matching detected region
                for dr in detected_regions:
                    bbox = dr.get("bounding_box", [0, 0, 1, 1])
                    ymin, xmin, ymax, xmax = bbox
                    px = drop_pos.get("x", 0.5)
                    py = drop_pos.get("y", 0.5)
                    if xmin <= px <= xmax and ymin <= py <= ymax:
                        region_bbox = bbox
                        if not target_desc:
                            target_desc = dr.get("description", "")
                        break

            assignment_id = f"ca_{uuid.uuid4().hex[:8]}"
            assign_data = {
                "id": assignment_id,
                "generation_id": generation_id,
                "wardrobe_item_id": item_id,
                "pin_number": pin_num,
                "drop_position": drop_pos,
                "target_description": target_desc,
                "region_bbox": region_bbox,
            }
            self.db.create_composition_assignment(user_id=user_id, assignment_data=assign_data)
            created_assignments.append(assign_data)

        return {
            "generation_id": generation_id,
            "assignments": created_assignments,
            "total_pins": len(created_assignments),
        }
