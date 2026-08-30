import os
import io
import json
import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image, ImageFilter
from google import genai
from google.genai import types

from app.db.database import DatabaseManager
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
    Service responsible for wardrobe management: lookbook segmentation, feature extraction,
    spatial subject grounding, and garment upscale processing.
    Composes ImageGenerator, DatabaseManager, and TelemetryLogger.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_key: str,
        storage_dir: str,
        vision_model: str = "gemini-3.5-flash-lite",
        imagen_model: str = "gemini-3.1-flash-image",
        audit_path: Optional[str] = None,
        client: Optional[genai.Client] = None,
        image_generator: Optional[ImageGenerator] = None,
        generation_service: Optional[Any] = None,
        telemetry: Optional[TelemetryLogger] = None,
    ):
        self.db = db_manager
        self.db_manager = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir
        self.vision_model = vision_model
        self.imagen_model = imagen_model
        self.audit_path = audit_path
        self.client = client or genai.Client(api_key=api_key)
        self.image_generator = image_generator
        self._generation_service = generation_service
        self.telemetry = telemetry or TelemetryLogger(
            audit_path=self.audit_path,
            component="wardrobe",
            storage_dir=self.storage_dir,
        )

        self.sources_dir = os.path.join(storage_dir, "wardrobe", "sources")
        self.items_dir = os.path.join(storage_dir, "wardrobe", "items")
        os.makedirs(self.sources_dir, exist_ok=True)
        os.makedirs(self.items_dir, exist_ok=True)

    def set_generation_service(self, generation_service: Any) -> None:
        self._generation_service = generation_service
        if hasattr(generation_service, "image_generator"):
            self.image_generator = generation_service.image_generator

    @property
    def generation_service(self) -> Any:
        return self._generation_service

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

    async def _generate_content_async(
        self, contents: List[Any], config: Optional[Any] = None, vision_model: Optional[str] = None
    ) -> Any:
        active_model = vision_model or self.vision_model
        kwargs: Dict[str, Any] = {"model": active_model, "contents": contents}
        if config is not None:
            kwargs["config"] = config

        if hasattr(self.client, "models") and hasattr(self.client.models, "generate_content"):
            gen_func = self.client.models.generate_content
            if asyncio.iscoroutinefunction(gen_func):
                return await gen_func(**kwargs)
            return await asyncio.to_thread(gen_func, **kwargs)

        raise RuntimeError("Client missing models.generate_content")

    async def extract_garment_features(
        self,
        crop_bytes: bytes,
        label: str,
        category: str,
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extracts exact text/slogans, graphic artwork descriptions, colors, and fabric textures.
        """
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
            response = await self._generate_content_async(contents, config=config, vision_model=active_model)
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

    async def segment_and_save_sheet(
        self,
        image_bytes: bytes,
        original_filename: str = "wardrobe_sheet.png",
        vision_model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Segments a multi-garment sheet image, crops detected items, and extracts detailed features.
        """
        active_model = vision_model or self.vision_model
        sheet_id = f"sheet_{uuid.uuid4().hex[:8]}"
        request_id = f"seg_{uuid.uuid4().hex}"
        logger.info(f"Segmenting wardrobe sheet {sheet_id} ({len(image_bytes)} bytes) using vision model '{active_model}'")

        safe_ext = os.path.splitext(original_filename)[1] or ".png"
        source_filename = f"{sheet_id}_source{safe_ext}"
        source_filepath = os.path.join(self.sources_dir, source_filename)
        with open(source_filepath, "wb") as f:
            f.write(image_bytes)

        image_part = to_image_part(image_bytes)
        contents = [image_part, WARDROBE_SEGMENTATION_PROMPT]
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=WardrobeSegmentationResult,
        )

        self._audit(
            "wardrobe_segmentation_request",
            request_id,
            sheet_id=sheet_id,
            model=active_model,
            bytes=len(image_bytes),
        )

        try:
            response = await self._generate_content_async(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            logger.info(f"Gemini vision response received for sheet {sheet_id}: {raw_text[:200]}...")
        except Exception as exc:
            logger.error(f"Gemini vision segmentation error: {exc}", exc_info=True)
            self._audit("wardrobe_segmentation_error", request_id, model=active_model, error=str(exc))
            raw_text = "{}"

        detected_items = []
        parsed = parse_json_safely(raw_text, default={})
        if isinstance(parsed, dict) and "items" in parsed:
            detected_items = parsed["items"]
        elif isinstance(parsed, list):
            detected_items = parsed

        base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        img_w, img_h = base_img.size

        if not detected_items:
            logger.info("No items detected by vision model; fallback to full-sheet card.")
            base_title = os.path.splitext(original_filename)[0].replace("_", " ").title()
            detected_items = [
                {
                    "label": base_title or "Garment Set",
                    "category": "full_outfit",
                    "box_2d": [0.0, 0.0, 1.0, 1.0],
                }
            ]

        prepared_crops = []
        for idx, item in enumerate(detected_items):
            raw_box = item.get("box_2d") or item.get("bbox") or item.get("bounding_box") or item.get("box")
            norm_box = self._normalize_bbox(raw_box, img_w, img_h)
            if not norm_box:
                continue

            ymin, xmin, ymax, xmax = norm_box
            label = item.get("label") or f"Garment {idx + 1}"
            category = (item.get("category") or "tops").lower()
            if category not in ["outerwear", "tops", "bottoms", "footwear", "accessories", "full_outfit"]:
                category = "tops"

            pad_y = (ymax - ymin) * 0.02
            pad_x = (xmax - xmin) * 0.02
            crop_ymin = max(0.0, ymin - pad_y)
            crop_xmin = max(0.0, xmin - pad_x)
            crop_ymax = min(1.0, ymax + pad_y)
            crop_xmax = min(1.0, xmax + pad_x)

            left = int(crop_xmin * img_w)
            top = int(crop_ymin * img_h)
            right = int(crop_xmax * img_w)
            bottom = int(crop_ymax * img_h)

            if right <= left or bottom <= top:
                continue

            cropped_img = base_img.crop((left, top, right, bottom))
            item_id = f"item_{uuid.uuid4().hex[:8]}"
            cropped_filename = f"{item_id}.png"
            cropped_filepath = os.path.join(self.items_dir, cropped_filename)

            crop_buf = io.BytesIO()
            cropped_img.save(crop_buf, format="PNG")
            crop_bytes = crop_buf.getvalue()

            with open(cropped_filepath, "wb") as f:
                f.write(crop_bytes)

            prepared_crops.append({
                "item_id": item_id,
                "label": label,
                "category": category,
                "norm_box": [ymin, xmin, ymax, xmax],
                "cropped_filepath": cropped_filepath,
                "crop_bytes": crop_bytes,
            })

        extraction_tasks = [
            self.extract_garment_features(
                crop_bytes=item["crop_bytes"],
                label=item["label"],
                category=item["category"],
                vision_model=active_model,
            )
            for item in prepared_crops
        ]
        extracted_features_list = await asyncio.gather(*extraction_tasks, return_exceptions=True)

        usage_dict = extract_usage_metadata(response if 'response' in locals() else None)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )
        seg_cost_total = float(cost_info.get("cost_usd", 0.0))
        seg_tokens_total = int(usage_dict.get("total_token_count", 0))

        num_items = max(len(prepared_crops), 1)
        per_item_seg_cost = round(seg_cost_total / num_items, 6)
        per_item_seg_tokens = int(seg_tokens_total / num_items)

        created_cards: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for idx, item in enumerate(prepared_crops):
            item_id = item["item_id"]
            label = item["label"]
            category = item["category"]
            ymin, xmin, ymax, xmax = item["norm_box"]
            cropped_filepath = item["cropped_filepath"]
            crop_bytes = item["crop_bytes"]

            feat_res = extracted_features_list[idx] if idx < len(extracted_features_list) else {}
            extracted_details = dict(feat_res) if isinstance(feat_res, dict) else {}
            feat_cost = float(extracted_details.pop("_cost_usd", 0.0))
            feat_tokens = int(extracted_details.pop("_tokens", 0))

            initial_cost = round(per_item_seg_cost + feat_cost, 6)
            initial_tokens = per_item_seg_tokens + feat_tokens

            item_record = {
                "id": item_id,
                "source_image_path": source_filepath,
                "label": label,
                "category": category,
                "cropped_image_path": cropped_filepath,
                "upscaled_image_path": None,
                "upscale_status": "pending",
                "upscale_error": None,
                "bbox_json": json.dumps([ymin, xmin, ymax, xmax]),
                "extracted_details_json": json.dumps(extracted_details) if extracted_details else None,
                "cost_usd": initial_cost,
                "tokens": initial_tokens,
                "created_at": now_iso,
            }
            await self.db.create_wardrobe_item(item_record)

            created_cards.append({
                "id": item_id,
                "label": label,
                "category": category,
                "image_url": f"/api/wardrobe/items/{item_id}/image",
                "upscaled_image_url": f"/api/wardrobe/items/{item_id}/upscaled-image",
                "source_image_url": f"/api/wardrobe/sources/{source_filename}",
                "bbox": [ymin, xmin, ymax, xmax],
                "extracted_details": extracted_details,
                "cost_usd": initial_cost,
                "tokens": initial_tokens,
                "created_at": now_iso,
                "upscale_status": "pending",
                "is_upscaled": False,
            })

            asyncio.create_task(
                self.upscale_garment_background(
                    item_id=item_id,
                    crop_bytes=crop_bytes,
                    label=label,
                    category=category,
                    extracted_details=extracted_details,
                )
            )

        self._audit(
            "wardrobe_segmentation_response",
            request_id,
            sheet_id=sheet_id,
            model=active_model,
            items_extracted=len(created_cards),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return created_cards

    async def upscale_garment_background(
        self,
        item_id: str,
        crop_bytes: bytes,
        label: str,
        category: str,
        extracted_details: Optional[Dict[str, Any]] = None,
        imagen_model: Optional[str] = None,
    ) -> None:
        """
        Enhances and upscales an individual garment crop using Gemini Interactions API (4K).
        """
        active_model = imagen_model or self.imagen_model or "gemini-3.1-flash-image"
        request_id = f"upscale_{uuid.uuid4().hex[:8]}"
        started = time.perf_counter()
        logger.info(f"Starting background AI 4K upscale for garment '{item_id}' ({label}, {category}) using '{active_model}'")

        await self.db.update_wardrobe_item_upscale(
            item_id=item_id,
            upscaled_image_path=None,
            upscale_status="processing",
        )

        details_lines = []
        if extracted_details:
            if extracted_details.get("has_text_or_logo") and extracted_details.get("exact_text_content"):
                text_content = extracted_details["exact_text_content"]
                text_str = ", ".join([f'"{t}"' for t in text_content]) if isinstance(text_content, list) else str(text_content)
                details_lines.append(f"- EXACT VISIBLE TEXT & SLOGANS (100% SPELLING LOCK): {text_str}")
            if extracted_details.get("logo_and_print_placement"):
                details_lines.append(f"- PRINT & LOGO PLACEMENT: {extracted_details['logo_and_print_placement']}")
            if extracted_details.get("has_graphic_or_print") and extracted_details.get("graphic_description"):
                details_lines.append(f"- GRAPHIC ARTWORK / MOTIF DESCRIPTION: {extracted_details['graphic_description']}")
            if extracted_details.get("fabric_texture"):
                details_lines.append(f"- FABRIC TEXTURE & WEAVE: {extracted_details['fabric_texture']}")
            if extracted_details.get("hardware_and_details"):
                details_lines.append(f"- HARDWARE & CONSTRUCTION DETAILS: {extracted_details['hardware_and_details']}")

        extracted_prompt_block = ("\nEXTRACTED SPECIFICATIONS & GRAPHIC LOCKS:\n" + "\n".join(details_lines)) if details_lines else ""

        prompt_text = (
            GARMENT_UPSCALE_SYSTEM_PROMPT
            .replace("{LABEL}", label)
            .replace("{CATEGORY}", category)
            .replace("{EXTRACTED_DETAILS_PROMPT}", extracted_prompt_block)
        )

        upscale_neg_prompt = (
            "blurry, low quality, artifacts, watermark, distorted text, misspelled words, altered logos, "
            "scrambled letters, generic replacement graphics, fake text, distorted prints, cropped, cut off, "
            "noise, jpeg artifacts, duplicate limbs, mannequin head, face"
        )

        try:
            upscale_cost = 0.0
            upscale_tokens = 0
            if self.image_generator is not None:
                enhanced_bytes = await self.image_generator.generate(
                    prompt=prompt_text,
                    negative_prompt=upscale_neg_prompt,
                    aspect_ratio="1:1",
                    reference_images=[crop_bytes],
                    audit_request_id=request_id,
                    model=active_model,
                )
                upscale_metrics = getattr(self.image_generator, "last_call_metrics", {})
                upscale_cost = float(upscale_metrics.get("cost_usd", 0.0))
                upscale_tokens = int(upscale_metrics.get("total_token_count", 0))
            elif self._generation_service is not None and hasattr(self._generation_service, "_call_image_model"):
                enhanced_bytes = await self._generation_service._call_image_model(
                    prompt=prompt_text,
                    negative_prompt=upscale_neg_prompt,
                    aspect_ratio="1:1",
                    reference_image_bytes=crop_bytes,
                    audit_request_id=request_id,
                    model_name=active_model,
                )
                upscale_metrics = getattr(self._generation_service, "_last_call_metrics", {})
                upscale_cost = float(upscale_metrics.get("cost_usd", 0.0))
                upscale_tokens = int(upscale_metrics.get("total_token_count", 0))
            else:
                raise RuntimeError("Image generator instance not available for garment upscale.")

            pil_img = Image.open(io.BytesIO(enhanced_bytes))
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGBA")

            upscaled_filename = f"{item_id}_upscaled.png"
            upscaled_filepath = os.path.join(self.items_dir, upscaled_filename)

            buf = io.BytesIO()
            pil_img.save(buf, format="PNG", dpi=(600, 600))
            with open(upscaled_filepath, "wb") as f:
                f.write(buf.getvalue())

            await self.db.update_wardrobe_item_upscale(
                item_id=item_id,
                upscaled_image_path=upscaled_filepath,
                upscale_status="completed",
                cost_usd=upscale_cost,
                tokens=upscale_tokens,
            )
            self._audit(
                "wardrobe_upscale_success",
                request_id,
                item_id=item_id,
                label=label,
                model=active_model,
                tokens=upscale_tokens,
                cost_usd=upscale_cost,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            logger.info(f"AI 4K upscale for garment '{item_id}' successfully saved to '{upscaled_filepath}' in {time.perf_counter() - started:.2f}s (cost=${upscale_cost:.4f}, tokens={upscale_tokens})")
        except Exception as exc:
            logger.warning(f"AI garment upscale failed for '{item_id}' ({exc}); applying high-resolution Lanczos fallback.", exc_info=True)
            try:
                pil_crop = Image.open(io.BytesIO(crop_bytes))
                target_size = (max(pil_crop.width * 4, 3840), max(pil_crop.height * 4, 3840))
                upscaled_crop = pil_crop.resize(target_size, Image.Resampling.LANCZOS)
                upscaled_crop = upscaled_crop.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

                upscaled_filename = f"{item_id}_upscaled.png"
                upscaled_filepath = os.path.join(self.items_dir, upscaled_filename)
                buf = io.BytesIO()
                upscaled_crop.save(buf, format="PNG", dpi=(600, 600))
                with open(upscaled_filepath, "wb") as f:
                    f.write(buf.getvalue())

                await self.db.update_wardrobe_item_upscale(
                    item_id=item_id,
                    upscaled_image_path=upscaled_filepath,
                    upscale_status="completed",
                    cost_usd=0.0,
                    tokens=0,
                )
                self._audit(
                    "wardrobe_upscale_fallback_success",
                    request_id,
                    item_id=item_id,
                    label=label,
                    error=str(exc),
                )
            except Exception as fallback_err:
                logger.error(f"Fallback upscaling failed for '{item_id}': {fallback_err}")
                await self.db.update_wardrobe_item_upscale(
                    item_id=item_id,
                    upscaled_image_path=None,
                    upscale_status="failed",
                    upscale_error=str(exc),
                )
                self._audit(
                    "wardrobe_upscale_error",
                    request_id,
                    item_id=item_id,
                    error=str(exc),
                )

    async def detect_clothing_regions(
        self, image_bytes: bytes, vision_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyzes a generated image to detect subject clothing regions with bounding boxes.
        """
        active_model = vision_model or self.vision_model
        logger.info(f"Detecting clothing regions for auto-mask preview using {active_model}...")

        image_part = to_image_part(image_bytes)
        contents = [image_part, CLOTHING_REGION_DETECTION_PROMPT]
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=ClothingRegionDetectionResult,
        )

        raw_text = "{}"
        try:
            response = await self._generate_content_async(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            logger.info(f"Clothing region detection response received: {raw_text[:200]}...")
        except Exception as exc:
            logger.error(f"Failed to detect clothing regions: {exc}")

        usage_dict = extract_usage_metadata(response if 'response' in locals() else None)
        cost_info = calculate_cost(
            model=active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
        )

        detected = []
        parsed = parse_json_safely(raw_text, default={})
        if isinstance(parsed, dict) and "regions" in parsed:
            detected = parsed["regions"]
        elif isinstance(parsed, list):
            detected = parsed

        base_img = Image.open(io.BytesIO(image_bytes))
        img_w, img_h = base_img.size

        regions: List[Dict[str, Any]] = []
        for idx, reg in enumerate(detected):
            raw_box = reg.get("box_2d") or reg.get("bbox") or reg.get("bounding_box")
            norm_box = self._normalize_bbox(raw_box, img_w, img_h)
            if not norm_box:
                continue

            label = reg.get("label") or f"Region {idx + 1}"
            category = (reg.get("category") or "tops").lower()
            reg_id = reg.get("id") or f"region_{idx + 1}"

            regions.append({
                "id": reg_id,
                "label": label,
                "category": category,
                "bbox": norm_box,
            })

        self._audit(
            "clothing_regions_detected",
            f"reg_{uuid.uuid4().hex[:8]}",
            model=active_model,
            regions_count=len(regions),
            tokens=usage_dict,
            cost_usd=cost_info["cost_usd"],
        )

        return regions

    async def list_items(self) -> List[Dict[str, Any]]:
        """Lists all active wardrobe items."""
        raw_items = await self.db.list_wardrobe_items()
        cards = []
        for item in raw_items:
            is_upscaled = bool(item.get("upscaled_image_path") and item.get("upscale_status") == "completed")
            cards.append({
                "id": item["id"],
                "label": item["label"],
                "category": item.get("category", "tops"),
                "image_url": f"/api/wardrobe/items/{item['id']}/image",
                "upscaled_image_url": f"/api/wardrobe/items/{item['id']}/upscaled-image" if item.get("upscaled_image_path") else None,
                "source_image_url": f"/api/wardrobe/sources/{os.path.basename(item['source_image_path'])}" if item.get("source_image_path") else None,
                "bbox": item.get("bbox"),
                "extracted_details": item.get("extracted_details"),
                "created_at": item.get("created_at"),
                "upscale_status": item.get("upscale_status", "completed" if is_upscaled else "pending"),
                "is_upscaled": is_upscaled,
                "cost_usd": float(item.get("cost_usd") or 0.0),
                "tokens": int(item.get("tokens") or 0),
            })
        return cards

    async def delete_item(self, item_id: str) -> bool:
        """Deletes a wardrobe item, removes its cached images from disk, and cascades assignments."""
        deleted_item = await self.db.delete_wardrobe_item(item_id)
        if not deleted_item:
            return False

        for path_key in ("cropped_image_path", "upscaled_image_path"):
            filepath = deleted_item.get(path_key)
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted file {filepath} on garment delete")
                except OSError as err:
                    logger.warning(f"Failed to remove file {filepath}: {err}")

        self._audit(
            "wardrobe_item_deleted",
            f"del_{uuid.uuid4().hex[:8]}",
            item_id=item_id,
            label=deleted_item.get("label"),
        )
        return True

    async def delete_all_items(self) -> int:
        """Deletes all wardrobe items, removes all item image files from disk, and cascades assignments."""
        deleted_items = await self.db.delete_all_wardrobe_items()
        for item in deleted_items:
            for path_key in ("cropped_image_path", "upscaled_image_path"):
                filepath = item.get(path_key)
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.info(f"Deleted file {filepath} on clear wardrobe")
                    except OSError as err:
                        logger.warning(f"Failed to remove file {filepath}: {err}")

        self._audit(
            "wardrobe_all_items_deleted",
            f"del_all_{uuid.uuid4().hex[:8]}",
            count=len(deleted_items),
        )
        return len(deleted_items)

    def _heuristic_spatial_grounding(self, assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
        grounded_pins = []
        for asgn in assignments:
            pin_num = asgn.get("pin_number", 1)
            drop_pos = asgn.get("drop_position") or {}
            x = float(drop_pos.get("x", 0.5)) if isinstance(drop_pos, dict) else 0.5
            y = float(drop_pos.get("y", 0.5)) if isinstance(drop_pos, dict) else 0.5
            cat = (asgn.get("category") or "tops").lower()
            label = asgn.get("item_label") or asgn.get("target_description") or "garment"

            if x < 0.35:
                h_desc = "on the left side of the frame"
                quad_h = "left"
            elif x > 0.65:
                h_desc = "on the right side of the frame"
                quad_h = "right"
            else:
                h_desc = "in the center of the frame"
                quad_h = "center"

            if y < 0.28 or any(w in label.lower() for w in ["hat", "cap", "beanie", "sunglass"]):
                body_loc = "head and hair region"
                quad_v = "upper"
            elif y > 0.68 or cat in ["bottoms", "footwear"]:
                body_loc = "lower body and legs region"
                quad_v = "lower"
            else:
                body_loc = "upper torso and chest region"
                quad_v = "mid"

            spatial_anchor = f"{quad_v}-{quad_h} quadrant (x: {round(x*100)}%, y: {round(y*100)}%)"
            target_subject = f"The subject located {h_desc}"

            grounded_pins.append({
                "pin_number": pin_num,
                "target_subject": target_subject,
                "body_location": body_loc,
                "spatial_anchor": spatial_anchor,
                "current_attire": "the existing clothing/styling at this position",
            })

        return {
            "grounded_pins": grounded_pins,
            "unmodified_subjects_guardrail": "Strictly preserve all other subjects and non-targeted character features, clothing, and hairstyles in the scene exactly as shown in the reference image without any alterations.",
        }

    async def ground_wardrobe_pins(
        self,
        image_bytes: bytes,
        assignments: List[Dict[str, Any]],
        vision_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Inspects the base image and user drop pin coordinates with Gemini Vision to identify
        the specific subject, body location, and non-target subject preservation guardrails.
        """
        if not assignments:
            return {
                "grounded_pins": [],
                "unmodified_subjects_guardrail": "Preserve all subjects and background elements exactly as shown.",
            }

        active_model = vision_model or self.vision_model
        fallback_result = self._heuristic_spatial_grounding(assignments)
        request_id = f"ground_{uuid.uuid4().hex}"
        started = time.perf_counter()

        pin_lines = []
        for asgn in assignments:
            pin_num = asgn.get("pin_number", 1)
            drop_pos = asgn.get("drop_position") or {}
            x = float(drop_pos.get("x", 0.5)) if isinstance(drop_pos, dict) else 0.5
            y = float(drop_pos.get("y", 0.5)) if isinstance(drop_pos, dict) else 0.5
            label = asgn.get("item_label") or asgn.get("target_description") or "Garment"
            cat = asgn.get("category") or "tops"
            pin_lines.append(
                f"- Pin #{pin_num}: coordinate x={round(x*100)}%, y={round(y*100)}% | Assigned Garment: \"{label}\" ({cat})"
            )

        pin_text = "DROPPED GARMENT PINS TO ANALYZE:\n" + "\n".join(pin_lines)
        image_part = to_image_part(image_bytes)
        contents = [
            image_part,
            pin_text,
            SUBJECT_GROUNDING_PROMPT,
        ]

        self._audit(
            "wardrobe_grounding_request",
            request_id,
            pins_count=len(assignments),
            model=active_model,
        )

        try:
            response = await self._generate_content_async(contents, vision_model=active_model)
            usage_dict = extract_usage_metadata(response)
            cost_info = calculate_cost(
                model=active_model,
                prompt_tokens=usage_dict["prompt_token_count"],
                candidates_tokens=usage_dict["candidates_token_count"],
            )
            raw_text = getattr(response, "text", "") or ""
            parsed = parse_json_safely(raw_text, default={})

            grounded_list = parsed.get("grounded_pins", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            guardrail = (parsed.get("unmodified_subjects_guardrail") if isinstance(parsed, dict) else None) or fallback_result["unmodified_subjects_guardrail"]

            grounded_by_pin = {g.get("pin_number"): g for g in grounded_list if isinstance(g, dict)}
            final_grounded = []

            for fallback_pin in fallback_result["grounded_pins"]:
                p_num = fallback_pin["pin_number"]
                if p_num in grounded_by_pin:
                    v_pin = grounded_by_pin[p_num]
                    final_grounded.append({
                        "pin_number": p_num,
                        "target_subject": v_pin.get("target_subject") or fallback_pin["target_subject"],
                        "body_location": v_pin.get("body_location") or fallback_pin["body_location"],
                        "spatial_anchor": v_pin.get("spatial_anchor") or fallback_pin["spatial_anchor"],
                        "current_attire": v_pin.get("current_attire") or fallback_pin["current_attire"],
                    })
                else:
                    final_grounded.append(fallback_pin)

            self._audit(
                "wardrobe_grounding_response",
                request_id,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                pins_grounded=len(final_grounded),
                tokens=usage_dict,
                cost_usd=cost_info["cost_usd"],
            )

            return {
                "grounded_pins": final_grounded,
                "unmodified_subjects_guardrail": guardrail,
            }
        except Exception as exc:
            logger.warning(f"Vision subject grounding pre-pass failed ({exc}); using fallback heuristic.", exc_info=True)
            self._audit("wardrobe_grounding_error", request_id, error=str(exc))
            return fallback_result
