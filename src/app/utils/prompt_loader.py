import json
from pathlib import Path
from typing import Any


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def load_json(filename: str) -> Any:
    return json.loads(load_prompt(filename))


EXTRACTION_SYSTEM_PROMPT = load_prompt("extraction_system.txt")
USER_BASELINE_TEMPLATE = load_prompt("user_baseline_template.txt")
IMAGE_GENERATION_SUFFIX = load_prompt("image_generation_suffix.txt")
DEFAULT_NEGATIVE_PROMPT = load_json("defaults.json").get(
    "negative_prompt",
    "blurry, distorted, extra limbs, low quality, artifacts, watermark, text"
)
INPAINT_SYSTEM_PROMPT = load_prompt("inpaint_system.txt")
INPAINT_SUFFIX = load_prompt("inpaint_suffix.txt")
