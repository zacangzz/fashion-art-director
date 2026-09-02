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
from app.services.storage_service import StorageService
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


def test_refinement_generation_lineage_and_color_anchor(tmp_path):
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    dummy_png = create_dummy_png_bytes(width=200, height=200)
    fake_blob.download_as_bytes.return_value = dummy_png
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local", storage_dir=storage_dir)

    # 1. Create root baseline generation in DB
    root_path = storage_service.upload_bytes(
        user_id="local_dev_user",
        category="generations",
        filename="gen_root_refine_master.png",
        data=dummy_png,
    )
    db_mgr.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_root_refine",
            "parent_id": None,
            "moodboard_id": None,
            "is_baseline": True,
            "created_at": "2026-09-01T10:00:00Z",
            "schema_json": {},
            "compiled_prompt": "Root scene before refinement",
            "negative_prompt": "blurry",
            "seed": 112233,
            "master_image_path": root_path,
            "aspect_ratio": "2:3",
            "resolution_width": 2560,
            "resolution_height": 3840,
            "model_name": "gemini-3-pro-image",
            "cost_usd": 0.04,
            "tokens": 1000,
            "accumulated_cost_usd": 0.04,
            "accumulated_tokens": 1000,
        },
    )

    # 2. Create Turn 1 refinement in DB
    turn1_path = storage_service.upload_bytes(
        user_id="local_dev_user",
        category="generations",
        filename="gen_turn1_refine_master.png",
        data=dummy_png,
    )
    db_mgr.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_turn1_refine",
            "parent_id": "gen_root_refine",
            "moodboard_id": None,
            "is_baseline": False,
            "created_at": "2026-09-01T10:05:00Z",
            "schema_json": {"refinement_prompt": "Make background softer"},
            "compiled_prompt": "Turn 1 refinement",
            "negative_prompt": "blurry",
            "seed": 112233,
            "master_image_path": turn1_path,
            "aspect_ratio": "2:3",
            "resolution_width": 2560,
            "resolution_height": 3840,
            "model_name": "gemini-3-pro-image",
            "cost_usd": 0.04,
            "tokens": 1000,
            "accumulated_cost_usd": 0.08,
            "accumulated_tokens": 2000,
        },
    )

    # 3. Setup mock client
    mock_client = create_mock_interactions_client(dummy_png)
    image_generator = ImageGenerator(client=mock_client)
    service = GenerationService(
        db_manager=db_mgr,
        storage_service=storage_service,
        client=mock_client,
        image_generator=image_generator,
    )

    # Turn 1 refinement from root baseline
    res_t1 = service.refine_generation(
        parent_id="gen_root_refine",
        prompt="Add sunglasses to subject",
        seed=112233,
        user_id="local_dev_user",
    )
    assert res_t1["generation_id"] is not None
    assert "{USER_PROMPT}" not in res_t1["compiled_prompt"]
    assert "Add sunglasses to subject" in res_t1["compiled_prompt"]
    assert "Color Constancy Lock" in res_t1["compiled_prompt"]
    assert "PROGRESSIVE REFINEMENT TURN #2" not in res_t1["compiled_prompt"]

    # Turn 2 progressive refinement from Turn 1 (Lineage Depth = 1)
    res_t2 = service.refine_generation(
        parent_id="gen_turn1_refine",
        prompt="Adjust lighting to subtle rim light",
        seed=112233,
        user_id="local_dev_user",
    )
    assert res_t2["generation_id"] is not None
    assert "{USER_PROMPT}" not in res_t2["compiled_prompt"]
    assert "Adjust lighting to subtle rim light" in res_t2["compiled_prompt"]
    assert "PROGRESSIVE REFINEMENT TURN #2 CHROMATIC ANCHOR" in res_t2["compiled_prompt"]
    assert "Maintain absolute color temperature, neutral white balance" in res_t2["compiled_prompt"]

    # Verify mock_client received single reference image [parent] for Turn 2
    _, last_call_kwargs = mock_client.interactions.create.call_args
    api_input = last_call_kwargs.get("input", [])
    assert isinstance(api_input, list)
    image_inputs = [item for item in api_input if isinstance(item, dict) and item.get("type") == "image"]
    assert len(image_inputs) == 1


def test_compile_delta_prompt_color_constancy_lock():
    baseline_categories = {
        "wardrobe_hair": [{"label": "white cotton t-shirt", "weight": 1.0, "enabled": True}],
    }
    current_categories = {
        "wardrobe_hair": [{"label": "charcoal wool coat", "weight": 1.0, "enabled": True}],
    }
    delta_prompt = compile_delta_prompt(
        narrative="Updated outerwear.",
        categories=current_categories,
        baseline_narrative="Original baseline.",
        baseline_categories=baseline_categories,
    )
    assert "Color Constancy & Calibrated White Balance Lock" in delta_prompt
    assert "Kelvin color temperature" in delta_prompt
    assert "color bounce" not in delta_prompt


def test_inpaint_prompt_color_constancy_lock():
    from app.services.prompt_compiler import PromptCompiler

    mask_stats = {
        "coverage_percentage": 10.5,
        "bounding_box": {"min_x": 50, "min_y": 50, "max_x": 150, "max_y": 150},
        "normalized_bounding_box": {"min_x": 0.25, "min_y": 0.25, "max_x": 0.75, "max_y": 0.75},
        "centroid": {"x": 100, "y": 100, "norm_x": 0.5, "norm_y": 0.5},
    }
    inpaint_prompt = PromptCompiler.format_inpaint_prompt(
        prompt="Swap leather bag for canvas tote",
        mask_stats=mask_stats,
        aspect_ratio="2:3",
    )
    assert "Color Constancy & White Balance Lock" in inpaint_prompt
    assert "Kelvin color temperature" in inpaint_prompt


def test_image_optimization_lossless_png_and_icc_retention():
    from app.utils.image_utils import optimize_reference_image

    # Create image with specific distinct RGB values
    img = Image.new("RGB", (100, 100), color=(142, 88, 210))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    original_bytes = buf.getvalue()

    opt_bytes, mime = optimize_reference_image(original_bytes, max_dimension=2048, target_format="PNG")
    assert mime == "image/png"

    # Re-open and verify pixel channel integrity
    re_opened = Image.open(io.BytesIO(opt_bytes))
    pixel = re_opened.getpixel((50, 50))
    assert pixel == (142, 88, 210)

