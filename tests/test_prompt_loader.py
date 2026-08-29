import json

from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    INPAINT_SUFFIX,
    INPAINT_SYSTEM_PROMPT,
    USER_BASELINE_TEMPLATE,
)


def test_prompt_assets_are_loaded_and_composed():
    assert "categories" in EXTRACTION_SYSTEM_PROMPT
    assert "subject_details" in EXTRACTION_SYSTEM_PROMPT
    assert "wardrobe_hair" in EXTRACTION_SYSTEM_PROMPT
    assert "camera_optics" in EXTRACTION_SYSTEM_PROMPT
    assert "e.g." not in EXTRACTION_SYSTEM_PROMPT
    assert "realistic teeth texture" in EXTRACTION_SYSTEM_PROMPT
    assert "{USER_PROMPT}" in USER_BASELINE_TEMPLATE
    assert "realistic teeth texture" in USER_BASELINE_TEMPLATE
    assert "{ASPECT_RATIO}" in IMAGE_GENERATION_SUFFIX
    assert "{SEED}" in IMAGE_GENERATION_SUFFIX
    assert "{NEGATIVE_PROMPT}" in IMAGE_GENERATION_SUFFIX
    assert "{RESOLUTION}" in INPAINT_SYSTEM_PROMPT
    assert "{ASPECT_RATIO}" in INPAINT_SYSTEM_PROMPT
    assert "realistic teeth texture" in INPAINT_SYSTEM_PROMPT
    assert "{RESOLUTION}" in INPAINT_SUFFIX
    assert "{ASPECT_RATIO}" in INPAINT_SUFFIX
    assert "blurry" in DEFAULT_NEGATIVE_PROMPT
    assert "unnaturally white teeth" in DEFAULT_NEGATIVE_PROMPT
    assert "fused teeth" in DEFAULT_NEGATIVE_PROMPT

