import io
import json
import os
import zipfile
from app.db.database import DatabaseManager
from app.services.image_transformer import generate_all_presets

class ExportService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def create_bundle_zip(self, generation_id: str) -> bytes:
        """
        Looks up generation metadata by generation_id, generates all 5 resolution presets,
        and packs them into an in-memory ZIP bundle with schema.json and metadata.json.
        """
        gen = await self.db_manager.get_generation(generation_id)
        if not gen:
            raise ValueError(f"Generation '{generation_id}' not found")

        master_path = gen.get("master_image_path")
        if not master_path or not os.path.exists(master_path):
            raise FileNotFoundError(f"Master image file for generation '{generation_id}' not found at path '{master_path}'")

        # Generate all 5 resolution presets in memory
        presets_dict = generate_all_presets(master_path)

        schema_json = gen.get("schema_json", {})
        if isinstance(schema_json, str):
            try:
                schema_json = json.loads(schema_json)
            except json.JSONDecodeError:
                schema_json = {}

        prompt_str = gen.get("compiled_prompt") or gen.get("prompt", "")

        # Check for inpainting mask artifact
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
            "aspect_ratio": gen.get("aspect_ratio", "2:3"),
            "resolution": {
                "width": gen.get("resolution_width", 1440),
                "height": gen.get("resolution_height", 1440),
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

