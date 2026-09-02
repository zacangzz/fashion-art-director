from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from app.utils.logger import get_logger
from app.utils.currency_service import get_daily_exchange_rate, get_today_iso_date

logger = get_logger("pricing")

# Official Google Gemini API Pricing Specs (source: https://ai.google.dev/gemini-api/docs/pricing)
OFFICIAL_MODEL_PRICING_SEEDS: List[Dict[str, Any]] = [
    {
        "model_name": "gemini-3.5-flash-lite",
        "effective_date": "2025-01-01",
        "prompt_cost_per_m": 0.075,
        "candidates_cost_per_m": 0.30,
        "per_image_cost": 0.0,
        "image_rates": {"default": 0.0},
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    {
        "model_name": "gemini-3.7-flash",
        "effective_date": "2025-01-01",
        "prompt_cost_per_m": 0.75,
        "candidates_cost_per_m": 3.75,
        "per_image_cost": 0.0,
        "image_rates": {"default": 0.0},
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    {
        "model_name": "gemini-3.1-flash-lite-image",
        "effective_date": "2025-01-01",
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
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    {
        "model_name": "gemini-3.1-flash-image",
        "effective_date": "2025-01-01",
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
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    },
    {
        "model_name": "gemini-3-pro-image",
        "effective_date": "2025-01-01",
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
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
    },
]

MODEL_PRICING: Dict[str, Dict[str, Any]] = {
    s["model_name"]: s for s in OFFICIAL_MODEL_PRICING_SEEDS
}

DEFAULT_FALLBACK_PRICING: Dict[str, Any] = {
    "model_name": "default",
    "effective_date": "2025-01-01",
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
    "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
}

# In-memory cache for resolved pricing: (model_key, date_key) -> pricing_dict
_PRICING_CACHE: Dict[str, Dict[str, Any]] = {}


def round_up_cost(val: float, decimals: int = 3) -> float:
    """
    Rounds up a monetary cost value to the given number of decimal places (ceiling rounding).
    Always guarantees that non-zero micro-costs are rounded UP.
    """
    if val <= 0:
        return 0.0
    factor = 10 ** decimals
    return math.ceil(val * factor) / factor


def get_model_pricing_for_date(
    model: Optional[str],
    target_date: Optional[str] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Resolves the active pricing tier for a model as of a specific effective date.
    Looks up in Firestore `model_pricing` collection, then cached seed tiers, with fallback.
    """
    model_key = (model or "").lower().strip()
    date_key = target_date or get_today_iso_date()
    cache_key = f"{model_key}::{date_key}"

    if cache_key in _PRICING_CACHE:
        return _PRICING_CACHE[cache_key]

    # Try Firestore query if db client is provided
    if db is not None:
        try:
            docs = list(
                db.collection("model_pricing")
                .where("model_name", "==", model_key)
                .where("effective_date", "<=", date_key)
                .order_by("effective_date", direction="DESCENDING")
                .limit(1)
                .stream()
            )
            if docs:
                p_data = docs[0].to_dict()
                _PRICING_CACHE[cache_key] = p_data
                return p_data
        except Exception as err:
            logger.debug(f"Firestore model pricing lookup note for {model_key}: {err}")

    # Fallback to seed lookup with fuzzy model matching
    pricing = MODEL_PRICING.get(model_key)
    if not pricing:
        for k, v in MODEL_PRICING.items():
            if k in model_key or model_key in k:
                pricing = v
                break
    if not pricing:
        pricing = DEFAULT_FALLBACK_PRICING

    _PRICING_CACHE[cache_key] = pricing
    return pricing


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
    target_date: Optional[str] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Calculates USD and SGD costs based on time-based model pricing table, token usage,
    image resolution tier, images generated, and daily exchange rate.
    Strictly rounds up both USD and SGD costs to 3 decimal places.
    """
    date_str = target_date or get_today_iso_date()
    pricing = get_model_pricing_for_date(model=model, target_date=date_str, db=db)

    # Determine per-image unit cost by resolution tier
    rates_dict = pricing.get("image_rates", {})
    eff_size = (image_size or "4K").upper().strip()
    unit_image_cost = rates_dict.get(eff_size)
    if unit_image_cost is None:
        unit_image_cost = rates_dict.get("default", pricing.get("per_image_cost", 0.0))

    prompt_cost_usd_raw = (prompt_tokens / 1_000_000.0) * float(pricing.get("prompt_cost_per_m", 0.0))
    candidates_cost_usd_raw = (candidates_tokens / 1_000_000.0) * float(pricing.get("candidates_cost_per_m", 0.0))
    images_cost_usd_raw = images_count * float(unit_image_cost)
    total_cost_usd_raw = prompt_cost_usd_raw + candidates_cost_usd_raw + images_cost_usd_raw
    total_tokens = prompt_tokens + candidates_tokens

    # Fetch daily exchange rate
    exchange_rate = get_daily_exchange_rate(target_date=date_str, db=db)
    total_cost_sgd_raw = total_cost_usd_raw * exchange_rate

    # Ceiling rounding to 3 decimals
    cost_usd = round_up_cost(total_cost_usd_raw, 3)
    cost_sgd = round_up_cost(total_cost_sgd_raw, 3)

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "candidates_tokens": candidates_tokens,
        "total_tokens": total_tokens,
        "images_count": images_count,
        "image_size": eff_size,
        "cost_usd": cost_usd,
        "cost_sgd": cost_sgd,
        "exchange_rate": exchange_rate,
        "exchange_rate_date": date_str,
        "effective_date": pricing.get("effective_date", "2025-01-01"),
        "breakdown": {
            "prompt_cost_usd": round_up_cost(prompt_cost_usd_raw, 3),
            "candidates_cost_usd": round_up_cost(candidates_cost_usd_raw, 3),
            "images_cost_usd": round_up_cost(images_cost_usd_raw, 3),
            "prompt_cost_sgd": round_up_cost(prompt_cost_usd_raw * exchange_rate, 3),
            "candidates_cost_sgd": round_up_cost(candidates_cost_usd_raw * exchange_rate, 3),
            "images_cost_sgd": round_up_cost(images_cost_usd_raw * exchange_rate, 3),
            "per_image_rate_usd": round_up_cost(float(unit_image_cost), 3),
        },
    }
