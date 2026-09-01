import io
import time
import base64
import random
import hashlib
from typing import Any, Dict, List, Optional, Union
from PIL import Image
from google import genai
from google.genai import types

from app.utils.logger import get_logger
from app.utils.telemetry import TelemetryLogger
from app.utils.pricing import extract_usage_metadata, calculate_cost
from app.utils.image_utils import (
    normalize_interaction_aspect_ratio,
    to_interaction_image_input,
    ASPECT_RATIO_RESOLUTIONS,
)
from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    IMAGE_GENERATION_SUFFIX,
)

logger = get_logger("image_generator")

LITE_IMAGE_MODELS = {
    "gemini-3.1-flash-lite-image",
}


def resolve_model_image_size(model_name: str, requested_size: Optional[str] = "4K") -> Optional[str]:
    """
    Returns the appropriate image_size for the given model.
    Lite models only support standard 1K (and 512px) resolution; requesting 2K or 4K causes Google API 404 Entity Not Found.
    Standard/Pro models (gemini-3.1-flash-image, gemini-3-pro-image) support 1K, 2K, 4K.
    """
    if not requested_size:
        return None

    clean_model = model_name.lower().strip()
    if clean_model in LITE_IMAGE_MODELS or "lite" in clean_model:
        if requested_size in ("2K", "4K"):
            return "1K"
        return requested_size
    return requested_size


class ImageGenerator:
    """
    Independent component responsible for executing Google GenAI Interactions API calls
    to generate, edit, and inpaint ultra-high-resolution images synchronously.
    """

    def __init__(
        self,
        client: genai.Client,
        default_model: str = "gemini-3-pro-image",
        telemetry: Optional[TelemetryLogger] = None,
    ):
        self.client = client
        self.default_model = default_model
        self.telemetry = telemetry
        self.last_call_metrics: Dict[str, Any] = {
            "cost_usd": 0.0,
            "total_token_count": 0,
            "prompt_tokens": 0,
            "candidates_tokens": 0,
        }

    def _execute_with_retry(
        self,
        func: Any,
        *args: Any,
        max_retries: int = 2,
        initial_backoff: float = 1.5,
        **kwargs: Any,
    ) -> Any:
        last_exc = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exc = e
                err_str = str(e).lower()
                retryable = any(
                    code in err_str
                    for code in [
                        "429",
                        "503",
                        "resource_exhausted",
                        "unavailable",
                        "timeout",
                        "deadline_exceeded",
                        "connection",
                    ]
                )
                if not retryable or attempt == max_retries - 1:
                    logger.error(f"Image generation failed after attempt {attempt + 1}: {e}")
                    raise
                backoff = initial_backoff * (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(
                    f"Transient error on attempt {attempt + 1}/{max_retries}: {e}. Retrying in {backoff:.2f}s..."
                )
                time.sleep(backoff)
        if last_exc:
            raise last_exc

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "2:3",
        model: Optional[str] = None,
        reference_images: Optional[List[Union[bytes, dict]]] = None,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        image_size: str = "4K",
        audit_request_id: Optional[str] = None,
    ) -> bytes:
        """
        Generates or edits an image synchronously using Google GenAI Interactions API.
        Automatically negotiates resolution capability (e.g. 1K for lite models, 4K for pro/flash).
        """
        active_model = model or self.default_model
        effective_image_size = resolve_model_image_size(active_model, image_size)
        norm_aspect = normalize_interaction_aspect_ratio(aspect_ratio)
        res_tuple = ASPECT_RATIO_RESOLUTIONS.get(aspect_ratio or "2:3", (2560, 3840))
        res_str = f"{res_tuple[0]}x{res_tuple[1]}"

        suffix = IMAGE_GENERATION_SUFFIX.format(
            RESOLUTION=res_str,
            ASPECT_RATIO=norm_aspect,
            SEED=seed if seed is not None else "unspecified",
            NEGATIVE_PROMPT=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
        )
        full_prompt = f"{prompt.rstrip()} {suffix.strip()}"

        input_items: List[Any] = []
        if reference_images:
            for ref in reference_images:
                if isinstance(ref, bytes):
                    input_items.append(to_interaction_image_input(ref, optimize=True))
                elif isinstance(ref, dict):
                    input_items.append(ref)

        input_items.append({"type": "text", "text": full_prompt})
        api_input = input_items if len(input_items) > 1 else full_prompt

        response_format: Dict[str, Any] = {
            "type": "image",
            "aspect_ratio": norm_aspect,
        }
        if effective_image_size:
            response_format["image_size"] = effective_image_size

        kwargs: Dict[str, Any] = {
            "model": active_model,
            "input": api_input,
            "response_format": response_format,
        }
        if temperature is not None:
            kwargs["generation_config"] = {"temperature": float(temperature)}

        logger.info(
            f"ImageGenerator calling Interactions API for '{active_model}' "
            f"(aspect={aspect_ratio} -> {norm_aspect}, size={effective_image_size}, seed={seed}, temp={temperature}, refs={len(reference_images or [])})"
        )

        started = time.perf_counter()
        if self.telemetry and audit_request_id:
            self.telemetry.record_event(
                event="image_model_request",
                request_id=audit_request_id,
                component="generation",
                model=active_model,
                config={
                    "aspect_ratio": norm_aspect,
                    "image_size": effective_image_size,
                    "seed": seed,
                    "negative_prompt": negative_prompt,
                    "temperature": temperature,
                },
                inputs={"parts_count": len(input_items)},
            )

        try:
            if hasattr(self.client, "interactions") and hasattr(self.client.interactions, "create"):
                call_target = self.client.interactions.create
                interaction = self._execute_with_retry(call_target, **kwargs)
            elif hasattr(self.client, "models") and hasattr(self.client.models, "generate_content"):
                interaction = self._execute_with_retry(
                    self.client.models.generate_content,
                    model=active_model,
                    contents=api_input,
                )
            else:
                raise RuntimeError("GenAI Client missing both interactions and models API interfaces.")
        except Exception as err:
            if self.telemetry and audit_request_id:
                self.telemetry.record_event(
                    event="image_model_error",
                    request_id=audit_request_id,
                    component="generation",
                    status="error",
                    model=active_model,
                    error=repr(err),
                )
            raise

        # Extract image bytes
        image_bytes: Optional[bytes] = None
        if getattr(interaction, "output_image", None) and getattr(interaction.output_image, "data", None):
            raw_val = interaction.output_image.data
            if isinstance(raw_val, bytes):
                image_bytes = raw_val
            elif isinstance(raw_val, str):
                try:
                    image_bytes = base64.b64decode(raw_val)
                except Exception:
                    image_bytes = raw_val.encode("utf-8")
        elif hasattr(interaction, "steps"):
            for step in getattr(interaction, "steps", []):
                step_type = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
                if step_type == "model_output":
                    content = getattr(step, "content", []) or (step.get("content", []) if isinstance(step, dict) else [])
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "image" and block.get("data"):
                                d = block["data"]
                                image_bytes = base64.b64decode(d) if isinstance(d, str) else d
                                break
                            elif "image" in block:
                                img_val = block["image"]
                                d = img_val.get("data") if isinstance(img_val, dict) else getattr(img_val, "data", img_val)
                                image_bytes = base64.b64decode(d) if isinstance(d, str) else d
                                break
                        elif getattr(block, "type", None) == "image" and getattr(block, "data", None):
                            d = block.data
                            image_bytes = base64.b64decode(d) if isinstance(d, str) else d
                            break
                        elif getattr(block, "image", None):
                            img_val = block.image
                            d = getattr(img_val, "data", img_val)
                            image_bytes = base64.b64decode(d) if isinstance(d, str) else d
                            break
                if image_bytes:
                    break
        elif hasattr(interaction, "candidates") and interaction.candidates:
            cand = interaction.candidates[0]
            if hasattr(cand, "content") and hasattr(cand.content, "parts") and cand.content.parts:
                part = cand.content.parts[0]
                if hasattr(part, "inline_data") and hasattr(part.inline_data, "data"):
                    raw_val = part.inline_data.data
                    if isinstance(raw_val, bytes):
                        image_bytes = raw_val
                    elif isinstance(raw_val, str):
                        try:
                            image_bytes = base64.b64decode(raw_val)
                        except Exception:
                            image_bytes = raw_val.encode("utf-8")

        if not image_bytes:
            raise RuntimeError(f"No image data returned from Google GenAI Interactions API for model '{active_model}'.")

        usage_dict = extract_usage_metadata(interaction)
        ref_count = len(reference_images or [])
        estimated_prompt_tokens = 560 * ref_count + max(len(full_prompt) // 4, 80)
        if usage_dict["total_token_count"] == 0:
            usage_dict = {
                "prompt_token_count": estimated_prompt_tokens,
                "candidates_token_count": 0,
                "total_token_count": estimated_prompt_tokens,
            }
        elif usage_dict["prompt_token_count"] == 0 and ref_count > 0:
            usage_dict["prompt_token_count"] = max(usage_dict["prompt_token_count"], estimated_prompt_tokens)
            usage_dict["total_token_count"] = usage_dict["prompt_token_count"] + usage_dict["candidates_token_count"]

        cost_info = calculate_cost(
            active_model,
            prompt_tokens=usage_dict["prompt_token_count"],
            candidates_tokens=usage_dict["candidates_token_count"],
            images_count=1,
            image_size=effective_image_size or "4K",
        )
        self.last_call_metrics = {
            "cost_usd": cost_info["cost_usd"],
            "total_token_count": usage_dict["total_token_count"],
            "prompt_tokens": usage_dict["prompt_token_count"],
            "candidates_tokens": usage_dict["candidates_token_count"],
            "cost_breakdown": cost_info.get("breakdown", {}),
            "image_size": effective_image_size or "4K",
        }

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            f"ImageGenerator received {len(image_bytes)} bytes ({duration_ms}ms, size={effective_image_size}, cost=${cost_info['cost_usd']:.4f})"
        )

        if self.telemetry and audit_request_id:
            self.telemetry.record_event(
                event="image_model_response",
                request_id=audit_request_id,
                component="generation",
                status="success",
                model=active_model,
                duration_ms=duration_ms,
                tokens=usage_dict,
                cost_usd=cost_info["cost_usd"],
                cost_breakdown=cost_info.get("breakdown", {}),
                outputs={
                    "bytes": len(image_bytes),
                    "sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "image_size": effective_image_size or "4K",
                },
            )

        return image_bytes
