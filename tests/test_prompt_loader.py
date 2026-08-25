import json

from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    USER_BASELINE_TEMPLATE,
)


def test_prompt_assets_are_loaded_and_composed():
    assert "categories" in EXTRACTION_SYSTEM_PROMPT
    assert "subject_details" in EXTRACTION_SYSTEM_PROMPT
    assert "wardrobe_hair" in EXTRACTION_SYSTEM_PROMPT
    assert "camera_optics" in EXTRACTION_SYSTEM_PROMPT
    assert "{USER_PROMPT}" in USER_BASELINE_TEMPLATE
    assert "{ASPECT_RATIO}" in IMAGE_GENERATION_SUFFIX
    assert "{SEED}" in IMAGE_GENERATION_SUFFIX
    assert "{NEGATIVE_PROMPT}" in IMAGE_GENERATION_SUFFIX
    assert "blurry" in DEFAULT_NEGATIVE_PROMPT
