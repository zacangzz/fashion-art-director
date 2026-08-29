import os
import io
import json
import uuid
import time
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from PIL import Image
from google import genai
from google.genai import types

from app.db.database import DatabaseManager
from app.schemas.domain import (
    WardrobeSegmentationResult,
    ClothingRegionDetectionResult,
)
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger
from app.utils.prompt_loader import (
    WARDROBE_SEGMENTATION_PROMPT,
    CLOTHING_REGION_DETECTION_PROMPT,
    SUBJECT_GROUNDING_PROMPT,
)
from app.utils.image_utils import to_image_part

logger = get_logger("wardrobe_service")


class WardrobeService:
    def __init__(
        self,
        db_manager: DatabaseManager,
        api_key: str,
        storage_dir: str,
        vision_model: str = "gemini-3.5-flash-lite",
        audit_path: Optional[str] = None,
        client: Optional[genai.Client] = None,
    ):
        self.db = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir
        self.vision_model = vision_model
        self.audit_path = audit_path
        self.client = client or genai.Client(api_key=api_key)
        self.telemetry = TelemetryLogger(
            audit_path=self.audit_path,
            component="wardrobe",
            storage_dir=self.storage_dir,
        )

        # Ensure storage subdirectories exist
        self.sources_dir = os.path.join(storage_dir, "wardrobe", "sources")
        self.items_dir = os.path.join(storage_dir, "wardrobe", "items")
        os.makedirs(self.sources_dir, exist_ok=True)
        os.makedirs(self.items_dir, exist_ok=True)

    def _audit(self, event_type: str, request_id: str, **kwargs):
        if not self.audit_path:
            return
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
        """Strips markdown code fences and whitespace."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    async def _generate_content_async(
        self, contents: List[Any], config: Optional[Any] = None, vision_model: Optional[str] = None
    ) -> Any:
        active_model = vision_model or self.vision_model
        kwargs = {"model": active_model, "contents": contents}
        if config is not None:
            kwargs["config"] = config
        return await asyncio.to_thread(
            self.client.models.generate_content,
            **kwargs,
        )

    def _normalize_bbox(
        self,
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

        # Auto-detect coordinate scale
        max_coord = max(abs(ymin), abs(xmin), abs(ymax), abs(xmax))
        if max_coord > 1.0:
            if max_coord <= 1050.0:
                # Gemini standard 0..1000 coordinate space
                ymin /= 1000.0
                xmin /= 1000.0
                ymax /= 1000.0
                xmax /= 1000.0
            else:
                # Absolute pixel coordinates
                ymin /= float(img_h) if img_h > 0 else 1.0
                xmin /= float(img_w) if img_w > 0 else 1.0
                ymax /= float(img_h) if img_h > 0 else 1.0
                xmax /= float(img_w) if img_w > 0 else 1.0

        # Ensure ymin < ymax and xmin < xmax
        if ymin > ymax:
            ymin, ymax = ymax, ymin
        if xmin > xmax:
            xmin, xmax = xmax, xmin

        # Clamp between 0.0 and 1.0
        ymin = max(0.0, min(1.0, ymin))
        xmin = max(0.0, min(1.0, xmin))
        ymax = max(0.0, min(1.0, ymax))
        xmax = max(0.0, min(1.0, xmax))

        # Check minimal dimension (at least 0.8% in both axes)
        if (ymax - ymin) < 0.008 or (xmax - xmin) < 0.008:
            return None

        return [round(ymin, 4), round(xmin, 4), round(ymax, 4), round(xmax, 4)]

    async def segment_and_save_sheet(
        self,
        image_bytes: bytes,
        original_filename: str = "wardrobe_sheet.png",
        vision_model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Ingests a multi-garment sheet image, runs Gemini vision to detect bounding boxes
        for each item, crops them with PIL, persists to DB, and returns garment cards.
        """
        active_model = vision_model or self.vision_model
        sheet_id = f"sheet_{uuid.uuid4().hex[:8]}"
        request_id = f"seg_{uuid.uuid4().hex}"
        logger.info(f"Segmenting wardrobe sheet {sheet_id} ({len(image_bytes)} bytes) using vision model '{active_model}'")

        # Save original source sheet
        safe_ext = os.path.splitext(original_filename)[1] or ".png"
        source_filename = f"{sheet_id}_source{safe_ext}"
        source_filepath = os.path.join(self.sources_dir, source_filename)
        with open(source_filepath, "wb") as f:
            f.write(image_bytes)

        # Call Gemini Vision to detect items and bounding boxes
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

        # Parse detected items
        cleaned = self._clean_json_text(raw_text)
        detected_items = []
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "items" in parsed:
                detected_items = parsed["items"]
            elif isinstance(parsed, list):
                detected_items = parsed
        except Exception as parse_err:
            logger.warning(f"Could not parse vision JSON response: {parse_err}. Raw: {cleaned}")

        base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        img_w, img_h = base_img.size

        # Fallback if no items detected: treat entire sheet as 1 item
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

        created_cards: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

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

            # Apply subtle 2% padding for clean aesthetic borders
            pad_y = (ymax - ymin) * 0.02
            pad_x = (xmax - xmin) * 0.02
            crop_ymin = max(0.0, ymin - pad_y)
            crop_xmin = max(0.0, xmin - pad_x)
            crop_ymax = min(1.0, ymax + pad_y)
            crop_xmax = min(1.0, xmax + pad_x)

            # Convert to absolute pixel coordinates
            left = int(crop_xmin * img_w)
            top = int(crop_ymin * img_h)
            right = int(crop_xmax * img_w)
            bottom = int(crop_ymax * img_h)

            # Ensure valid bounding box
            if right <= left or bottom <= top:
                continue

            cropped_img = base_img.crop((left, top, right, bottom))
            item_id = f"item_{uuid.uuid4().hex[:8]}"
            cropped_filename = f"{item_id}.png"
            cropped_filepath = os.path.join(self.items_dir, cropped_filename)

            cropped_img.save(cropped_filepath, format="PNG")

            item_record = {
                "id": item_id,
                "source_image_path": source_filepath,
                "label": label,
                "category": category,
                "cropped_image_path": cropped_filepath,
                "bbox_json": json.dumps([ymin, xmin, ymax, xmax]),
                "created_at": now_iso,
            }
            await self.db.create_wardrobe_item(item_record)

            created_cards.append({
                "id": item_id,
                "label": label,
                "category": category,
                "image_url": f"/api/wardrobe/items/{item_id}/image",
                "source_image_url": f"/api/wardrobe/sources/{source_filename}",
                "bbox": [ymin, xmin, ymax, xmax],
                "created_at": now_iso,
            })

        self._audit(
            "wardrobe_segmentation_response",
            request_id,
            sheet_id=sheet_id,
            model=active_model,
            items_extracted=len(created_cards),
        )

        return created_cards

    async def detect_clothing_regions(
        self, image_bytes: bytes, vision_model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyzes a generated image to detect subject clothing regions with bounding boxes.
        Used for auto-mask overlay preview.
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

        base_img = Image.open(io.BytesIO(image_bytes))
        img_w, img_h = base_img.size

        try:
            response = await self._generate_content_async(contents, config=config, vision_model=active_model)
            raw_text = getattr(response, "text", "") or ""
            cleaned = self._clean_json_text(raw_text)
            parsed = json.loads(cleaned)
            regions_raw = parsed.get("regions", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
        except Exception as exc:
            logger.warning(f"Failed to detect clothing regions: {exc}")
            regions_raw = []

        regions = []
        for idx, r in enumerate(regions_raw):
            raw_box = r.get("box_2d") or r.get("bbox") or r.get("bounding_box") or r.get("box")
            norm_box = self._normalize_bbox(raw_box, img_w, img_h) or [0.2, 0.2, 0.8, 0.8]
            reg_id = f"reg_{idx + 1}"
            label = r.get("label") or f"Clothing Region {idx + 1}"
            category = (r.get("category") or "tops").lower()
            regions.append({
                "id": reg_id,
                "label": label,
                "category": category,
                "bbox": norm_box,
            })

        return regions

    async def list_items(self) -> List[Dict[str, Any]]:
        """Lists all active wardrobe items."""
        raw_items = await self.db.list_wardrobe_items()
        cards = []
        for item in raw_items:
            cards.append({
                "id": item["id"],
                "label": item["label"],
                "category": item.get("category", "tops"),
                "image_url": f"/api/wardrobe/items/{item['id']}/image",
                "source_image_url": f"/api/wardrobe/sources/{os.path.basename(item['source_image_path'])}" if item.get("source_image_path") else None,
                "bbox": item.get("bbox"),
                "created_at": item.get("created_at"),
            })
        return cards

    async def delete_item(self, item_id: str) -> bool:
        """Soft-deletes a wardrobe item."""
        return await self.db.delete_wardrobe_item(item_id)

    async def delete_all_items(self) -> int:
        """Soft-deletes all wardrobe items."""
        return await self.db.delete_all_wardrobe_items()

    def _heuristic_spatial_grounding(self, assignments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Deterministic spatial grounding fallback if Vision model fails or is offline.
        Translates normalized (x, y) coordinates and category into descriptive subject/spatial strings.
        """
        grounded_pins = []
        for asgn in assignments:
            pin_num = asgn.get("pin_number", 1)
            drop_pos = asgn.get("drop_position") or {}
            x = float(drop_pos.get("x", 0.5)) if isinstance(drop_pos, dict) else 0.5
            y = float(drop_pos.get("y", 0.5)) if isinstance(drop_pos, dict) else 0.5
            cat = (asgn.get("category") or "tops").lower()
            label = asgn.get("item_label") or asgn.get("target_description") or "garment"

            # Horizontal placement
            if x < 0.35:
                h_desc = "on the left side of the frame"
                quad_h = "left"
            elif x > 0.65:
                h_desc = "on the right side of the frame"
                quad_h = "right"
            else:
                h_desc = "in the center of the frame"
                quad_h = "center"

            # Vertical anatomy
            if y < 0.28 or "hat" in label.lower() or "cap" in label.lower() or "beanie" in label.lower() or "sunglass" in label.lower():
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
        Vision-Assisted Subject Grounding (Pre-pass).
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

        # Build pin summary prompt input
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
            raw_text = getattr(response, "text", "") or ""
            cleaned = self._clean_json_text(raw_text)
            parsed = json.loads(cleaned)

            grounded_list = parsed.get("grounded_pins", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])
            guardrail = (parsed.get("unmodified_subjects_guardrail") if isinstance(parsed, dict) else None) or fallback_result["unmodified_subjects_guardrail"]

            # Merge with fallback to ensure every pin has a grounded description
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
            )

            return {
                "grounded_pins": final_grounded,
                "unmodified_subjects_guardrail": guardrail,
            }
        except Exception as exc:
            logger.warning(f"Vision subject grounding pre-pass failed ({exc}); using fallback heuristic.", exc_info=True)
            self._audit("wardrobe_grounding_error", request_id, error=str(exc))
            return fallback_result
