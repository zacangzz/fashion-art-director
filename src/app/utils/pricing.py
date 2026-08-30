from typing import Any, Dict, Optional
from app.utils.logger import get_logger

logger = get_logger("pricing")

# Pricing per million tokens (USD) and resolution-specific image output rates (USD).
# Based on official Google GenAI Interactions API pricing specification.
MODEL_PRICING: Dict[str, Dict[str, Any]] = {
    # Vision / Multimodal Text models
    "gemini-3.5-flash-lite": {
        "prompt_cost_per_m": 0.075,
        "candidates_cost_per_m": 0.30,
        "per_image_cost": 0.0,
        "image_rates": {"default": 0.0},
    },
    "gemini-3.7-flash": {
        "prompt_cost_per_m": 0.75,
        "candidates_cost_per_m": 3.75,
        "per_image_cost": 0.0,
        "image_rates": {"default": 0.0},
    },
    # Image Generation models
    "gemini-3.1-flash-lite-image": {
        "prompt_cost_per_m": 0.25,
        "candidates_cost_per_m": 1.50,
        "per_image_cost": 0.0336,
        "image_rates": {
            "1K": 0.0336,
            "1024x1024": 0.0336,
            "512px": 0.022,
            "0.5K": 0.022,
            "default": 0.0336,
        },
    },
    "gemini-3.1-flash-image": {
        "prompt_cost_per_m": 0.50,
        "candidates_cost_per_m": 3.00,
        "per_image_cost": 0.151,
        "image_rates": {
            "4K": 0.151,
            "2K": 0.101,
            "1K": 0.067,
            "512px": 0.045,
            "0.5K": 0.045,
            "default": 0.151,
        },
    },
    "gemini-3-pro-image": {
        "prompt_cost_per_m": 2.00,
        "candidates_cost_per_m": 12.00,
        "per_image_cost": 0.240,
        "image_rates": {
            "4K": 0.240,
            "2K": 0.134,
            "1K": 0.134,
            "512px": 0.090,
            "0.5K": 0.090,
            "default": 0.240,
        },
    },
}

DEFAULT_FALLBACK_PRICING: Dict[str, Any] = {
    "prompt_cost_per_m": 2.00,
    "candidates_cost_per_m": 12.00,
    "per_image_cost": 0.240,
    "image_rates": {
        "4K": 0.240,
        "2K": 0.134,
        "1K": 0.134,
        "512px": 0.090,
        "default": 0.240,
    },
}


def extract_usage_metadata(response: Any) -> Dict[str, int]:
    """
    Extracts usage_metadata directly from Google GenAI SDK response.
    Returns dictionary with prompt_token_count, candidates_token_count, total_token_count.
    """
    if response is None:
        return {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}

    usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = int(
            getattr(usage, "prompt_token_count", None)
            or getattr(usage, "prompt_tokens", 0)
            or 0
        )
        candidates_tokens = int(
            getattr(usage, "candidates_token_count", None)
            or getattr(usage, "candidates_tokens", 0)
            or 0
        )
        total_tokens = int(
            getattr(usage, "total_token_count", None)
            or getattr(usage, "total_tokens", 0)
            or (prompt_tokens + candidates_tokens)
        )
        return {
            "prompt_token_count": prompt_tokens,
            "candidates_token_count": candidates_tokens,
            "total_token_count": total_tokens,
        }

    # Handle dictionary representation if response is already serialized
    if isinstance(response, dict):
        usage_dict = response.get("usage_metadata") or response.get("usage")
        if isinstance(usage_dict, dict):
            prompt_tokens = int(usage_dict.get("prompt_token_count", 0) or usage_dict.get("prompt_tokens", 0) or 0)
            candidates_tokens = int(
                usage_dict.get("candidates_token_count", 0) or usage_dict.get("candidates_tokens", 0) or 0
            )
            total_tokens = int(
                usage_dict.get("total_token_count", 0)
                or usage_dict.get("total_tokens", 0)
                or (prompt_tokens + candidates_tokens)
            )
            return {
                "prompt_token_count": prompt_tokens,
                "candidates_token_count": candidates_tokens,
                "total_token_count": total_tokens,
            }

    return {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}


def calculate_cost(
    model: Optional[str],
    prompt_tokens: int = 0,
    candidates_tokens: int = 0,
    images_count: int = 0,
    image_size: Optional[str] = "4K",
) -> Dict[str, Any]:
    """
    Calculates USD cost based on model pricing table, token usage, image resolution tier, and images generated.
    """
    model_key = (model or "").lower().strip()
    pricing = MODEL_PRICING.get(model_key)
    if not pricing:
        # Fuzzy match if versioned string
        for k, v in MODEL_PRICING.items():
            if k in model_key or model_key in k:
                pricing = v
                break
    if not pricing:
        pricing = DEFAULT_FALLBACK_PRICING

    # Determine per-image unit cost by resolution tier
    rates_dict = pricing.get("image_rates", {})
    eff_size = (image_size or "4K").upper().strip()
    unit_image_cost = rates_dict.get(eff_size)
    if unit_image_cost is None:
        unit_image_cost = rates_dict.get("default", pricing.get("per_image_cost", 0.0))

    prompt_cost = (prompt_tokens / 1_000_000.0) * float(pricing.get("prompt_cost_per_m", 0.0))
    candidates_cost = (candidates_tokens / 1_000_000.0) * float(pricing.get("candidates_cost_per_m", 0.0))
    images_cost = images_count * float(unit_image_cost)

    total_cost = prompt_cost + candidates_cost + images_cost
    total_tokens = prompt_tokens + candidates_tokens

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "candidates_tokens": candidates_tokens,
        "total_tokens": total_tokens,
        "images_count": images_count,
        "image_size": eff_size,
        "cost_usd": round(total_cost, 6),
        "breakdown": {
            "prompt_cost_usd": round(prompt_cost, 6),
            "candidates_cost_usd": round(candidates_cost, 6),
            "images_cost_usd": round(images_cost, 6),
            "per_image_rate_usd": round(float(unit_image_cost), 6),
        },
    }
