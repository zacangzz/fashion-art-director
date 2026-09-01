import io
import pytest
import os
import json
import base64
import hashlib
from PIL import Image
from unittest.mock import MagicMock, patch
from app.services.generation_service import (
    GenerationService,
    compile_prompt,
    compile_delta_prompt,
    get_modified_categories,
)
from app.services.image_generator import ImageGenerator
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


def create_dummy_png_bytes(width=100, height=100, color=(100, 150, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_mock_interactions_client(png_bytes: bytes):
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image.data = base64.b64encode(png_bytes).decode("utf-8")
    mock_interaction.output_text = "generated image"
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=200, candidates_token_count=256, total_token_count=456)
    mock_client.interactions.create.return_value = mock_interaction
    return mock_client


def test_compile_prompt_modular_narrative():
    narrative = "A stunning cinematic visual of a child on a patio."
    categories = {
        "subject_details": [{"label": "young boy with ginger hair", "weight": 1.0, "enabled": True}],
        "wardrobe_hair": [{"label": "cream knit sweater", "weight": 1.0, "enabled": True}],
        "environment": [{"label": "sunlit stone terrace", "weight": 1.0, "enabled": True}],
        "objects_props": [{"label": "terracotta outdoor sofa", "weight": 1.0, "enabled": True}],
        "layout_framing": [{"label": "medium-wide shot", "weight": 1.0, "enabled": True}],
        "camera_optics": [{"label": "35mm prime lens", "weight": 1.5, "enabled": True}],
        "lighting": [{"label": "golden hour sunlight", "weight": 1.0, "enabled": True}],
        "color_profile": [{"label": "warm earthy palette", "weight": 1.0, "enabled": True}],
        "mood_era": [{"label": "1970s retro luxury", "weight": 1.0, "enabled": True}],
    }

    compiled = compile_prompt(narrative=narrative, categories=categories)
    assert "A stunning cinematic visual of a child on a patio." in compiled
    assert "Subject: young boy with ginger hair, wearing cream knit sweater." in compiled
    assert "Environment: set in sunlit stone terrace, featuring terracotta outdoor sofa." in compiled
    assert "Composition: medium-wide shot, shot on 35mm prime lens." in compiled
    assert "Lighting & Color: illuminated with golden hour sunlight, color palette of warm earthy palette." in compiled
    assert "Aesthetic: 1970s retro luxury." in compiled


def test_compile_delta_prompt_preservation_and_adjustments():
    baseline_categories = {
        "subject_details": [{"label": "young boy with ginger hair", "weight": 1.0, "enabled": True}],
        "wardrobe_hair": [{"label": "cream knit sweater", "weight": 1.0, "enabled": True}],
        "environment": [{"label": "sunlit stone terrace", "weight": 1.0, "enabled": True}],
        "lighting": [{"label": "golden hour sunlight", "weight": 1.0, "enabled": True}],
    }
    current_categories = {
        "subject_details": [{"label": "young boy with ginger hair", "weight": 1.0, "enabled": True}],
        "wardrobe_hair": [{"label": "navy blue pea coat", "weight": 1.0, "enabled": True}],
        "environment": [{"label": "sunlit stone terrace", "weight": 1.0, "enabled": True}],
        "lighting": [{"label": "golden hour sunlight", "weight": 1.0, "enabled": True}],
    }

    delta_prompt = compile_delta_prompt(
        narrative="Child on the terrace with a darker jacket.",
        categories=current_categories,
        baseline_narrative="Child on the terrace in sweater.",
        baseline_categories=baseline_categories,
        locked_categories=["subject_details", "environment"],
    )

    assert "Visual Reference Foundation" in delta_prompt
    assert "Requested Modifications" in delta_prompt
    assert "navy blue pea coat" in delta_prompt


def test_fine_tune_generation_mocked(tmp_path):
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    parent_path = os.path.join(gen_dir, "gen_base_01_master.png")
    with open(parent_path, "wb") as f:
        f.write(create_dummy_png_bytes())

    db_mgr.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_base_01",
            "parent_id": None,
            "moodboard_id": "mb_test_123",
            "is_baseline": True,
            "schema_json": {"narrative": "parent goal"},
            "compiled_prompt": "parent prompt",
            "negative_prompt": "blurry",
            "seed": 918231,
            "master_image_path": parent_path,
            "aspect_ratio": "2:3",
            "resolution_width": 1080,
            "resolution_height": 1620,
        }
    )

    dummy_png = create_dummy_png_bytes()
    mock_client = create_mock_interactions_client(dummy_png)
    image_generator = ImageGenerator(client=mock_client)

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake_key",
        storage_dir=storage_dir,
        client=mock_client,
        image_generator=image_generator,
    )
    state = {
        "narrative": "Fine-tuned goal with altered lighting.",
        "categories": {
            "lighting": [{"label": "dramatic rim light", "weight": 1.0, "enabled": True}],
        },
    }
    res = service.fine_tune_generation(
        parent_id="gen_base_01",
        state=state,
        seed=918231,
        use_image_reference=True,
        user_id="local_dev_user",
    )

    assert res["generation_id"].startswith("gen_")
    assert res["parent_id"] == "gen_base_01"
    assert res["seed"] == 918231
    assert "Fine-tuned goal with altered lighting." in res["compiled_prompt"]
    assert "dramatic rim light" in res["compiled_prompt"]

    child_rec = db_mgr.get_generation(res["generation_id"])
    assert child_rec is not None
    assert child_rec["parent_id"] == "gen_base_01"


def test_fine_tune_generation_with_tag_chip_instances(tmp_path):
    from app.schemas.domain import TagChip, TagCategory

    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    parent_path = os.path.join(gen_dir, "gen_base_02_master.png")
    with open(parent_path, "wb") as f:
        f.write(create_dummy_png_bytes())

    db_mgr.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_base_02",
            "parent_id": None,
            "moodboard_id": "mb_test_456",
            "is_baseline": True,
            "schema_json": {"narrative": "parent"},
            "compiled_prompt": "parent prompt",
            "negative_prompt": "blurry",
            "seed": 123456,
            "master_image_path": parent_path,
            "aspect_ratio": "2:3",
            "resolution_width": 1080,
            "resolution_height": 1620,
        }
    )

    dummy_png = create_dummy_png_bytes()
    mock_client = create_mock_interactions_client(dummy_png)
    image_generator = ImageGenerator(client=mock_client)

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake_key",
        storage_dir=storage_dir,
        client=mock_client,
        image_generator=image_generator,
    )
    chip = TagChip(id="tag_1", category=TagCategory.SUBJECT_DETAILS, label="copper hair model", enabled=True, locked=False)
    
    res = service.fine_tune_generation(
        parent_id="gen_base_02",
        narrative="Refined scene with Pydantic chips",
        categories={"subject_details": [chip]},
        seed=123456,
        use_image_reference=False,
        user_id="local_dev_user",
    )

    assert res["generation_id"].startswith("gen_")
    assert "copper hair model" in res["compiled_prompt"]
    
    child = db_mgr.get_generation(res["generation_id"])
    assert child is not None


def test_analyze_mask_bytes():
    from app.utils.image_utils import analyze_mask_bytes

    img = Image.new("RGB", (100, 100), color="black")
    for y in range(20, 40):
        for x in range(10, 30):
            img.putpixel((x, y), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    mask_bytes = buf.getvalue()

    stats = analyze_mask_bytes(mask_bytes)
    assert stats["width"] == 100
    assert stats["height"] == 100
    assert stats["total_pixels"] == 10000
    assert stats["masked_pixels"] == 400
    assert stats["unmasked_pixels"] == 9600
    assert stats["coverage_percentage"] == 4.0
    assert stats["bounding_box"] == {
        "min_x": 10,
        "min_y": 20,
        "max_x": 29,
        "max_y": 39,
        "width": 20,
        "height": 20,
    }


def test_inpaint_region_audit_and_mask_tracking(tmp_path):
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    dummy_png = create_dummy_png_bytes(width=200, height=200)
    mock_client = create_mock_interactions_client(dummy_png)
    image_generator = ImageGenerator(client=mock_client)

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake_key",
        storage_dir=storage_dir,
        client=mock_client,
        image_generator=image_generator,
    )

    mask_img = Image.new("RGB", (200, 200), color="black")
    for y in range(50, 100):
        for x in range(50, 100):
            mask_img.putpixel((x, y), (255, 255, 255))
    mb = io.BytesIO()
    mask_img.save(mb, format="PNG")
    mask_bytes = mb.getvalue()

    res = service.inpaint_region(
        parent_id="",
        image_bytes=dummy_png,
        mask_bytes=mask_bytes,
        prompt="Change handbag to a red clutch",
        seed=777888,
        aspect_ratio="1:1",
        user_id="local_dev_user",
    )

    assert res["generation_id"].startswith("gen_")
    assert res["seed"] == 777888
    assert res["mask_stats"]["coverage_percentage"] == 6.25

    rec = db_mgr.get_generation(res["generation_id"])
    assert rec is not None
