import os
import io
import uuid
import base64
import random
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from PIL import Image
from google import genai

from app.db.database import FirestoreManager, DatabaseManager
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from app.services.prompt_compiler import (
    PromptCompiler,
    compile_prompt,
    compile_delta_prompt,
    get_modified_categories,
    extract_category_labels,
)
from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger
from app.utils.image_utils import (
    ASPECT_RATIO_RESOLUTIONS,
    analyze_mask_bytes,
    detect_closest_aspect_ratio,
    normalize_interaction_aspect_ratio,
    to_interaction_image_input,
)
from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    WARDROBE_COMPOSITION_SYSTEM_PROMPT,
)

logger = get_logger("generation_service")


class GenerationService:
    """
    Synchronous generation orchestration service for baseline candidates, seed-locked fine-tuning,
    conversational refinement, targeted inpainting, and wardrobe composition.
    Composes ImageGenerator, StorageService, PromptCompiler, FirestoreManager, and TelemetryLogger.
    """

    def __init__(
        self,
        db_manager: FirestoreManager,
        api_key: str,
        storage_dir: Optional[str] = "./storage",
        storage_service: Optional[StorageService] = None,
        model_name: str = "gemini-3-pro-image",
        inpaint_model_name: str = "gemini-3-pro-image",
        audit_path: Optional[Path] = None,
        wardrobe_service: Optional[Any] = None,
        client: Optional[genai.Client] = None,
        image_generator: Optional[ImageGenerator] = None,
        telemetry: Optional[TelemetryLogger] = None,
    ):
        self.db = db_manager
        self.db_manager = db_manager
        self.api_key = api_key
        self.storage_dir = storage_dir or "./storage"
        self.storage_service = storage_service or StorageService(storage_dir=self.storage_dir, environment="local")
        self.model_name = model_name
        self.inpaint_model_name = inpaint_model_name
        self.wardrobe_service = wardrobe_service
        self.client = client or genai.Client(api_key=self.api_key)
        self.telemetry = telemetry or TelemetryLogger(
            component="generation",
        )
        self.prompt_compiler = PromptCompiler()
        self.image_generator = image_generator or ImageGenerator(
            client=self.client,
            default_model=self.model_name,
            telemetry=self.telemetry,
        )

    @property
    def _last_call_metrics(self) -> Dict[str, Any]:
        return self.image_generator.last_call_metrics

    @_last_call_metrics.setter
    def _last_call_metrics(self, val: Dict[str, Any]) -> None:
        self.image_generator.last_call_metrics = val

    def _audit(self, event_type: str, request_id: str, **kwargs) -> None:
        try:
            self.telemetry.record_event(
                event=event_type,
                request_id=request_id,
                component="generation",
                **kwargs,
            )
        except Exception as e:
            logger.warning(f"Could not record generation telemetry: {e}")

    def _save_generation_image(
        self, user_id: str, filename: str, image_bytes: bytes, aspect_ratio: str
    ) -> tuple[str, int, int]:
        """
        Saves generation image via StorageService, returns (storage_path, width, height).
        """
        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size

        storage_path = self.storage_service.upload_bytes(
            user_id=user_id,
            category="generations",
            filename=filename,
            data=image_bytes,
            content_type="image/png",
        )
        return storage_path, width, height

    def _load_image_bytes(self, image_path: str) -> bytes:
        return self.storage_service.download_bytes(image_path)

    def _call_image_model(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: Optional[int] = None,
        aspect_ratio: str = "2:3",
        reference_image_bytes: Optional[bytes] = None,
        audit_request_id: Optional[str] = None,
        reference_image_path: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> bytes:
        refs = [reference_image_bytes] if reference_image_bytes else None
        return self.image_generator.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            model=model_name or self.model_name,
            reference_images=refs,
            seed=seed,
            negative_prompt=negative_prompt,
            temperature=temperature,
            image_size="4K",
            audit_request_id=audit_request_id,
        )

    def _call_multi_image_model(
        self,
        contents: List[Any],
        seed: Optional[int] = None,
        aspect_ratio: str = "2:3",
        negative_prompt: str = "",
        audit_request_id: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> bytes:
        text_prompts: List[str] = []
        image_refs: List[Any] = []

        for item in contents:
            if isinstance(item, str):
                text_prompts.append(item)
            elif isinstance(item, bytes):
                image_refs.append(item)
            elif isinstance(item, dict) and item.get("type") == "image":
                image_refs.append(item)
            elif hasattr(item, "inline_data") and getattr(item, "inline_data", None):
                raw_d = item.inline_data.data
                mime_t = getattr(item.inline_data, "mime_type", "image/png")
                image_refs.append({
                    "type": "image",
                    "data": base64.b64encode(raw_d).decode("utf-8") if isinstance(raw_d, bytes) else str(raw_d),
                    "mime_type": mime_t,
                })

        combined_prompt = " ".join(text_prompts).strip()

        return self.image_generator.generate(
            prompt=combined_prompt,
            aspect_ratio=aspect_ratio,
            model=model_name or self.model_name,
            reference_images=image_refs,
            seed=seed,
            negative_prompt=negative_prompt,
            temperature=temperature,
            image_size="4K",
            audit_request_id=audit_request_id,
        )

    def generate_single_baseline(
        self,
        moodboard_id: Optional[str],
        state_dict: Dict[str, Any],
        positive_prompt: str,
        negative_prompt: str,
        seed: int,
        aspect_ratio: str = "2:3",
        imagen_model: Optional[str] = None,
        temperature: Optional[float] = 1.0,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Generates and persists a single baseline image candidate synchronously.
        """
        active_model = imagen_model or self.model_name
        gen_id = f"gen_base_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        req_id = f"baseline_single_{uuid.uuid4().hex[:10]}"
        logger.info(f"Generating baseline candidate {gen_id} (seed={seed}, temp={temperature}, model='{active_model}') for user '{user_id}'...")

        state_payload = dict(state_dict) if isinstance(state_dict, dict) else {}
        state_payload["imagen_model"] = active_model

        image_bytes = self._call_image_model(
            prompt=positive_prompt,
            aspect_ratio=aspect_ratio,
            model_name=active_model,
            seed=seed,
            negative_prompt=negative_prompt,
            temperature=temperature,
            audit_request_id=req_id,
        )

        filename = f"{gen_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes, aspect_ratio)

        metrics = self.image_generator.last_call_metrics
        call_cost = float(metrics.get("cost_usd", 0.0))
        call_tokens = int(metrics.get("total_token_count", 0))

        # Apportion upstream moodboard extraction and prompt ideation costs
        mb_acc_cost = 0.0
        mb_acc_tokens = 0
        if moodboard_id and self.db:
            mb_data = self.db.get_moodboard(moodboard_id)
            if mb_data:
                mb_acc_cost = float(mb_data.get("accumulated_cost_usd") or 0.0)
                mb_acc_tokens = int(mb_data.get("accumulated_tokens") or 0)

        apportioned_mb_cost = round(mb_acc_cost / 4.0, 6)
        apportioned_mb_tokens = int(mb_acc_tokens / 4)
        acc_cost = round(call_cost + apportioned_mb_cost, 6)
        acc_tokens = call_tokens + apportioned_mb_tokens

        cost_breakdown = {
            "direct_image_cost_usd": call_cost,
            "direct_image_tokens": call_tokens,
            "upstream_moodboard_cost_usd": apportioned_mb_cost,
            "upstream_moodboard_tokens": apportioned_mb_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "call_metrics": metrics.get("cost_breakdown", {}),
        }
        state_payload["cost_breakdown"] = cost_breakdown

        record = {
            "id": gen_id,
            "parent_id": None,
            "moodboard_id": moodboard_id,
            "is_baseline": True,
            "created_at": created_at,
            "schema_json": state_payload,
            "compiled_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "master_image_path": master_path,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": active_model,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "id": gen_id,
            "seed": seed,
            "image_url": f"/api/images/{master_path}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "compiled_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "temperature": temperature,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "cost_breakdown": cost_breakdown,
        }

    def generate_4_baselines(
        self,
        moodboard_id: Optional[str],
        state: Union[Dict[str, Any], Any],
        aspect_ratio: str = "2:3",
        prompt_override: Optional[str] = None,
        imagen_model: Optional[str] = None,
        temperature: Optional[float] = 1.0,
        user_id: str = "local_dev_user",
    ) -> List[Dict[str, Any]]:
        """
        Executes 4 baseline candidate generations with distinct randomized seeds.
        """
        state_dict = state.model_dump() if hasattr(state, "model_dump") else (state if isinstance(state, dict) else {})
        positive_prompt = (
            prompt_override
            or state_dict.get("master_prompt")
            or self.prompt_compiler.compile_prompt(
                narrative=state_dict.get("narrative"),
                categories=state_dict.get("categories"),
            )
        )
        negative_prompt = DEFAULT_NEGATIVE_PROMPT

        seeds = [random.randint(100000, 9999999) for _ in range(4)]
        while len(set(seeds)) < 4:
            seeds.append(random.randint(100000, 9999999))
            seeds = list(set(seeds))[:4]

        results = []
        for s in seeds:
            res = self.generate_single_baseline(
                moodboard_id=moodboard_id,
                state_dict=state_dict,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                seed=s,
                aspect_ratio=aspect_ratio,
                imagen_model=imagen_model,
                temperature=temperature,
                user_id=user_id,
            )
            results.append(res)
        return results

    def generate_baselines(self, *args, **kwargs):
        """Convenience alias for generate_4_baselines."""
        return self.generate_4_baselines(*args, **kwargs)

    def register_uploaded_photo(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        custom_aspect_ratio: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Ingests a user-provided image directly as a baseline generation record.
        """
        gen_id = f"gen_upload_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        pil_img = Image.open(io.BytesIO(image_bytes))
        width, height = pil_img.size
        eff_aspect = custom_aspect_ratio or detect_closest_aspect_ratio(width, height)

        out_filename = f"{gen_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, out_filename, image_bytes, eff_aspect)

        title = os.path.splitext(filename or "uploaded_photo")[0].replace("_", " ").title()
        prompt_desc = f"Directly ingested photo: {title}"
        seed = random.randint(100000, 9999999)

        record = {
            "id": gen_id,
            "parent_id": None,
            "moodboard_id": None,
            "is_baseline": True,
            "created_at": created_at,
            "schema_json": {"task": "direct_photo_upload", "original_filename": filename},
            "compiled_prompt": prompt_desc,
            "negative_prompt": "",
            "seed": seed,
            "master_image_path": master_path,
            "aspect_ratio": eff_aspect,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": "direct_upload",
            "cost_usd": 0.0,
            "tokens": 0,
            "accumulated_cost_usd": 0.0,
            "accumulated_tokens": 0,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "generation_id": gen_id,
            "image_url": f"/api/images/{master_path}",
            "seed": seed,
            "aspect_ratio": eff_aspect,
            "resolution": {"width": width, "height": height},
            "compiled_prompt": prompt_desc,
            "created_at": created_at,
        }

    def fine_tune_generation(
        self,
        parent_id: str,
        state: Optional[Union[Dict[str, Any], Any]] = None,
        narrative: Optional[str] = None,
        categories: Optional[Dict[str, Any]] = None,
        baseline_narrative: Optional[str] = None,
        baseline_categories: Optional[Dict[str, Any]] = None,
        locked_categories: Optional[List[str]] = None,
        prompt_override: Optional[str] = None,
        seed: int = 4289102,
        use_image_reference: bool = True,
        aspect_ratio: str = "2:3",
        negative_prompt: Optional[str] = None,
        imagen_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Seed-locked multimodal fine-tuning generation using delta prompt instructions.
        """
        active_model = imagen_model or self.model_name
        req_id = f"finetune_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        child_id = f"gen_child_{uuid.uuid4().hex[:8]}"

        parent_gen = self.db.get_generation(parent_id) if parent_id else None
        parent_image_bytes = None

        if parent_gen and use_image_reference:
            parent_path = parent_gen.get("master_image_path")
            if parent_path:
                try:
                    parent_image_bytes = self._load_image_bytes(parent_path)
                except Exception as e:
                    logger.warning(f"Could not load parent image bytes: {e}")

        eff_cats = categories or (state.get("categories") if isinstance(state, dict) else {})
        eff_narr = narrative or (state.get("narrative") if isinstance(state, dict) else "")

        delta_prompt = self.prompt_compiler.compile_delta_prompt(
            narrative=eff_narr,
            categories=eff_cats,
            baseline_narrative=baseline_narrative or (parent_gen.get("compiled_prompt") if parent_gen else None),
            baseline_categories=baseline_categories or (parent_gen.get("schema_json", {}).get("categories") if parent_gen else None),
            locked_categories=locked_categories,
            prompt_override=prompt_override,
        )

        eff_neg_prompt = negative_prompt or DEFAULT_NEGATIVE_PROMPT

        image_bytes = self._call_image_model(
            prompt=delta_prompt,
            aspect_ratio=aspect_ratio,
            model_name=active_model,
            reference_image_bytes=parent_image_bytes,
            seed=seed,
            negative_prompt=eff_neg_prompt,
            audit_request_id=req_id,
        )

        filename = f"{child_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes, aspect_ratio)

        metrics = self.image_generator.last_call_metrics
        call_cost = float(metrics.get("cost_usd", 0.0))
        call_tokens = int(metrics.get("total_token_count", 0))

        parent_acc_cost = float(parent_gen.get("accumulated_cost_usd", 0.0)) if parent_gen else 0.0
        parent_acc_tokens = int(parent_gen.get("accumulated_tokens", 0)) if parent_gen else 0

        acc_cost = round(parent_acc_cost + call_cost, 6)
        acc_tokens = parent_acc_tokens + call_tokens

        cost_breakdown = {
            "direct_image_cost_usd": call_cost,
            "direct_image_tokens": call_tokens,
            "parent_accumulated_cost_usd": parent_acc_cost,
            "parent_accumulated_tokens": parent_acc_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "call_metrics": metrics.get("cost_breakdown", {}),
        }

        schema_payload = state if isinstance(state, dict) else {
            "narrative": eff_narr,
            "categories": eff_cats,
            "locked_categories": locked_categories or [],
        }
        schema_payload["cost_breakdown"] = cost_breakdown

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": parent_gen.get("moodboard_id") if parent_gen else None,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": schema_payload,
            "compiled_prompt": delta_prompt,
            "negative_prompt": eff_neg_prompt,
            "seed": seed,
            "master_image_path": master_path,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": active_model,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": seed,
            "compiled_prompt": delta_prompt,
            "negative_prompt": eff_neg_prompt,
            "image_url": f"/api/images/{master_path}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "cost_breakdown": cost_breakdown,
        }

    def refine_generation(
        self,
        parent_id: str,
        prompt: str,
        seed: int,
        aspect_ratio: str = "2:3",
        negative_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        imagen_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Conversational iterative refinement turn using parent reference image.
        """
        active_model = imagen_model or self.model_name
        req_id = f"refine_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        child_id = f"gen_refine_{uuid.uuid4().hex[:8]}"

        parent_gen = self.db.get_generation(parent_id)
        if not parent_gen:
            raise ValueError(f"Parent generation '{parent_id}' not found")

        parent_path = parent_gen.get("master_image_path")
        parent_bytes = self._load_image_bytes(parent_path)

        refine_instruction = self.prompt_compiler.format_refinement_prompt(prompt)
        eff_neg_prompt = negative_prompt or parent_gen.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT

        image_bytes = self._call_image_model(
            prompt=refine_instruction,
            aspect_ratio=aspect_ratio,
            model_name=active_model,
            reference_image_bytes=parent_bytes,
            seed=seed,
            negative_prompt=eff_neg_prompt,
            audit_request_id=req_id,
        )

        filename = f"{child_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes, aspect_ratio)

        metrics = self.image_generator.last_call_metrics
        call_cost = float(metrics.get("cost_usd", 0.0))
        call_tokens = int(metrics.get("total_token_count", 0))

        parent_acc_cost = float(parent_gen.get("accumulated_cost_usd", 0.0))
        parent_acc_tokens = int(parent_gen.get("accumulated_tokens", 0))
        acc_cost = round(parent_acc_cost + call_cost, 6)
        acc_tokens = parent_acc_tokens + call_tokens

        cost_breakdown = {
            "direct_image_cost_usd": call_cost,
            "direct_image_tokens": call_tokens,
            "parent_accumulated_cost_usd": parent_acc_cost,
            "parent_accumulated_tokens": parent_acc_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "call_metrics": metrics.get("cost_breakdown", {}),
        }

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": parent_gen.get("moodboard_id"),
            "conversation_id": conversation_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": {"refinement_prompt": prompt, "parent_id": parent_id, "cost_breakdown": cost_breakdown},
            "compiled_prompt": refine_instruction,
            "negative_prompt": eff_neg_prompt,
            "seed": seed,
            "master_image_path": master_path,
            "aspect_ratio": aspect_ratio,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": active_model,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "conversation_id": conversation_id,
            "seed": seed,
            "prompt": prompt,
            "compiled_prompt": refine_instruction,
            "negative_prompt": eff_neg_prompt,
            "image_url": f"/api/images/{master_path}",
            "created_at": created_at,
            "aspect_ratio": aspect_ratio,
            "resolution": {"width": width, "height": height},
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "cost_breakdown": cost_breakdown,
        }

    def inpaint_region(
        self,
        parent_id: str,
        image_bytes: bytes,
        mask_bytes: bytes,
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        aspect_ratio: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Targeted inpainting using black & white mask and spatial prompt context with 4K output.
        """
        req_id = f"inpaint_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        child_id = f"gen_inpaint_{uuid.uuid4().hex[:8]}"

        parent_gen = self.db.get_generation(parent_id) if parent_id else None
        eff_seed = seed or (parent_gen.get("seed") if parent_gen else random.randint(100000, 999999))
        eff_aspect = aspect_ratio or (parent_gen.get("aspect_ratio") if parent_gen else "2:3")
        eff_neg_prompt = negative_prompt or (parent_gen.get("negative_prompt") if parent_gen else DEFAULT_NEGATIVE_PROMPT)

        mask_stats = analyze_mask_bytes(mask_bytes)
        spatial_prompt = self.prompt_compiler.format_inpaint_prompt(
            prompt=prompt,
            mask_stats=mask_stats,
            aspect_ratio=eff_aspect,
            negative_prompt=eff_neg_prompt,
        )

        self._audit(
            "inpaint_request",
            req_id,
            parent_id=parent_id,
            prompt=prompt,
            mask=mask_stats,
            source_image={"width": mask_stats.get("width", 0), "height": mask_stats.get("height", 0)},
        )

        image_bytes_out = self._call_multi_image_model(
            contents=[image_bytes, mask_bytes, spatial_prompt],
            aspect_ratio=eff_aspect,
            model_name=self.inpaint_model_name,
            seed=eff_seed,
            negative_prompt=eff_neg_prompt,
            audit_request_id=req_id,
        )

        filename = f"{child_id}_master.png"
        mask_filename = f"{child_id}_mask.png"

        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes_out, eff_aspect)
        mask_path, _, _ = self._save_generation_image(user_id, mask_filename, mask_bytes, eff_aspect)

        metrics = self.image_generator.last_call_metrics
        call_cost = float(metrics.get("cost_usd", 0.0))
        call_tokens = int(metrics.get("total_token_count", 0))

        parent_acc_cost = float(parent_gen.get("accumulated_cost_usd", 0.0)) if parent_gen else 0.0
        parent_acc_tokens = int(parent_gen.get("accumulated_tokens", 0)) if parent_gen else 0
        acc_cost = round(parent_acc_cost + call_cost, 6)
        acc_tokens = parent_acc_tokens + call_tokens

        cost_breakdown = {
            "direct_image_cost_usd": call_cost,
            "direct_image_tokens": call_tokens,
            "parent_accumulated_cost_usd": parent_acc_cost,
            "parent_accumulated_tokens": parent_acc_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "call_metrics": metrics.get("cost_breakdown", {}),
        }

        inpaint_meta = {
            "mask_path": mask_path,
            "mask_url": f"/api/images/{mask_path}",
            "mask_stats": mask_stats,
            "prompt": prompt,
            "user_inpaint_prompt": prompt,
            "inpaint_model": self.inpaint_model_name,
        }

        record = {
            "id": child_id,
            "parent_id": parent_id or None,
            "moodboard_id": parent_gen.get("moodboard_id") if parent_gen else None,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": {"inpaint_metadata": inpaint_meta, "inpaint_model": self.inpaint_model_name, "cost_breakdown": cost_breakdown},
            "compiled_prompt": spatial_prompt,
            "negative_prompt": eff_neg_prompt,
            "seed": eff_seed,
            "master_image_path": master_path,
            "aspect_ratio": eff_aspect,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": self.inpaint_model_name,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        self._audit(
            "inpaint_response",
            req_id,
            generation_id=child_id,
            parent_id=parent_id,
            status="success",
            dimensions={"width": width, "height": height},
        )

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "seed": eff_seed,
            "prompt": prompt,
            "compiled_prompt": spatial_prompt,
            "negative_prompt": eff_neg_prompt,
            "image_url": f"/api/images/{master_path}",
            "mask_url": f"/api/images/{mask_path}",
            "created_at": created_at,
            "aspect_ratio": eff_aspect,
            "resolution": {"width": width, "height": height},
            "mask_stats": mask_stats,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "cost_breakdown": cost_breakdown,
        }

    def compose_wardrobe(
        self,
        parent_id: str,
        assignments: List[Union[Dict[str, Any], Any]],
        aspect_ratio: Optional[str] = None,
        model_name: Optional[str] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
        custom_instruction: Optional[str] = None,
        imagen_model: Optional[str] = None,
        vision_model: Optional[str] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Multimodal wardrobe composition preserving subject identity and applying assigned garments.
        """
        active_model = imagen_model or model_name or self.model_name
        req_id = f"compose_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        child_id = f"gen_wardrobe_{uuid.uuid4().hex[:8]}"

        parent_gen = self.db.get_generation(parent_id)
        if not parent_gen:
            raise ValueError(f"Parent generation '{parent_id}' not found")

        parent_path = parent_gen.get("master_image_path")
        parent_image_bytes = self._load_image_bytes(parent_path)

        eff_aspect = aspect_ratio or parent_gen.get("aspect_ratio", "2:3")
        eff_seed = seed if seed is not None else parent_gen.get("seed", 4289102)

        normalized_assignments: List[Dict[str, Any]] = []
        for asgn in assignments:
            if hasattr(asgn, "model_dump"):
                normalized_assignments.append(asgn.model_dump())
            elif hasattr(asgn, "dict"):
                normalized_assignments.append(asgn.dict())
            elif isinstance(asgn, dict):
                normalized_assignments.append(dict(asgn))
            else:
                normalized_assignments.append(getattr(asgn, "__dict__", {}))

        grounded_data = {}
        if self.wardrobe_service is not None:
            try:
                grounded_data = self.wardrobe_service.ground_wardrobe_pins(
                    generation_id=parent_id,
                    assignments=normalized_assignments,
                    vision_model=vision_model,
                    user_id=user_id,
                )
            except Exception as e:
                logger.warning(f"Could not run wardrobe subject grounding: {e}")

        grounded_pins_list = grounded_data.get("grounded_pins", [])
        grounded_by_pin = {g["pin_number"]: g for g in grounded_pins_list if "pin_number" in g}
        guardrail_text = grounded_data.get(
            "unmodified_subjects_guardrail",
            "Strictly preserve all other subjects and non-targeted character features exactly as shown.",
        )

        garment_references: List[bytes] = []
        assignment_prompts: List[str] = []
        graphic_locks_required = False

        for asgn in normalized_assignments:
            item_id = asgn.get("wardrobe_item_id")
            pin_num = asgn.get("pin_number", 1)
            item = self.db.get_wardrobe_item(item_id) if item_id else None

            if item:
                crop_path = item.get("upscaled_image_path") or item.get("cropped_image_path")
                if crop_path:
                    try:
                        garment_references.append(self._load_image_bytes(crop_path))
                    except Exception as e:
                        logger.warning(f"Could not load garment crop {crop_path}: {e}")

                g_info = grounded_by_pin.get(pin_num, {})
                target_sub = g_info.get("target_subject", f"Subject at pin #{pin_num}")
                body_loc = g_info.get("body_location", "targeted body area")
                spatial_anc = g_info.get("spatial_anchor", "designated region")

                label = item.get("label", "garment")
                category = item.get("category", "tops")
                asgn_text = f"Pin #{pin_num} ({spatial_anc}): Replace {body_loc} of {target_sub} with \"{label}\" ({category})."

                extracted_details = item.get("extracted_details") or {}
                if extracted_details:
                    details_parts = []
                    if extracted_details.get("has_text_or_logo") and extracted_details.get("exact_text_content"):
                        graphic_locks_required = True
                        txt = extracted_details["exact_text_content"]
                        t_str = ", ".join([f'"{t}"' for t in txt]) if isinstance(txt, list) else str(txt)
                        details_parts.append(f"EXACT TEXT (100% SPELLING LOCK): {t_str}")
                    if extracted_details.get("logo_and_print_placement"):
                        details_parts.append(f"PLACEMENT: {extracted_details['logo_and_print_placement']}")
                    if extracted_details.get("has_graphic_or_print") and extracted_details.get("graphic_description"):
                        graphic_locks_required = True
                        details_parts.append(f"GRAPHIC ARTWORK: {extracted_details['graphic_description']}")
                    if extracted_details.get("fabric_texture"):
                        details_parts.append(f"TEXTURE: {extracted_details['fabric_texture']}")
                    if details_parts:
                        asgn_text += f"\n  - DETAILS: {'; '.join(details_parts)}"

                assignment_prompts.append(asgn_text)

        # Trace lineage depth
        lineage_depth = 0
        curr_p = parent_gen
        visited_lineage = set()
        while curr_p and curr_p.get("parent_id") and curr_p.get("id") not in visited_lineage:
            visited_lineage.add(curr_p.get("id"))
            next_p = self.db.get_generation(curr_p["parent_id"])
            if not next_p:
                break
            curr_p = next_p
            lineage_depth += 1

        composition_parts = [
            WARDROBE_COMPOSITION_SYSTEM_PROMPT,
            f"MULTI-SUBJECT INVARIANCE GUARDRAIL:\n{guardrail_text}",
        ]
        if lineage_depth >= 1:
            turn_num = lineage_depth + 1
            composition_parts.append(
                f"PROGRESSIVE STYLING TURN #{turn_num} CHROMATIC ANCHOR:\n"
                "- Maintain absolute color temperature and neutral white balance fidelity matching the original root scene.\n"
                "- Do NOT accumulate or amplify warm ambient color bounce from prior turns. Keep all background elements, neutral whites, sky tones, and un-targeted skin undertones strictly aligned with the pristine base scene."
            )
        composition_parts.append("ASSIGNED GARMENT MODIFICATIONS:\n" + "\n\n".join(assignment_prompts))

        if custom_instruction and custom_instruction.strip():
            composition_parts.append(f"ADDITIONAL USER INSTRUCTION:\n{custom_instruction.strip()}")

        composition_prompt = "\n\n".join(composition_parts)

        base_neg_prompt = negative_prompt or parent_gen.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT
        if graphic_locks_required:
            comp_neg_prompt = f"{base_neg_prompt}, scrambled text, altered logos, fake text, misspelled words, generic replacement graphics"
        else:
            comp_neg_prompt = base_neg_prompt

        all_refs = [parent_image_bytes] + garment_references
        image_bytes_out = self._call_multi_image_model(
            contents=all_refs + [composition_prompt],
            aspect_ratio=eff_aspect,
            model_name=active_model,
            seed=eff_seed,
            negative_prompt=comp_neg_prompt,
            audit_request_id=req_id,
        )

        filename = f"{child_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes_out, eff_aspect)

        metrics = self.image_generator.last_call_metrics
        image_call_cost = float(metrics.get("cost_usd", 0.0))
        image_call_tokens = int(metrics.get("total_token_count", 0))

        grounding_cost = float(grounded_data.get("cost_usd") or 0.0)
        grounding_toks_raw = grounded_data.get("tokens")
        grounding_tokens = int(
            grounding_toks_raw.get("total_token_count", 0)
            if isinstance(grounding_toks_raw, dict)
            else (grounding_toks_raw or 0)
        )

        turn_cost = round(image_call_cost + grounding_cost, 6)
        turn_tokens = image_call_tokens + grounding_tokens

        parent_acc_cost = float(parent_gen.get("accumulated_cost_usd", 0.0)) if parent_gen else 0.0
        parent_acc_tokens = int(parent_gen.get("accumulated_tokens", 0)) if parent_gen else 0
        acc_cost = round(parent_acc_cost + turn_cost, 6)
        acc_tokens = parent_acc_tokens + turn_tokens

        cost_breakdown = {
            "image_model_cost_usd": image_call_cost,
            "image_model_tokens": image_call_tokens,
            "grounding_cost_usd": grounding_cost,
            "grounding_tokens": grounding_tokens,
            "turn_cost_usd": turn_cost,
            "turn_tokens": turn_tokens,
            "parent_accumulated_cost_usd": parent_acc_cost,
            "parent_accumulated_tokens": parent_acc_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "call_metrics": metrics.get("cost_breakdown", {}),
        }

        schema_data = {
            "wardrobe_assignments": normalized_assignments,
            "grounded_pins": grounded_pins_list,
            "wardrobe_composition": True,
            "cost_breakdown": cost_breakdown,
        }
        if custom_instruction and custom_instruction.strip():
            schema_data["custom_instruction"] = custom_instruction.strip()
        if conversation_id:
            schema_data["conversation_id"] = conversation_id

        record = {
            "id": child_id,
            "parent_id": parent_id,
            "moodboard_id": parent_gen.get("moodboard_id"),
            "conversation_id": conversation_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": schema_data,
            "compiled_prompt": composition_prompt,
            "negative_prompt": comp_neg_prompt,
            "seed": eff_seed,
            "master_image_path": master_path,
            "aspect_ratio": eff_aspect,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": active_model,
            "cost_usd": turn_cost,
            "tokens": turn_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "generation_id": child_id,
            "parent_id": parent_id,
            "conversation_id": conversation_id,
            "seed": eff_seed,
            "compiled_prompt": composition_prompt,
            "negative_prompt": comp_neg_prompt,
            "image_url": f"/api/images/{master_path}",
            "created_at": created_at,
            "aspect_ratio": eff_aspect,
            "resolution": {"width": width, "height": height},
            "assignments": [
                {
                    **asgn,
                    "grounded_subject": grounded_by_pin.get(asgn.get("pin_number", 1), {}).get("target_subject", "Subject"),
                }
                for asgn in normalized_assignments
            ],
            "cost_usd": turn_cost,
            "tokens": turn_tokens,
            "accumulated_cost_usd": acc_cost,
            "accumulated_tokens": acc_tokens,
            "cost_breakdown": cost_breakdown,
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        aspect_ratio: Optional[str] = "1:1",
        parent_id: Optional[str] = None,
        moodboard_id: Optional[str] = None,
        chips_snapshot: Optional[Any] = None,
        user_id: str = "local_dev_user",
    ) -> Dict[str, Any]:
        """
        Legacy single image generation endpoint.
        """
        eff_seed = seed or random.randint(100000, 9999999)
        eff_aspect = aspect_ratio or "1:1"
        eff_neg_prompt = negative_prompt or DEFAULT_NEGATIVE_PROMPT
        gen_id = f"gen_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        req_id = f"legacy_gen_{uuid.uuid4().hex[:8]}"

        image_bytes = self._call_image_model(
            prompt=prompt,
            aspect_ratio=eff_aspect,
            model_name=self.model_name,
            seed=eff_seed,
            negative_prompt=eff_neg_prompt,
            audit_request_id=req_id,
        )

        filename = f"{gen_id}_master.png"
        master_path, width, height = self._save_generation_image(user_id, filename, image_bytes, eff_aspect)

        metrics = self.image_generator.last_call_metrics
        call_cost = float(metrics.get("cost_usd", 0.0))
        call_tokens = int(metrics.get("total_token_count", 0))

        record = {
            "id": gen_id,
            "parent_id": parent_id,
            "moodboard_id": moodboard_id,
            "is_baseline": False,
            "created_at": created_at,
            "schema_json": {"chips": chips_snapshot} if chips_snapshot else {},
            "compiled_prompt": prompt,
            "negative_prompt": eff_neg_prompt,
            "seed": eff_seed,
            "master_image_path": master_path,
            "aspect_ratio": eff_aspect,
            "resolution_width": width,
            "resolution_height": height,
            "model_name": self.model_name,
            "cost_usd": call_cost,
            "tokens": call_tokens,
            "accumulated_cost_usd": call_cost,
            "accumulated_tokens": call_tokens,
        }
        self.db.create_generation(user_id=user_id, gen_data=record)

        return {
            "generation_id": gen_id,
            "created_at": created_at,
            "compiled_prompt": prompt,
            "negative_prompt": eff_neg_prompt,
            "seed": eff_seed,
            "master_image_url": f"/api/images/{master_path}",
            "resolution": {"width": width, "height": height},
            "cost_usd": call_cost,
            "tokens": call_tokens,
        }
