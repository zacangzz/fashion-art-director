import io
import os
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from PIL import Image

from app.db.database import FirestoreManager, DatabaseManager
from app.services.storage_service import StorageService
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
    Synchronous service responsible for high-resolution 4K master restoration exports
    and in-memory archive bundling.
    Composes ImageGenerator, StorageService, FirestoreManager, and TelemetryLogger.
    """

    def __init__(
        self,
        db_manager: FirestoreManager,
        image_generator: Optional[ImageGenerator] = None,
        storage_service: Optional[StorageService] = None,
        storage_dir: Optional[str] = None,
        audit_path: Optional[str] = None,
        generation_service: Optional[Any] = None,
    ):
        self._db = db_manager
        self.db = db_manager
        self.storage_service = storage_service
        self.image_generator = image_generator
        if self.image_generator is None and generation_service is not None:
            self.image_generator = getattr(generation_service, "image_generator", None) or generation_service
        self.storage_dir = storage_dir or "./storage"
        self.telemetry = TelemetryLogger(
            component="export_service",
        )

    @property
    def db_manager(self) -> FirestoreManager:
        return self._db

    @db_manager.setter
    def db_manager(self, value: FirestoreManager) -> None:
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

    def _load_image_bytes(self, image_path: str) -> bytes:
        if self.storage_service is not None and not os.path.exists(image_path):
            return self.storage_service.download_bytes(image_path)
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                return f.read()
        if self.storage_service is not None:
            return self.storage_service.download_bytes(image_path)
        raise FileNotFoundError(f"Image not found at {image_path}")

    def prepare_export_master(
        self,
        generation_id: str,
        prompt_override: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Sends the chosen generation image to Gemini with an image restoration and upscale prompt,
        saves the high-quality 4K master file in Cloud Storage, and links the new generation record.
        """
        audit_request_id = f"req_export_{uuid.uuid4().hex[:8]}"
        self._audit("export_prepare_started", audit_request_id, source_generation_id=generation_id)

        gen = self.db.get_generation(generation_id)
        if not gen:
            self._audit("export_prepare_error", audit_request_id, error=f"Generation '{generation_id}' not found")
            raise ValueError(f"Generation '{generation_id}' not found")

        source_path = gen.get("master_image_path")
        source_bytes = self._load_image_bytes(source_path)

        prompt = prompt_override or DEFAULT_UPSCALE_PROMPT
        aspect_ratio = gen.get("aspect_ratio", "2:3")
        seed = gen.get("seed", 4289102)

        if not self.image_generator:
            raise RuntimeError("ImageGenerator not configured on ExportService")

        upscaled_bytes = self.image_generator.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            reference_images=[source_bytes],
            seed=seed,
            image_size="4K",
            audit_request_id=audit_request_id,
        )

        export_id = f"export_{uuid.uuid4().hex[:8]}"
        filename = f"{export_id}_4k.png"

        pil_img = Image.open(io.BytesIO(upscaled_bytes))
        width, height = pil_img.size

        if self.storage_service is not None:
            export_storage_path = self.storage_service.upload_bytes(
                user_id=user_id,
                category="generations",
                filename=filename,
                data=upscaled_bytes,
                content_type="image/png",
            )
        else:
            export_path = os.path.join(self.storage_dir, "generations", filename)
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "wb") as f:
                f.write(upscaled_bytes)
            export_storage_path = export_path

        metrics = self.image_generator.last_call_metrics or {}
        call_cost = float(metrics.get("cost_usd", 0.04))
        call_tokens = int(metrics.get("total_token_count", 1500))

        export_record = {
            "id": export_id,
            "parent_id": generation_id,
            "moodboard_id": gen.get("moodboard_id"),
            "is_baseline": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_json": {
                "task": "4k_export_master",
                "source_generation_id": generation_id,
                "prompt": prompt,
            },
            "compiled_prompt": prompt,
            "negative_prompt": "",
            "seed": seed,
            "master_image_path": export_storage_path,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": "gemini-3-pro-image",
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": round(float(gen.get("accumulated_cost_usd", 0.0)) + call_cost, 6),
            "accumulated_tokens": int(gen.get("accumulated_tokens", 0)) + call_tokens,
        }

        self.db.create_generation(user_id=user_id, gen_data=export_record)

        self._audit(
            "export_prepare_success",
            audit_request_id,
            export_id=export_id,
            dimensions={"width": width, "height": height},
            cost_usd=call_cost,
        )

        return {
            "export_generation_id": export_id,
            "source_generation_id": generation_id,
            "master_image_url": f"/api/images/{export_storage_path}",
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "cost_usd": call_cost,
            "tokens": call_tokens,
        }

    def bundle_export_presets(
        self,
        generation_id: str,
        export_format: str = "PNG",
        jpeg_quality: int = 95,
        user_id: str = "local_dev_user",
    ) -> bytes:
        """
        Takes the chosen generation master image, crops and resizes it to all 8 standard publication
        aspect ratios and resolutions, and packages them in-memory into a ZIP archive.
        """
        audit_request_id = f"req_bundle_{uuid.uuid4().hex[:8]}"
        self._audit("export_bundle_started", audit_request_id, generation_id=generation_id)

        gen = self.db.get_generation(generation_id)
        if not gen:
            self._audit("export_bundle_error", audit_request_id, error=f"Generation '{generation_id}' not found")
            raise ValueError(f"Generation '{generation_id}' not found")

        source_path = gen.get("master_image_path")
        source_bytes = self._load_image_bytes(source_path)

        master_img = Image.open(io.BytesIO(source_bytes))
        if master_img.mode != "RGB":
            master_img = master_img.convert("RGB")

        zip_buf = io.BytesIO()
        ext = export_format.lower()
        if ext == "jpeg":
            ext = "jpg"

        with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Include the pristine original master image
            orig_buf = io.BytesIO()
            if ext == "jpg":
                master_img.save(orig_buf, format="JPEG", quality=jpeg_quality)
            else:
                master_img.save(orig_buf, format="PNG")
            zip_file.writestr(f"00_Master_Original_{master_img.width}x{master_img.height}.{ext}", orig_buf.getvalue())

            # 2. Render and package all 8 presets
            for preset_name, (target_w, target_h) in BUNDLE_PRESETS.items():
                cropped = resize_and_crop(master_img, target_w, target_h)
                img_buf = io.BytesIO()
                if ext == "jpg":
                    cropped.save(img_buf, format="JPEG", quality=jpeg_quality)
                else:
                    cropped.save(img_buf, format="PNG")
                zip_file.writestr(f"{preset_name}.{ext}", img_buf.getvalue())

            # 3. Include lineage metadata manifest
            manifest = {
                "generation_id": generation_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "aspect_ratio": gen.get("aspect_ratio"),
                "seed": gen.get("seed"),
                "model_name": gen.get("model_name"),
                "compiled_prompt": gen.get("compiled_prompt"),
                "negative_prompt": gen.get("negative_prompt"),
                "accumulated_cost_usd": gen.get("accumulated_cost_usd"),
                "presets_included": list(BUNDLE_PRESETS.keys()),
            }
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))

        self._audit("export_bundle_success", audit_request_id, presets_count=len(BUNDLE_PRESETS))
        return zip_buf.getvalue()
