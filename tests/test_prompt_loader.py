import json

from app.utils.prompt_loader import (
    DEFAULT_NEGATIVE_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    IMAGE_GENERATION_SUFFIX,
    INPAINT_SUFFIX,
    INPAINT_SYSTEM_PROMPT,
    USER_BASELINE_TEMPLATE,
    RESYNC_MASTER_PROMPT_SYSTEM,
    RESYNC_MASTER_PROMPT_TEMPLATE,
    RESYNC_PROMPT_FROM_LEVERS_SYSTEM,
    RESYNC_PROMPT_FROM_LEVERS_TEMPLATE,
    RESYNC_LEVERS_FROM_PROMPT_SYSTEM,
    RESYNC_LEVERS_FROM_PROMPT_TEMPLATE,
    CHECK_CONFLICTS_SYSTEM_PROMPT,
)


def test_prompt_assets_are_loaded_and_composed():
    # Extraction System
    assert "categories" in EXTRACTION_SYSTEM_PROMPT
    assert "subject_details" in EXTRACTION_SYSTEM_PROMPT
    assert "wardrobe_hair" in EXTRACTION_SYSTEM_PROMPT
    assert "camera_optics" in EXTRACTION_SYSTEM_PROMPT
    assert "e.g." not in EXTRACTION_SYSTEM_PROMPT
    assert "realistic teeth texture" in EXTRACTION_SYSTEM_PROMPT
    assert "Nano Banana" in EXTRACTION_SYSTEM_PROMPT
    assert "gemini-3.1-flash-image" in EXTRACTION_SYSTEM_PROMPT
    assert "STRUCTURED SEQUENTIAL PROSE" in EXTRACTION_SYSTEM_PROMPT
    assert "HYPER-SPECIFICITY" in EXTRACTION_SYSTEM_PROMPT
    assert "Creative Intent & Scene Context" in EXTRACTION_SYSTEM_PROMPT
    assert "1 or more" in EXTRACTION_SYSTEM_PROMPT
    assert "1 to 5" not in EXTRACTION_SYSTEM_PROMPT
    assert "Imagen" not in EXTRACTION_SYSTEM_PROMPT

    # User Baseline Template
    assert "{USER_PROMPT}" in USER_BASELINE_TEMPLATE
    assert "realistic teeth texture" in USER_BASELINE_TEMPLATE
    assert "Nano Banana" in USER_BASELINE_TEMPLATE
    assert "gemini-3.1-flash-image" in USER_BASELINE_TEMPLATE
    assert "structured sequential prose" in USER_BASELINE_TEMPLATE

    # Resync Master Prompt
    assert "Nano Banana" in RESYNC_MASTER_PROMPT_SYSTEM
    assert "gemini-3.1-flash-image" in RESYNC_MASTER_PROMPT_SYSTEM
    assert "STRUCTURED SEQUENTIAL PROSE" in RESYNC_MASTER_PROMPT_SYSTEM
    assert "HYPER-SPECIFICITY" in RESYNC_MASTER_PROMPT_SYSTEM
    assert "1 or more" in RESYNC_MASTER_PROMPT_SYSTEM
    assert "Imagen" not in RESYNC_MASTER_PROMPT_SYSTEM
    assert "{PREVIOUS_MASTER_PROMPT}" in RESYNC_MASTER_PROMPT_TEMPLATE
    assert "{UPDATED_CATEGORIES_JSON}" in RESYNC_MASTER_PROMPT_TEMPLATE
    assert "Nano Banana" in RESYNC_MASTER_PROMPT_TEMPLATE

    # Resync Prompt from Levers
    assert "Nano Banana" in RESYNC_PROMPT_FROM_LEVERS_SYSTEM
    assert "gemini-3.1-flash-image" in RESYNC_PROMPT_FROM_LEVERS_SYSTEM
    assert "STRUCTURED SEQUENTIAL PROSE" in RESYNC_PROMPT_FROM_LEVERS_SYSTEM
    assert "Imagen" not in RESYNC_PROMPT_FROM_LEVERS_SYSTEM
    assert "{CATEGORIES_JSON}" in RESYNC_PROMPT_FROM_LEVERS_TEMPLATE
    assert "Nano Banana" in RESYNC_PROMPT_FROM_LEVERS_TEMPLATE

    # Resync Levers from Prompt
    assert "Nano Banana" in RESYNC_LEVERS_FROM_PROMPT_SYSTEM
    assert "gemini-3.1-flash-image" in RESYNC_LEVERS_FROM_PROMPT_SYSTEM
    assert "HYPER-SPECIFICITY" in RESYNC_LEVERS_FROM_PROMPT_SYSTEM
    assert "1 or more" in RESYNC_LEVERS_FROM_PROMPT_SYSTEM
    assert "Imagen" not in RESYNC_LEVERS_FROM_PROMPT_SYSTEM
    assert "{MASTER_PROMPT}" in RESYNC_LEVERS_FROM_PROMPT_TEMPLATE
    assert "Nano Banana" in RESYNC_LEVERS_FROM_PROMPT_TEMPLATE

    # Check Conflicts
    assert "Nano Banana" in CHECK_CONFLICTS_SYSTEM_PROMPT
    assert "gemini-3.1-flash-image" in CHECK_CONFLICTS_SYSTEM_PROMPT
    assert "Imagen" not in CHECK_CONFLICTS_SYSTEM_PROMPT

    # Suffixes & Inpainting
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
