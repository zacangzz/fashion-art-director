import io
import pytest
import os
import json
import hashlib
from PIL import Image
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.generation_service import (
    GenerationService,
    compile_prompt,
    compile_delta_prompt,
    get_modified_categories,
)
from app.db.database import DatabaseManager



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
    assert "Composition: medium-wide shot, shot on (35mm prime lens:1.5)." in compiled
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

    diff = get_modified_categories(
        current_categories=current_categories,
        baseline_categories=baseline_categories,
        current_narrative="Scene A",
        baseline_narrative="Scene A",
    )
    assert diff["has_changes"] is True
    assert diff["categories"].get("wardrobe_hair") is True
    assert diff["categories"].get("environment") is None

    delta_prompt = compile_delta_prompt(
        narrative="Scene A",
        categories=current_categories,
        baseline_narrative="Scene A",
        baseline_categories=baseline_categories,
        locked_categories=["subject_details", "environment"],
    )

    assert "Visual Reference Foundation: Use the reference image as the structural" in delta_prompt
    assert "Requested Modifications: Wardrobe & Hairstyle: wearing navy blue pea coat." in delta_prompt
    assert "Consistent Anchors:" in delta_prompt
    assert "Subject & Character Details" in delta_prompt
    assert "Environment & Setting" in delta_prompt
    assert "Color Profile & Palette" not in delta_prompt
    assert "Mood, Vibe & Era" not in delta_prompt

    # Test with no locked categories
    delta_unlocked = compile_delta_prompt(
        narrative="Scene A",
        categories=current_categories,
        baseline_narrative="Scene A",
        baseline_categories=baseline_categories,
        locked_categories=[],
    )
    assert "Requested Modifications: Wardrobe & Hairstyle: wearing navy blue pea coat." in delta_unlocked
    assert "Consistent Anchors:" not in delta_unlocked



@pytest.mark.asyncio
async def test_generate_4_baselines(tmp_path):
    db_file = str(tmp_path / "test_gen.db")
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    mock_client = MagicMock()
    mock_gen_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_gen_response

    storage_dir = str(tmp_path / "storage")

    with patch("app.services.generation_service.genai.Client", return_value=mock_client):
        service = GenerationService(db_manager=db_mgr, api_key="fake_key", storage_dir=storage_dir)
        state = {
            "narrative": "Editorial living room scene.",
            "categories": {
                "subject_details": [{"label": "model relaxing", "weight": 1.0, "enabled": True}],
                "environment": [{"label": "modernist villa", "weight": 1.0, "enabled": True}],
            },
        }
        baselines = await service.generate_4_baselines(moodboard_id="mb_test_123", state=state)

        assert len(baselines) == 4
        seeds = [b["seed"] for b in baselines]
        assert len(set(seeds)) == 4  # All 4 seeds distinct
        for b in baselines:
            assert b["id"].startswith("gen_")
            assert b["image_url"].startswith("/api/images/")
            # Check DB record
            rec = await db_mgr.get_generation(b["id"])
            assert rec is not None
            assert rec["is_baseline"] in (1, True)
            assert rec["moodboard_id"] == "mb_test_123"
            assert "Editorial living room scene." in rec["compiled_prompt"]


@pytest.mark.asyncio
async def test_fine_tune_generation(tmp_path):
    db_file = str(tmp_path / "test_gen.db")
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    # Pre-create parent baseline image on disk & in DB
    parent_path = os.path.join(gen_dir, "gen_base_01_master.png")
    with open(parent_path, "wb") as f:
        f.write(b"fake_parent_image_bytes")

    await db_mgr.create_generation({
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
    })

    mock_client = MagicMock()
    mock_gen_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_child"
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_gen_response.model_dump.return_value = {"usage_metadata": {"total_token_count": 456}}
    mock_client.models.generate_content.return_value = mock_gen_response

    with patch("app.services.generation_service.genai.Client", return_value=mock_client):
        audit_path = tmp_path / "fine_tune_audit.jsonl"
        service = GenerationService(
            db_manager=db_mgr,
            api_key="fake_key",
            storage_dir=storage_dir,
            audit_path=audit_path,
        )
        state = {
            "narrative": "Fine-tuned goal with altered lighting.",
            "categories": {
                "lighting": [{"label": "dramatic rim light", "weight": 1.0, "enabled": True}],
            },
        }
        res = await service.fine_tune_generation(
            parent_id="gen_base_01",
            state=state,
            seed=918231,
            use_image_reference=True,
        )

        assert res["generation_id"].startswith("gen_")
        assert res["parent_id"] == "gen_base_01"
        assert res["seed"] == 918231
        assert "Fine-tuned goal with altered lighting." in res["compiled_prompt"]
        assert "dramatic rim light" in res["compiled_prompt"]

        # Check DB
        child_rec = await db_mgr.get_generation(res["generation_id"])
        assert child_rec is not None
        assert child_rec["parent_id"] == "gen_base_01"
        assert child_rec["is_baseline"] in (0, False)


@pytest.mark.asyncio
async def test_fine_tune_generation_with_tag_chip_instances(tmp_path):
    from app.schemas.domain import TagChip, TagCategory

    db_file = str(tmp_path / "test_tagchip_gen.db")
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    parent_path = os.path.join(gen_dir, "gen_base_02_master.png")
    with open(parent_path, "wb") as f:
        f.write(b"fake_parent_image_bytes")

    await db_mgr.create_generation({
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
    })

    mock_client = MagicMock()
    mock_gen_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x89PNG_new_bytes"
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_gen_response

    with patch("app.services.generation_service.genai.Client", return_value=mock_client):
        service = GenerationService(db_manager=db_mgr, api_key="fake_key", storage_dir=storage_dir)
        chip = TagChip(id="tag_1", category=TagCategory.SUBJECT_DETAILS, label="copper hair model", enabled=True, locked=False, weight=1.4)
        
        # Pass TagChip Pydantic instances in categories
        res = await service.fine_tune_generation(
            parent_id="gen_base_02",
            narrative="Refined scene with Pydantic chips",
            categories={"subject_details": [chip]},
            seed=123456,
            use_image_reference=False,
        )

        assert res["generation_id"].startswith("gen_")
        assert "copper hair model" in res["compiled_prompt"]
        
        # Verify stored in DB cleanly
        child = await db_mgr.get_generation(res["generation_id"])
        assert child is not None
        assert child["schema_json"]["categories"]["subject_details"][0]["label"] == "copper hair model"


def test_analyze_mask_bytes():
    from app.services.generation_service import analyze_mask_bytes

    # Create a 100x100 black image with a 20x20 white rectangle at (10, 20) -> (29, 39)
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
    assert stats["normalized_bounding_box"]["min_x"] == 0.1
    assert stats["normalized_bounding_box"]["min_y"] == 0.2
    assert stats["centroid"] is not None
    assert stats["sha256"] is not None


@pytest.mark.asyncio
async def test_inpaint_region_audit_and_mask_tracking(tmp_path):
    db_file = str(tmp_path / "test_inpaint_gen.db")
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)
    audit_path = tmp_path / "inpaint_audit.jsonl"

    parent_path = os.path.join(gen_dir, "gen_base_99_master.png")
    with open(parent_path, "wb") as f:
        f.write(b"fake_parent_image_bytes")

    await db_mgr.create_generation({
        "id": "gen_base_99",
        "parent_id": None,
        "moodboard_id": "mb_test_99",
        "is_baseline": True,
        "schema_json": {"narrative": "A studio portrait of a woman in an amber coat."},
        "compiled_prompt": "A studio portrait of a woman in an amber coat.",
        "negative_prompt": "blurry",
        "seed": 4289102,
        "master_image_path": parent_path,
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    })

    # Prepare input image and mask
    src_img = Image.new("RGB", (100, 100), color="blue")
    src_buf = io.BytesIO()
    src_img.save(src_buf, format="PNG")
    src_bytes = src_buf.getvalue()

    mask_img = Image.new("RGB", (100, 100), color="black")
    for y in range(10, 30):
        for x in range(10, 30):
            mask_img.putpixel((x, y), (255, 255, 255))
    mask_buf = io.BytesIO()
    mask_img.save(mask_buf, format="PNG")
    mask_bytes = mask_buf.getvalue()

    # Mock GenAI
    mock_client = MagicMock()
    mock_gen_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x89PNG_inpaint_result"
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_gen_response

    with patch("app.services.generation_service.genai.Client", return_value=mock_client):
        service = GenerationService(
            db_manager=db_mgr,
            api_key="fake_key",
            storage_dir=storage_dir,
            audit_path=audit_path,
        )

        res = await service.inpaint_region(
            parent_id="gen_base_99",
            image_bytes=src_bytes,
            mask_bytes=mask_bytes,
            prompt="change amber coat to emerald velvet blazer",
            seed=555123,
        )

        # 1. Assert result payload
        assert res["generation_id"].startswith("gen_inpaint_")
        assert res["parent_id"] == "gen_base_99"
        assert res["seed"] == 555123
        assert res["image_url"].endswith("_master.png")
        assert res["mask_url"].endswith("_mask.png")
        assert res["mask_stats"]["coverage_percentage"] == 4.0
        assert res["mask_stats"]["bounding_box"]["width"] == 20

        child_id = res["generation_id"]

        # 2. Assert disk files persisted (both master and mask)
        master_disk_path = os.path.join(gen_dir, f"{child_id}_master.png")
        mask_disk_path = os.path.join(gen_dir, f"{child_id}_mask.png")
        assert os.path.exists(master_disk_path)
        assert os.path.exists(mask_disk_path)
        with open(mask_disk_path, "rb") as f:
            assert f.read() == mask_bytes

        # 3. Assert DB record has inpaint_metadata
        child_rec = await db_mgr.get_generation(child_id)
        assert child_rec is not None
        assert child_rec["parent_id"] == "gen_base_99"
        assert child_rec["mask_image_url"] == f"/api/images/{child_id}_mask.png"
        assert child_rec["inpaint_metadata"]["mask_stats"]["coverage_percentage"] == 4.0
        assert child_rec["inpaint_metadata"]["prompt"] == "change amber coat to emerald velvet blazer"

        # 4. Assert structured audit log entries
        assert audit_path.exists()
        lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").strip().split("\n")]
        assert len(lines) == 2

        req_event, resp_event = lines
        assert req_event["event"] == "inpaint_request"
        assert req_event["parent_id"] == "gen_base_99"
        assert req_event["mask"]["coverage_percentage"] == 4.0
        assert req_event["mask"]["width"] == 100
        assert req_event["source_image"]["width"] == 100
        assert "bytes" not in req_event["mask"] or isinstance(req_event["mask"]["bytes"], int)

        assert resp_event["event"] == "inpaint_response"
        assert resp_event["generation_id"] == child_id
        assert resp_event["mask_artifact"]["filename"] == f"{child_id}_mask.png"
        assert resp_event["mask_artifact"]["coverage_percentage"] == 4.0


@pytest.mark.asyncio
async def test_compose_wardrobe_with_subject_grounding(tmp_path):
    db_file = str(tmp_path / "test_wardrobe_gen.db")
    db_mgr = DatabaseManager(db_file)
    await db_mgr.init_db()

    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    wd_dir = os.path.join(storage_dir, "wardrobe", "items")
    os.makedirs(gen_dir, exist_ok=True)
    os.makedirs(wd_dir, exist_ok=True)

    # 1. Create base generation record + master image file
    parent_img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    parent_path = os.path.join(gen_dir, "gen_base_1_master.png")
    parent_img.save(parent_path, format="PNG")

    parent_record = {
        "id": "gen_base_1",
        "parent_id": None,
        "moodboard_id": "mb_123",
        "is_baseline": True,
        "created_at": "2026-08-25T10:00:00Z",
        "schema_json": {"narrative": "A boy and girl sitting together."},
        "compiled_prompt": "A boy and girl sitting together.",
        "negative_prompt": "blurry",
        "seed": 4289102,
        "master_image_path": parent_path,
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    }
    await db_mgr.create_generation(parent_record)

    # 2. Create wardrobe item
    garment_img = Image.new("RGB", (50, 50), color=(200, 50, 50))
    garment_path = os.path.join(wd_dir, "wd_cap_1.png")
    garment_img.save(garment_path, format="PNG")

    await db_mgr.create_wardrobe_item({
        "id": "wd_cap_1",
        "source_image_path": garment_path,
        "label": "Red Baseball Cap",
        "category": "accessories",
        "cropped_image_path": garment_path,
        "bbox_json": [0.1, 0.1, 0.3, 0.3],
        "created_at": "2026-08-25T10:00:00Z",
    })

    # 3. Mock Gemini Image client and WardrobeService
    mock_client = MagicMock()
    mock_gen_response = MagicMock()
    mock_part = MagicMock()
    mock_part.inline_data.data = b"\x89PNG_wardrobe_result"
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_gen_response.candidates = [mock_candidate]
    mock_client.models.generate_content.return_value = mock_gen_response

    mock_wardrobe_service = MagicMock()
    mock_wardrobe_service.ground_wardrobe_pins = AsyncMock(return_value={
        "grounded_pins": [
            {
                "pin_number": 1,
                "target_subject": "The young boy on the left side of the frame",
                "body_location": "head and hair region",
                "spatial_anchor": "upper-left (x: 30%, y: 20%)",
                "current_attire": "bare-headed with dark hair",
            }
        ],
        "unmodified_subjects_guardrail": "The young girl on the right side MUST remain completely untouched.",
    })

    with patch("app.services.generation_service.genai.Client", return_value=mock_client):
        service = GenerationService(
            db_manager=db_mgr,
            api_key="fake_key",
            storage_dir=storage_dir,
            wardrobe_service=mock_wardrobe_service,
        )

        res = await service.compose_wardrobe(
            parent_id="gen_base_1",
            assignments=[
                {
                    "wardrobe_item_id": "wd_cap_1",
                    "pin_number": 1,
                    "drop_position": {"x": 0.3, "y": 0.2},
                    "target_description": "hat",
                }
            ],
            seed=4289102,
        )

        assert res["generation_id"].startswith("gen_wardrobe_")
        assert res["parent_id"] == "gen_base_1"
        assert res["seed"] == 4289102
        assert "The young boy on the left side of the frame" in res["compiled_prompt"]
        assert "The young girl on the right side MUST remain completely untouched" in res["compiled_prompt"]
        assert "MULTI-SUBJECT INVARIANCE GUARDRAIL" in res["compiled_prompt"]
        assert len(res["assignments"]) == 1
        assert res["assignments"][0]["grounded_subject"] == "The young boy on the left side of the frame"


@pytest.mark.asyncio
async def test_register_uploaded_photo(tmp_path):
    db_file = tmp_path / "test_studio.db"
    db_mgr = DatabaseManager(f"sqlite:///{db_file}")
    await db_mgr.init_db()

    storage_dir = str(tmp_path / "storage")
    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    img = Image.new("RGB", (300, 450), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    result = await service.register_uploaded_photo(
        image_bytes=raw_bytes,
        filename="lookbook_photo.png",
        custom_aspect_ratio="2:3",
    )

    assert result["generation_id"].startswith("gen_upload_")
    assert result["aspect_ratio"] == "2:3"
    assert result["resolution"] == {"width": 300, "height": 450}
    assert "/api/images/" in result["image_url"]

    # Verify stored in DB
    rec = await db_mgr.get_generation(result["generation_id"])
    assert rec is not None
    assert rec["is_baseline"] == 1
    assert os.path.exists(rec["master_image_path"])


