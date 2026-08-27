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
REFINEMENT_SYSTEM_PROMPT = load_prompt("refinement_system.txt")
WARDROBE_SEGMENTATION_PROMPT = load_prompt("wardrobe_segmentation.txt")
WARDROBE_COMPOSITION_SYSTEM_PROMPT = load_prompt("wardrobe_composition_system.txt")
CLOTHING_REGION_DETECTION_PROMPT = load_prompt("clothing_region_detection.txt")
SUBJECT_GROUNDING_PROMPT = load_prompt("subject_grounding_system.txt")
RESYNC_MASTER_PROMPT_SYSTEM = load_prompt("resync_master_prompt_system.txt")
RESYNC_MASTER_PROMPT_TEMPLATE = load_prompt("resync_master_prompt_template.txt")

