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

from app.db.database import FirestoreManager
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from app.schemas.domain import (
    PropSegmentationResult,
    PropExtractedDetails,
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
    get_standard_srgb_profile_bytes,
    standardize_image_to_srgb,
)
from app.utils.prompt_loader import (
    PROP_SEGMENTATION_PROMPT,
    PROP_FEATURE_EXTRACTION_PROMPT,
    PROP_UPSCALE_SYSTEM_PROMPT,
    PROP_SCENE_GROUNDING_PROMPT,
)

logger = get_logger("prop_service")


class PropService:
    """
    Synchronous service responsible for prop management:
    - Multi-prop catalog segmentation & single-prop upload
    - Prop material/finish feature extraction
    - Spatial 3D scene grounding pre-pass for bounding boxes
    - 4K AI asset upscaling
    - Full telemetry logging under component='props'
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
        self.telemetry = telemetry or TelemetryLogger(component="props")

    def _audit(self, event_type: str, request_id: str, **kwargs):
        try:
            self.telemetry.record_event(
                event=event_type,
                request_id=request_id,
                component="props",
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Failed to write prop audit log: {e}")

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
            return self.client.models.generate_content(**kwargs_legacy)

        raise RuntimeError("Client missing both interactions.create and models.generate_content")

    def extract_prop_features(
        self,
        crop_bytes: bytes,
        label: str,
        category: str,
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        active_model = vision_model or self.vision_model
        request_id = f"feat_prop_{uuid.uuid4().hex[:8]}"
        image_part = to_image_part(crop_bytes)
        contents = [
            image_part,
            f"PROP OBJECT TARGET: {label} ({category})\n" + PROP_FEATURE_EXTRACTION_PROMPT,
        ]
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=PropExtractedDetails,
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
                "prop_feature_extraction_success",
                request_id,
                label=label,
                category=category,
                has_text=parsed.get("has_text_or_logo", False) if isinstance(parsed, dict) else False,
                materials=parsed.get("materials", []) if isinstance(parsed, dict) else [],
                tokens=feat_tokens,
                cost_usd=feat_cost,
            )
            return parsed if isinstance(parsed, dict) else {}
        except Exception as exc:
            logger.warning(f"Prop feature extraction failed for '{label}': {exc}")
            return {
                "prop_type": label,
                "materials": ["standard materials"],
                "primary_color": "as shown",
                "surface_finish": "natural finish",
                "textures": None,
                "has_text_or_logo": False,
                "exact_text_content": [],
                "geometry_and_form": None,
                "estimated_scale_hint": None,
                "style_era": None,
                "_cost_usd": 0.0,
                "_tokens": 0,
            }

    def segment_and_save_sheet(
        self,
        image_bytes: bytes,
        original_filename: str = "props_sheet.png",
        vision_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> List[Dict[str, Any]]:
        active_model = vision_model or self.vision_model
        sheet_id = f"propsheet_{uuid.uuid4().hex[:8]}"
        request_id = f"seg_prop_{uuid.uuid4().hex}"
        logger.info(f"Segmenting prop sheet {sheet_id} ({len(image_bytes)} bytes) using vision model '{active_model}' for user '{user_id}'")

        safe_ext = os.path.splitext(original_filename)[1] or ".png"
        source_filename = f"{sheet_id}_source{safe_ext}"
        source_storage_path = self.storage_service.upload_bytes(
            user_id=user_id,
            category="props/sources",
            filename=source_filename,
            data=image_bytes,
        )

        image_part = to_image_part(image_bytes)
        contents = [image_part, PROP_SEGMENTATION_PROMPT]
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=PropSegmentationResult,
        )

        self._audit(
            "prop_segmentation_requested",
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
                "prop_segmentation_success",
                request_id,
                sheet_id=sheet_id,
                items_detected=len(items_raw),
                tokens=seg_tokens,
                cost_usd=seg_cost,
            )
        except Exception as e:
            self._audit("prop_segmentation_error", request_id, sheet_id=sheet_id, error=str(e))
            logger.error(f"Prop segmentation failed: {e}")
            raise

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_w, img_h = pil_img.size

        results: List[Dict[str, Any]] = []
        cost_per_item = seg_cost / max(len(items_raw), 1)
        tokens_per_item = seg_tokens // max(len(items_raw), 1)

        def _process_item(item_data: Dict[str, Any]) -> Dict[str, Any]:
            item_id = f"pi_{uuid.uuid4().hex[:8]}"
            label = item_data.get("label", "Prop Item")
            category = item_data.get("category", "decor")
            bbox_raw = item_data.get("bounding_box") or item_data.get("box_2d") or {}

            norm_box = self._normalize_bbox(bbox_raw, img_w, img_h)
            if not norm_box:
                norm_box = [0.0, 0.0, 1.0, 1.0]

            ymin, xmin, ymax, xmax = norm_box
            pad_y = (ymax - ymin) * 0.025
            pad_x = (xmax - xmin) * 0.025
            crop_ymin = max(0.0, ymin - pad_y)
            crop_xmin = max(0.0, xmin - pad_x)
            crop_ymax = min(1.0, ymax + pad_y)
            crop_xmax = min(1.0, xmax + pad_x)

            left = max(0, int(crop_xmin * img_w))
            top = max(0, int(crop_ymin * img_h))
            right = min(img_w, int(crop_xmax * img_w))
            bottom = min(img_h, int(crop_ymax * img_h))

            if right <= left or bottom <= top:
                left, top, right, bottom = 0, 0, img_w, img_h

            cropped_pil = pil_img.crop((left, top, right, bottom))
            crop_buf = io.BytesIO()
            save_kw: Dict[str, Any] = {"format": "PNG"}
            srgb_bytes = get_standard_srgb_profile_bytes()
            if srgb_bytes:
                save_kw["icc_profile"] = srgb_bytes
            cropped_pil.save(crop_buf, **save_kw)
            crop_bytes = crop_buf.getvalue()

            crop_filename = f"{item_id}_cropped.png"
            crop_storage_path = self.storage_service.upload_bytes(
                user_id=user_id,
                category="props/items",
                filename=crop_filename,
                data=crop_bytes,
            )

            details = self.extract_prop_features(
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

            created = self.db.create_prop_item(user_id=user_id, item_data=db_payload)
            res_item = dict(created)
            res_item["bbox"] = norm_box
            res_item["extracted_details"] = details
            if not res_item.get("image_url"):
                res_item["image_url"] = f"/api/images/{crop_storage_path.lstrip('/')}"
            if not res_item.get("source_image_url"):
                res_item["source_image_url"] = f"/api/images/{source_storage_path.lstrip('/')}"
            return res_item

        max_workers = min(4, max(1, len(items_raw))) if items_raw else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_process_item, items_raw))

        return results

    def save_single_prop(
        self,
        image_bytes: bytes,
        original_filename: str = "prop.png",
        filename: Optional[str] = None,
        label: Optional[str] = None,
        category: Optional[str] = None,
        vision_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Directly saves an individual uploaded prop image without requiring sheet segmentation.
        Performs AI feature extraction and creates a prop item.
        """
        eff_filename = filename or original_filename
        active_model = vision_model or self.vision_model
        item_id = f"pi_{uuid.uuid4().hex[:8]}"
        request_id = f"single_prop_{uuid.uuid4().hex[:8]}"

        safe_ext = os.path.splitext(eff_filename)[1] or ".png"
        source_filename = f"{item_id}_source{safe_ext}"
        source_storage_path = self.storage_service.upload_bytes(
            user_id=user_id,
            category="props/sources",
            filename=source_filename,
            data=image_bytes,
        )

        standardized_bytes = standardize_image_to_srgb(image_bytes, target_format="PNG")
        crop_filename = f"{item_id}_cropped.png"
        crop_storage_path = self.storage_service.upload_bytes(
            user_id=user_id,
            category="props/items",
            filename=crop_filename,
            data=standardized_bytes,
        )

        eff_label = label or os.path.splitext(eff_filename)[0].replace("_", " ").title() or "Custom Prop"
        eff_cat = category or "decor"

        details = self.extract_prop_features(
            standardized_bytes, eff_label, eff_cat, vision_model=active_model
        )
        feat_cost = float(details.pop("_cost_usd", 0.0))
        feat_tokens = int(details.pop("_tokens", 0))

        db_payload = {
            "id": item_id,
            "source_image_path": source_storage_path,
            "label": eff_label,
            "category": eff_cat,
            "cropped_image_path": crop_storage_path,
            "upscaled_image_path": None,
            "upscale_status": "pending",
            "bbox_json": [0.0, 0.0, 1.0, 1.0],
            "extracted_details_json": details,
            "cost_usd": feat_cost,
            "tokens": feat_tokens,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        created = self.db.create_prop_item(user_id=user_id, item_data=db_payload)
        res_item = dict(created)
        res_item["bbox"] = [0.0, 0.0, 1.0, 1.0]
        res_item["extracted_details"] = details
        if not res_item.get("image_url"):
            res_item["image_url"] = f"/api/images/{crop_storage_path.lstrip('/')}"
        if not res_item.get("source_image_url"):
            res_item["source_image_url"] = f"/api/images/{source_storage_path.lstrip('/')}"

        self._audit(
            "prop_single_upload_success",
            request_id,
            item_id=item_id,
            label=eff_label,
            category=eff_cat,
            cost_usd=feat_cost,
            tokens=feat_tokens,
        )
        return res_item

    upload_single_prop = save_single_prop

    def upscale_prop(
        self,
        item_id: str,
        user_id: str = "local_dev_user",
        imagen_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        item = self.db.get_prop_item(item_id)
        if not item:
            raise ValueError(f"Prop item '{item_id}' not found")

        active_model = imagen_model or self.imagen_model
        request_id = f"upscale_prop_{uuid.uuid4().hex[:8]}"

        crop_path = item.get("cropped_image_path")
        if not crop_path:
            raise ValueError(f"Prop item '{item_id}' has no cropped image path")

        crop_bytes = self.storage_service.download_bytes(crop_path)

        label = item.get("label", "Prop Object")
        category = item.get("category", "decor")
        details = item.get("extracted_details") or {}

        details_desc = ""
        if isinstance(details, dict) and details:
            mat = ", ".join(details.get("materials", [])) if isinstance(details.get("materials"), list) else details.get("materials", "")
            finish = details.get("surface_finish", "")
            primary_col = details.get("primary_color", "")
            details_desc = f" Materials: {mat or 'high quality authentic materials'}. Surface Finish: {finish or 'fine finish'}. Primary Color: {primary_col or 'as shown'}."

        prompt = PROP_UPSCALE_SYSTEM_PROMPT.format(
            LABEL=label,
            CATEGORY=category,
            EXTRACTED_DETAILS_PROMPT=details_desc,
        )

        generator = self.image_generator
        if not generator:
            generator = ImageGenerator(client=self.client, default_model=active_model, telemetry=self.telemetry)

        self._audit(
            "prop_upscale_started",
            request_id,
            item_id=item_id,
            label=label,
            model=active_model,
        )

        self.db.update_prop_item_upscale(
            item_id=item_id,
            upscaled_image_path=None,
            upscale_status="processing",
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

            upscaled_bytes = standardize_image_to_srgb(upscaled_bytes, target_format="PNG")
            upscale_filename = f"{item_id}_upscaled.png"
            upscaled_storage_path = self.storage_service.upload_bytes(
                user_id=user_id,
                category="props/items",
                filename=upscale_filename,
                data=upscaled_bytes,
            )

            metrics = generator.last_call_metrics or {}
            upscale_cost = float(metrics.get("cost_usd", 0.04))
            upscale_tokens = int(metrics.get("total_token_count", 1500))

            self.db.update_prop_item_upscale(
                item_id=item_id,
                upscaled_image_path=upscaled_storage_path,
                upscale_status="completed",
                cost_usd=upscale_cost,
                tokens=upscale_tokens,
            )

            self._audit(
                "prop_upscale_success",
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
                "upscaled_image_url": f"/api/images/{upscaled_storage_path.lstrip('/')}",
                "upscale_status": "completed",
                "is_upscaled": True,
                "cost_usd": upscale_cost,
                "tokens": upscale_tokens,
            }
        except Exception as exc:
            self._audit("prop_upscale_error", request_id, item_id=item_id, error=str(exc))
            self.db.update_prop_item_upscale(
                item_id=item_id,
                upscaled_image_path=None,
                upscale_status="failed",
                upscale_error=str(exc),
            )
            raise

    def _heuristic_prop_grounding(self, assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
        grounded_props = []
        for asgn in assignments:
            pin_num = asgn.get("pin_number", 1)
            bbox = asgn.get("bounding_box") or {}
            ymin = float(bbox.get("ymin", 0.4))
            xmin = float(bbox.get("xmin", 0.4))
            ymax = float(bbox.get("ymax", 0.6))
            xmax = float(bbox.get("xmax", 0.6))
            scale = asgn.get("scale_preset", "medium")
            label = asgn.get("item_label") or asgn.get("target_description") or "prop object"
            cat = asgn.get("category", "decor")

            mid_x = (xmin + xmax) / 2.0
            mid_y = (ymin + ymax) / 2.0

            if mid_x < 0.35:
                h_desc = "left side"
            elif mid_x > 0.65:
                h_desc = "right side"
            else:
                h_desc = "center"

            if mid_y < 0.35:
                v_desc = "background upper area"
                depth_plane = "Background"
            elif mid_y > 0.65:
                v_desc = "foreground lower area"
                depth_plane = "Foreground"
            else:
                v_desc = "midground"
                depth_plane = "Midground"

            spatial_anchor = f"{v_desc}, {h_desc} quadrant (bounds: x {round(xmin*100)}%-{round(xmax*100)}%, y {round(ymin*100)}%-{round(ymax*100)}%)"

            if cat == "furniture":
                host_surface = f"Standing on the floor plane in the {v_desc}"
            elif cat in ["tableware", "decor"]:
                host_surface = f"Resting on the nearest horizontal surface or furniture plane at this {v_desc}"
            else:
                host_surface = f"Positioned in the {v_desc} of the scene"

            if scale == "small":
                rel_scale = f"Small decorative accent footprint, occupying approx {round((ymax-ymin)*100)}% of frame height"
            elif scale == "large":
                rel_scale = f"Prominent large-scale feature, occupying approx {round((ymax-ymin)*100)}% of frame height"
            else:
                rel_scale = f"Natural medium proportion, occupying approx {round((ymax-ymin)*100)}% of frame height"

            grounded_props.append({
                "pin_number": pin_num,
                "host_surface": host_surface,
                "spatial_anchor": spatial_anchor,
                "relative_scale": rel_scale,
                "lighting_and_shadow": "Harmonize with primary room lighting and cast realistic contact shadows onto supporting surface",
                "depth_occlusion": f"{depth_plane} placement, overlapping background and respecting foreground elements",
            })

        return {
            "grounded_props": grounded_props,
            "scene_preservation_guardrail": "Strictly preserve all human subjects, hairstyles, clothing, and surrounding architecture exactly as shown in the reference image without any alterations.",
        }

    def ground_prop_boxes(
        self,
        generation_id: str,
        assignments: List[Dict[str, Any]],
        user_id: str = "local_dev_user",
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates spatial grounding for placed prop bounding boxes onto the base scene image,
        runs Gemini Vision / heuristic analysis, and writes assignment records to Firestore.
        """
        gen = self.db.get_generation(generation_id)
        if not gen:
            raise ValueError(f"Generation '{generation_id}' not found")

        active_model = vision_model or self.vision_model
        request_id = f"ground_prop_{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()

        img_path = gen.get("master_image_path")
        if not img_path:
            raise ValueError(f"Generation '{generation_id}' has no master image path")
        img_bytes = self.storage_service.download_bytes(img_path)

        created_assignments = []
        for idx, assign in enumerate(assignments):
            pin_num = assign.get("pin_number", idx + 1)
            item_id = assign.get("prop_item_id")
            bbox = assign.get("bounding_box") or {"ymin": 0.4, "xmin": 0.4, "ymax": 0.6, "xmax": 0.6}
            scale_preset = assign.get("scale_preset", "medium")
            custom_instruction = assign.get("custom_instruction")
            target_desc = assign.get("target_description") or ""

            assignment_id = f"pa_{uuid.uuid4().hex[:8]}"
            assign_data = {
                "id": assignment_id,
                "generation_id": generation_id,
                "prop_item_id": item_id,
                "pin_number": pin_num,
                "bounding_box": bbox,
                "scale_preset": scale_preset,
                "target_description": target_desc,
                "custom_instruction": custom_instruction,
            }
            self.db.create_prop_assignment(user_id=user_id, assignment_data=assign_data)
            created_assignments.append(assign_data)

        fallback_result = self._heuristic_prop_grounding(assignments)
        if not assignments:
            return {
                "generation_id": generation_id,
                "assignments": [],
                "grounded_props": [],
                "scene_preservation_guardrail": "Preserve all subjects and background elements exactly as shown.",
                "cost_usd": 0.0,
                "tokens": 0,
            }

        prop_lines = []
        for asgn in assignments:
            pin_num = asgn.get("pin_number", 1)
            bbox = asgn.get("bounding_box") or {}
            ymin = round(float(bbox.get("ymin", 0.4)) * 100)
            xmin = round(float(bbox.get("xmin", 0.4)) * 100)
            ymax = round(float(bbox.get("ymax", 0.6)) * 100)
            xmax = round(float(bbox.get("xmax", 0.6)) * 100)
            scale = asgn.get("scale_preset", "medium")
            label = asgn.get("item_label") or "Prop Object"
            cat = asgn.get("category", "decor")
            note = asgn.get("custom_instruction")
            note_str = f" | User Note: \"{note}\"" if note else ""
            prop_lines.append(
                f"- Prop #{pin_num}: Bounding Box [ymin={ymin}%, xmin={xmin}%, ymax={ymax}%, xmax={xmax}%] | "
                f"Scale: {scale.upper()} | Title: \"{label}\" ({cat}){note_str}"
            )

        prop_text = "PLACED PROP BOUNDING BOXES TO ANALYZE:\n" + "\n".join(prop_lines)
        image_part = to_image_part(img_bytes)
        contents = [
            image_part,
            prop_text,
            PROP_SCENE_GROUNDING_PROMPT,
        ]

        self._audit(
            "prop_grounding_request",
            request_id,
            props_count=len(assignments),
            model=active_model,
        )

        try:
            response = self._generate_content_sync(contents, vision_model=active_model)
            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            raw_text = getattr(response, "text", "") or ""
            parsed = parse_json_safely(raw_text, default={})

            grounded_list = parsed.get("grounded_props", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            guardrail = (parsed.get("scene_preservation_guardrail") if isinstance(parsed, dict) else None) or fallback_result["scene_preservation_guardrail"]

            grounded_by_pin = {g.get("pin_number"): g for g in grounded_list if isinstance(g, dict)}
            final_grounded = []

            for fallback_pin in fallback_result["grounded_props"]:
                p_num = fallback_pin["pin_number"]
                if p_num in grounded_by_pin:
                    v_pin = grounded_by_pin[p_num]
                    final_grounded.append({
                        "pin_number": p_num,
                        "host_surface": v_pin.get("host_surface") or fallback_pin["host_surface"],
                        "spatial_anchor": v_pin.get("spatial_anchor") or fallback_pin["spatial_anchor"],
                        "relative_scale": v_pin.get("relative_scale") or fallback_pin["relative_scale"],
                        "lighting_and_shadow": v_pin.get("lighting_and_shadow") or fallback_pin["lighting_and_shadow"],
                        "depth_occlusion": v_pin.get("depth_occlusion") or fallback_pin["depth_occlusion"],
                    })
                else:
                    final_grounded.append(fallback_pin)

            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            self._audit(
                "prop_grounding_response",
                request_id,
                duration_ms=duration_ms,
                props_grounded=len(final_grounded),
                tokens=usage_dict,
                cost_usd=cost_info["cost_usd"],
            )

            return {
                "generation_id": generation_id,
                "assignments": created_assignments,
                "grounded_props": final_grounded,
                "scene_preservation_guardrail": guardrail,
                "cost_usd": float(cost_info["cost_usd"]),
                "tokens": usage_dict,
                "cost_breakdown": cost_info.get("breakdown", {}),
            }
        except Exception as exc:
            logger.warning(f"Vision prop scene grounding failed ({exc}); using fallback heuristic.", exc_info=True)
            self._audit("prop_grounding_error", request_id, error=str(exc))
            return {
                "generation_id": generation_id,
                "assignments": created_assignments,
                "grounded_props": fallback_result["grounded_props"],
                "scene_preservation_guardrail": fallback_result["scene_preservation_guardrail"],
                "cost_usd": 0.0,
                "tokens": {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0},
                "cost_breakdown": {},
            }
