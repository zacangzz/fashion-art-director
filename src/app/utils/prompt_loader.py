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
RESYNC_PROMPT_FROM_LEVERS_SYSTEM = load_prompt("resync_prompt_from_levers_system.txt")
RESYNC_PROMPT_FROM_LEVERS_TEMPLATE = load_prompt("resync_prompt_from_levers_template.txt")
RESYNC_LEVERS_FROM_PROMPT_SYSTEM = load_prompt("resync_levers_from_prompt_system.txt")
RESYNC_LEVERS_FROM_PROMPT_TEMPLATE = load_prompt("resync_levers_from_prompt_template.txt")
CHECK_CONFLICTS_SYSTEM_PROMPT = load_prompt("check_conflicts_system.txt")
GARMENT_UPSCALE_SYSTEM_PROMPT = load_prompt("garment_upscale_system.txt")
GARMENT_FEATURE_EXTRACTION_PROMPT = load_prompt("garment_feature_extraction.txt")
BACKGROUND_HARMONIZATION_TEMPLATE = load_prompt("background_harmonization_template.txt")
SPATIAL_SCENE_ANALYSIS_TEMPLATE = load_prompt("spatial_scene_analysis.txt")
PROP_SEGMENTATION_PROMPT = load_prompt("prop_segmentation.txt")
PROP_FEATURE_EXTRACTION_PROMPT = load_prompt("prop_feature_extraction.txt")
PROP_UPSCALE_SYSTEM_PROMPT = load_prompt("prop_upscale_system.txt")
PROP_SCENE_GROUNDING_PROMPT = load_prompt("prop_scene_grounding.txt")
PROP_COMPOSITION_SYSTEM_PROMPT = load_prompt("prop_composition_system.txt")

