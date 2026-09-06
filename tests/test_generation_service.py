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
    from app.utils.image_utils import optimize_reference_image, get_standard_srgb_profile_bytes

    # Create image with specific distinct RGB values
    img = Image.new("RGB", (100, 100), color=(142, 88, 210))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    original_bytes = buf.getvalue()

    opt_bytes, mime = optimize_reference_image(original_bytes, max_dimension=2048, target_format="PNG")
    assert mime == "image/png"

    # Re-open and verify pixel channel integrity and ICC profile
    re_opened = Image.open(io.BytesIO(opt_bytes))
    pixel = re_opened.getpixel((50, 50))
    assert pixel == (142, 88, 210)
    assert "icc_profile" in re_opened.info
    assert len(re_opened.info["icc_profile"]) == len(get_standard_srgb_profile_bytes())


def test_standardize_image_to_srgb_embeds_icc_profile():
    from app.utils.image_utils import standardize_image_to_srgb, get_standard_srgb_profile_bytes

    # Create untagged raw RGB image
    img = Image.new("RGB", (50, 50), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_untagged = buf.getvalue()

    # Verify initially untagged
    initial = Image.open(io.BytesIO(raw_untagged))
    assert initial.info.get("icc_profile") is None

    # Standardize
    std_bytes = standardize_image_to_srgb(raw_untagged, target_format="PNG")
    re_opened = Image.open(io.BytesIO(std_bytes))
    assert "icc_profile" in re_opened.info
    assert len(re_opened.info["icc_profile"]) == len(get_standard_srgb_profile_bytes())


def test_save_generation_image_embeds_srgb_profile(tmp_path):
    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local", storage_dir=storage_dir)

    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    service = GenerationService(
        db_manager=db_mgr,
        storage_service=storage_service,
    )

    # Raw untagged image from GenAI server
    img = Image.new("RGB", (80, 120), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    master_path, w, h = service._save_generation_image("user_123", "gen_test_01.png", raw_bytes, "2:3")
    assert w == 80
    assert h == 120

    # Read back from storage
    saved_bytes = storage_service.download_bytes(master_path)
    saved_img = Image.open(io.BytesIO(saved_bytes))
    assert "icc_profile" in saved_img.info
    assert len(saved_img.info["icc_profile"]) > 0


def test_conform_uploaded_image_smart_canvas_fit_4_5():
    from app.utils.image_utils import conform_uploaded_image, get_standard_srgb_profile_bytes

    # Create image simulating FT3.png (1651 x 1838) with specific center color
    img = Image.new("RGB", (1651, 1838), color=(120, 200, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    conformed_bytes, aspect, w, h = conform_uploaded_image(raw_bytes)

    assert aspect == "4:5"
    assert w == 1651
    assert h == 2064
    assert round(w / h, 2) == 0.80

    # Verify center pixel is untouched and ICC profile is attached
    re_opened = Image.open(io.BytesIO(conformed_bytes))
    assert re_opened.size == (1651, 2064)
    center_pixel = re_opened.getpixel((1651 // 2, 2064 // 2))
    assert center_pixel == (120, 200, 150)
    assert "icc_profile" in re_opened.info
    assert len(re_opened.info["icc_profile"]) == len(get_standard_srgb_profile_bytes())


def test_conform_uploaded_image_downscales_oversized():
    from app.utils.image_utils import conform_uploaded_image

    # Create oversized image: 4800 x 3200 (3:2 ratio)
    img = Image.new("RGB", (4800, 3200), color=(100, 120, 140))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    conformed_bytes, aspect, w, h = conform_uploaded_image(raw_bytes, max_dimension=3840)

    assert aspect == "3:2"
    assert max(w, h) <= 3840
    assert w == 3840
    assert h == 2560


def test_wardrobe_service_generate_photo_scene_description():
    from app.services.wardrobe_service import WardrobeService
    from app.utils.prompt_loader import PHOTO_INGESTION_SYSTEM_PROMPT

    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    storage_service = MagicMock()
    mock_client = MagicMock()

    mock_interaction = MagicMock()
    mock_interaction.output_text = "A candid, atmospheric worm's-eye view of two young siblings on a lush meadow."
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=150, candidates_token_count=80, total_token_count=230)
    mock_client.interactions.create.return_value = mock_interaction

    wardrobe_service = WardrobeService(
        db_manager=db_mgr,
        api_key="mock_key",
        storage_service=storage_service,
        client=mock_client,
    )

    dummy_bytes = create_dummy_png_bytes(200, 200)
    desc = wardrobe_service.generate_photo_scene_description(dummy_bytes, vision_model="gemini-3.5-flash-lite")

    assert "worm's-eye view of two young siblings" in desc
    mock_client.interactions.create.assert_called_once()
    call_kwargs = mock_client.interactions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.5-flash-lite"
    assert any("Scene Context & Atmosphere" in str(item) for item in call_kwargs["input"])


def test_register_uploaded_photo_conforms_and_extracts_prose(tmp_path):
    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local", storage_dir=storage_dir)

    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    wardrobe_service = MagicMock()
    wardrobe_service.generate_photo_scene_description.return_value = "Worm's-eye shot of kids on grass."

    service = GenerationService(
        db_manager=db_mgr,
        storage_service=storage_service,
        wardrobe_service=wardrobe_service,
    )

    # 1651 x 1838 input
    raw_bytes = create_dummy_png_bytes(1651, 1838)
    result = service.register_uploaded_photo(raw_bytes, filename="FT3.png", user_id="test_user")

    assert result["aspect_ratio"] == "4:5"
    assert result["compiled_prompt"] == "Worm's-eye shot of models on grass."
    assert result["resolution"] == {"width": 1651, "height": 2064}

    # Verify Firestore document
    gen_doc = db_mgr.get_generation(result["generation_id"])
    assert gen_doc is not None
    assert gen_doc["compiled_prompt"] == "Worm's-eye shot of models on grass."
    assert gen_doc["aspect_ratio"] == "4:5"
    assert gen_doc["schema_json"]["has_scene_prose"] is True


def test_compose_wardrobe_legacy_upload_on_the_fly_fallback_and_locks(tmp_path):
    storage_dir = str(tmp_path / "storage")
    os.makedirs(os.path.join(storage_dir, "generations"), exist_ok=True)
    os.makedirs(os.path.join(storage_dir, "wardrobe"), exist_ok=True)

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local", storage_dir=storage_dir)

    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    # Legacy upload with generic placeholder prompt
    parent_img_bytes = create_dummy_png_bytes(1651, 2064)
    parent_path = storage_service.upload_bytes(
        user_id="test_user",
        category="generations",
        filename="gen_upload_legacy_master.png",
        data=parent_img_bytes,
    )

    db_mgr.create_generation(
        user_id="test_user",
        gen_data={
            "id": "gen_upload_legacy",
            "master_image_path": parent_path,
            "compiled_prompt": "Directly ingested photo: Ft3",
            "prompt": "Directly ingested photo: Ft3",
            "model_name": "direct_upload",
            "aspect_ratio": "4:5",
            "seed": 12345,
        }
    )

    # Wardrobe item
    crop_path = storage_service.upload_bytes(
        user_id="test_user",
        category="wardrobe",
        filename="crop_kenzo.png",
        data=create_dummy_png_bytes(200, 200),
    )
    db_mgr.create_wardrobe_item(
        user_id="test_user",
        item_data={
            "id": "item_kenzo",
            "label": "Kenzo Tiger T-Shirt",
            "category": "tops",
            "cropped_image_path": crop_path,
            "extracted_details": {
                "has_text_or_logo": True,
                "exact_text_content": ["KENZO PARIS"],
                "has_graphic_or_print": True,
                "graphic_description": "Embroidered tiger graphic",
            }
        }
    )

    wardrobe_service = MagicMock()
    wardrobe_service.generate_photo_scene_description.return_value = "Master scene: extreme worm's-eye view of children on grass with daisies."
    wardrobe_service.ground_wardrobe_pins.return_value = {
        "grounded_pins": [{
            "pin_number": 1,
            "target_subject": "boy in yellow shorts",
            "body_location": "upper torso",
            "spatial_anchor": "left side of frame",
        }],
        "unmodified_subjects_guardrail": "Keep girl on right strictly unchanged.",
    }

    image_generator = MagicMock()
    image_generator.generate.return_value = create_dummy_png_bytes(1651, 2064)
    image_generator.last_call_metrics = {"cost_usd": 0.04, "total_token_count": 500}

    service = GenerationService(
        db_manager=db_mgr,
        storage_service=storage_service,
        image_generator=image_generator,
        wardrobe_service=wardrobe_service,
    )

    res = service.compose_wardrobe(
        parent_id="gen_upload_legacy",
        assignments=[{"pin_number": 1, "wardrobe_item_id": "item_kenzo"}],
        user_id="test_user",
    )

    # 1. On-the-fly ingestion was triggered and parent record updated
    wardrobe_service.generate_photo_scene_description.assert_called_once()
    updated_parent = db_mgr.get_generation("gen_upload_legacy")
    assert "Master scene: extreme worm's-eye view" in updated_parent["compiled_prompt"]

    # 2. Inspect prompt passed to image_generator
    call_args = image_generator.generate.call_args.kwargs
    prompt_text = call_args["prompt"]
    assert "REFERENCE BASE SCENE ANCHOR" in prompt_text
    assert "Master scene: extreme worm's-eye view" in prompt_text
    assert "CANVAS & PERSPECTIVE LOCK" in prompt_text
    assert "(shown in Reference Image #2)" in prompt_text

    # Verify safety filter sanitization: minor and raw anatomy terms are scrubbed
    assert "boy" not in prompt_text.lower()
    assert "girl" not in prompt_text.lower()
    assert "children" not in prompt_text.lower()
    assert "upper torso" not in prompt_text.lower()
    assert "model in yellow shorts" in prompt_text
    assert "upper garment area" in prompt_text
    assert "Keep model on right strictly unchanged" in prompt_text

    # 3. Verify reference images count passed
    assert len(call_args["reference_images"]) == 2


def test_sanitize_prompt_for_safety_scrubs_minor_and_anatomy_terms():
    from app.utils.prompt_loader import sanitize_prompt_for_safety

    # 1. Minor terms and age demographics
    raw_prompt = (
        "Two young boys standing heroically. Left subject, a younger boy with curly hair, "
        "and a taller child on the right. Both little kids and toddlers are watching the teenager."
    )
    sanitized = sanitize_prompt_for_safety(raw_prompt)
    assert "young boy" not in sanitized.lower()
    assert "taller child" not in sanitized.lower()
    assert "little kids" not in sanitized.lower()
    assert "toddler" not in sanitized.lower()
    assert "teenager" not in sanitized.lower()
    assert "Two models" in sanitized
    assert "models" in sanitized

    # 2. Sensitive anatomy to standardized garment zones
    anatomy_prompt = (
        "Replace Upper torso / chest of Taller child with tank top. "
        "Also replace legs / waist with shorts. The model is bare-headed."
    )
    sanitized_anatomy = sanitize_prompt_for_safety(anatomy_prompt)
    assert "upper torso / chest" not in sanitized_anatomy.lower()
    assert "legs / waist" not in sanitized_anatomy.lower()
    assert "bare-headed" not in sanitized_anatomy.lower()
    assert "Upper garment area" in sanitized_anatomy
    assert "lower garment area" in sanitized_anatomy
    assert "unadorned hair" in sanitized_anatomy


def test_sanitize_prompt_for_safety_preserves_fashion_phrases():
    from app.utils.prompt_loader import sanitize_prompt_for_safety

    # Legitimate fashion garments shouldn't have words corrupted
    fashion_prompt = "Model wearing oversized boyfriend jeans and a linen shirt with a chest pocket."
    sanitized = sanitize_prompt_for_safety(fashion_prompt)
    assert "boyfriend jeans" in sanitized
    assert "chest pocket" in sanitized


def test_image_generator_reference_image_interleaving():
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image.data = base64.b64encode(create_dummy_png_bytes()).decode("utf-8")
    mock_interaction.output_text = "generated"
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100, total_token_count=200)
    mock_client.interactions.create.return_value = mock_interaction

    gen = ImageGenerator(client=mock_client)

    img1 = create_dummy_png_bytes(50, 50)
    img2 = create_dummy_png_bytes(60, 60)

    # Multi-image call: should include Reference Image #1: and Reference Image #2:
    gen.generate(
        prompt="Compose scene",
        reference_images=[img1, img2],
        model="gemini-3.1-flash-image",
    )

    call_items = mock_client.interactions.create.call_args.kwargs["input"]
    text_labels = [item["text"] for item in call_items if isinstance(item, dict) and item.get("type") == "text"]
    assert "Reference Image #1:" in text_labels
    assert "Reference Image #2:" in text_labels

    # Single-image call: should NOT insert redundant tag
    mock_client.interactions.create.reset_mock()
    gen.generate(
        prompt="Single image edit",
        reference_images=[img1],
        model="gemini-3.1-flash-image",
    )
    single_call_items = mock_client.interactions.create.call_args.kwargs["input"]
    single_text_labels = [item["text"] for item in single_call_items if isinstance(item, dict) and item.get("type") == "text"]
    assert "Reference Image #1:" not in single_text_labels



