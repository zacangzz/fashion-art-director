import io
import os
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from PIL import Image

from app.db.database import DatabaseManager
from app.services.image_generator import ImageGenerator
from app.utils.image_utils import (
    ASPECT_RATIO_RESOLUTIONS,
    resize_and_crop,
)
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger

logger = get_logger("export_service")

DEFAULT_UPSCALE_PROMPT = (
    "Restore, de-noise, and enhance the provided reference image as an authentic raw photo. "
    "Maximize optical resolution and crisp focus while strictly preserving original facial structures, "
    "visible skin pores, natural skin texture, realistic teeth texture, natural tooth alignment, authentic gum line, subtle dental translucency, "
    "minor skin blemishes, natural light, and overall composition. "
    "Focus on ensuring that all clothing, garments, fabric weaves, seams, and material textures are clear, tactile, and richly detailed."
)

BUNDLE_PRESETS: Dict[str, tuple[int, int]] = {
    "01_SocialFeed_1080x1350": (1080, 1350),      # 4:5 Social Feed
    "02_StoryMobile_1080x1920": (1080, 1920),     # 9:16 Story / Mobile
    "03_WideBanner_1440x780": (1440, 780),        # ~1.85:1 Banner
    "04_Square_1440x1440": (1440, 1440),          # 1:1 High-Res Square
    "05_LandscapeDisplay_1730x960": (1730, 960),  # ~1.8:1 Landscape
    "06_4KUHD_Landscape_3840x2160": (3840, 2160), # 16:9 4K UHD Landscape
    "07_4KPortrait_2160x3840": (2160, 3840),     # 9:16 4K Vertical / Poster
    "08_4KSquare_2160x2160": (2160, 2160),        # 1:1 4K Square Print
}


class ExportService:
    """
    Service responsible for high-resolution 4K master restoration exports and archive bundling.
    Composes ImageGenerator, DatabaseManager, and TelemetryLogger.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        image_generator: Optional[ImageGenerator] = None,
        storage_dir: Optional[str] = None,
        audit_path: Optional[str] = None,
        generation_service: Optional[Any] = None,
    ):
        self._db = db_manager
        self.db = db_manager
        self.image_generator = image_generator
        if self.image_generator is None and generation_service is not None:
            self.image_generator = getattr(generation_service, "image_generator", None) or generation_service
        self.storage_dir = storage_dir or "./storage"
        self.telemetry = TelemetryLogger(
            audit_path or os.path.join(self.storage_dir, "logs", "generation_audit.jsonl")
        )

    @property
    def db_manager(self) -> DatabaseManager:
        return self._db

    @db_manager.setter
    def db_manager(self, value: DatabaseManager) -> None:
        self._db = value
        self.db = value

    def _audit(self, event_name: str, request_id: str, **kwargs):
        try:
            self.telemetry.record_event(
                component="export_service",
                event=event_name,
                request_id=request_id,
                **kwargs,
            )
        except Exception as err:
            logger.warning(f"Could not write export audit event: {err}")

    async def prepare_export_master(
        self,
        generation_id: str,
        prompt_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sends the chosen generation image to Gemini with an image restoration and upscale prompt,
        saves the high-quality 4K master file, and links the new generation record to parent generation_id.
        """
        audit_request_id = f"req_export_{uuid.uuid4().hex[:8]}"
        self._audit("export_prepare_started", audit_request_id, source_generation_id=generation_id)

        gen = await self.db.get_generation(generation_id)
        if not gen:
            self._audit("export_prepare_error", audit_request_id, error=f"Generation '{generation_id}' not found")
            raise ValueError(f"Generation '{generation_id}' not found")

        master_path = gen.get("master_image_path")
        if not master_path or not os.path.exists(master_path):
            self._audit("export_prepare_error", audit_request_id, error=f"Master image file not found at '{master_path}'")
            raise FileNotFoundError(f"Master image file for generation '{generation_id}' not found at path '{master_path}'")

        with open(master_path, "rb") as f:
            source_image_bytes = f.read()

        aspect_ratio = gen.get("aspect_ratio", "2:3")
        seed = gen.get("seed", 4289102)
        negative_prompt = gen.get("negative_prompt", "")
        prompt_text = (prompt_override or "").strip() or DEFAULT_UPSCALE_PROMPT

        if not self.image_generator:
            raise RuntimeError("ImageGenerator instance is required for AI master export restoration.")

        logger.info(f"Preparing AI upscale export master for gen_id={generation_id}, aspect_ratio={aspect_ratio}")
        
        if hasattr(self.image_generator, "generate"):
            enhanced_image_bytes = await self.image_generator.generate(
                prompt=prompt_text,
                negative_prompt=negative_prompt,
                seed=seed,
                aspect_ratio=aspect_ratio,
                reference_images=[source_image_bytes],
                audit_request_id=audit_request_id,
            )
        elif hasattr(self.image_generator, "_call_image_model"):
            enhanced_image_bytes = await self.image_generator._call_image_model(
                prompt=prompt_text,
                negative_prompt=negative_prompt,
                seed=seed,
                aspect_ratio=aspect_ratio,
                reference_image_bytes=source_image_bytes,
                audit_request_id=audit_request_id,
                reference_image_path=master_path,
            )
        else:
            raise RuntimeError("Unsupported image generator instance for export restoration.")

        # Process and ensure 4K Master resolution
        target_4k = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio, (3840, 3840))
        try:
            pil_img = Image.open(io.BytesIO(enhanced_image_bytes))
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGB")

            curr_w, curr_h = pil_img.size
            if target_4k and (curr_w < target_4k[0] or curr_h < target_4k[1]):
                logger.info(f"Upscaling restored image from {curr_w}x{curr_h} to 4K target {target_4k[0]}x{target_4k[1]}")
                pil_img = pil_img.resize(target_4k, Image.Resampling.LANCZOS)

            img_width, img_height = pil_img.size
            buffer = io.BytesIO()
            pil_img.save(buffer, format="PNG", dpi=(600, 600))
            final_bytes = buffer.getvalue()
        except Exception as img_err:
            logger.warning(f"Error processing image dimensions: {img_err}")
            final_bytes = enhanced_image_bytes
            img_width, img_height = target_4k if target_4k else (3840, 3840)

        export_gen_id = f"gen_export_{uuid.uuid4().hex[:8]}"
        out_filename = f"{export_gen_id}_master.png"
        out_dir = os.path.join(self.storage_dir, "generations")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, out_filename)

        with open(out_path, "wb") as f:
            f.write(final_bytes)

        created_at_str = datetime.now(timezone.utc).isoformat()
        schema_json = {
            "is_export_master": True,
            "source_generation_id": generation_id,
            "task": "image_restoration_upscale",
            "aspect_ratio": aspect_ratio,
        }

        export_record = {
            "id": export_gen_id,
            "parent_id": generation_id,
            "moodboard_id": gen.get("moodboard_id"),
            "is_baseline": False,
            "created_at": created_at_str,
            "prompt": prompt_text,
            "compiled_prompt": prompt_text,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "schema_json": json.dumps(schema_json),
            "tags_snapshot": gen.get("tags_snapshot", "[]"),
            "master_image_path": out_path,
            "aspect_ratio": aspect_ratio,
            "resolution_width": img_width,
            "resolution_height": img_height,
        }

        await self.db.create_generation(export_record)

        self._audit(
            "export_prepare_completed",
            audit_request_id,
            export_generation_id=export_gen_id,
            source_generation_id=generation_id,
            dimensions={"width": img_width, "height": img_height},
            bytes=len(enhanced_image_bytes),
        )

        return {
            "generation_id": export_gen_id,
            "parent_id": generation_id,
            "seed": seed,
            "compiled_prompt": prompt_text,
            "negative_prompt": negative_prompt,
            "master_image_url": f"/api/images/{out_filename}",
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": img_width, "height": img_height},
            "created_at": created_at_str,
        }

    async def create_bundle_zip(self, generation_id: str) -> bytes:
        """
        Looks up generation metadata by generation_id, generates all resolution presets,
        and packs them into an in-memory ZIP bundle with schema.json and metadata.json.
        """
        gen = await self.db.get_generation(generation_id)
        if not gen:
            raise ValueError(f"Generation '{generation_id}' not found")

        master_path = gen.get("master_image_path")
        if not master_path or not os.path.exists(master_path):
            raise FileNotFoundError(f"Master image file for generation '{generation_id}' not found at path '{master_path}'")

        master_img = Image.open(master_path)
        if master_img.mode not in ("RGB", "RGBA"):
            master_img = master_img.convert("RGB")

        presets_dict = {}
        for preset_name, (w, h) in BUNDLE_PRESETS.items():
            processed_img = resize_and_crop(master_img, w, h)
            buf = io.BytesIO()
            processed_img.save(buf, format="PNG", dpi=(600, 600))
            presets_dict[f"{preset_name}.png"] = buf.getvalue()

        schema_json = gen.get("schema_json", {})
        if isinstance(schema_json, str):
            try:
                schema_json = json.loads(schema_json)
            except json.JSONDecodeError:
                schema_json = {}

        prompt_str = gen.get("compiled_prompt") or gen.get("prompt", "")

        inpaint_meta = schema_json.get("inpaint_metadata") if isinstance(schema_json, dict) else None
        mask_path = inpaint_meta.get("mask_path") if isinstance(inpaint_meta, dict) else None
        if not mask_path or not os.path.exists(mask_path):
            fallback_mask = master_path.replace("_master.png", "_mask.png")
            if os.path.exists(fallback_mask):
                mask_path = fallback_mask

        metadata = {
            "generation_id": gen["id"],
            "parent_id": gen.get("parent_id"),
            "moodboard_id": gen.get("moodboard_id"),
            "is_baseline": gen.get("is_baseline", False),
            "created_at": gen.get("created_at"),
            "prompt": prompt_str,
            "compiled_prompt": prompt_str,
            "negative_prompt": gen.get("negative_prompt", ""),
            "seed": gen.get("seed"),
            "aspect_ratio": gen.get("aspect_ratio", "1:1"),
            "resolution": {
                "width": gen.get("resolution_width", 3840),
                "height": gen.get("resolution_height", 3840),
            },
        }
        if inpaint_meta:
            metadata["inpaint_metadata"] = inpaint_meta

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for filename, data in presets_dict.items():
                zf.writestr(filename, data)
            if mask_path and os.path.exists(mask_path):
                with open(mask_path, "rb") as mf:
                    zf.writestr("inpaint_mask.png", mf.read())
            zf.writestr("schema.json", json.dumps(schema_json, indent=2))
            zf.writestr("metadata.json", json.dumps(metadata, indent=2))

        return zip_buffer.getvalue()
