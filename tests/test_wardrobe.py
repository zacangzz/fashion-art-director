import os
import io
import json
import base64
import pytest
import aiosqlite
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.schemas.domain import CompositionPinAssignment


@pytest.fixture
async def test_db(tmp_path):
    db_file = tmp_path / "test_studio.db"
    db_mgr = DatabaseManager(f"sqlite:///{db_file}")
    await db_mgr.init_db()
    return db_mgr


@pytest.fixture
def dummy_image_bytes():
    img = Image.new("RGB", (200, 200), color=(120, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_wardrobe_db_crud(test_db, dummy_image_bytes, tmp_path):
    # 1. Create wardrobe item
    item_img = tmp_path / "crop1.png"
    item_img.write_bytes(dummy_image_bytes)

    source_img = tmp_path / "source1.png"
    source_img.write_bytes(dummy_image_bytes)

    item_data = {
        "id": "wd_test_01",
        "source_image_path": str(source_img),
        "label": "Classic Blue Blazer",
        "category": "outerwear",
        "cropped_image_path": str(item_img),
        "bbox_json": [0.1, 0.1, 0.6, 0.6],
        "created_at": "2026-08-25T10:00:00Z",
    }
    await test_db.create_wardrobe_item(item_data)

    # 2. Get item
    fetched = await test_db.get_wardrobe_item("wd_test_01")
    assert fetched is not None
    assert fetched["label"] == "Classic Blue Blazer"
    assert fetched["category"] == "outerwear"
    assert fetched["bbox"] == [0.1, 0.1, 0.6, 0.6]

    # 3. List items
    items = await test_db.list_wardrobe_items()
    assert len(items) == 1
    assert items[0]["id"] == "wd_test_01"

    # 4. Create composition assignment
    asgn_data = {
        "id": "asgn_01",
        "generation_id": "gen_test_01",
        "wardrobe_item_id": "wd_test_01",
        "pin_number": 1,
        "drop_position": {"x": 0.5, "y": 0.4},
        "target_description": "jacket region",
        "region_bbox": [0.1, 0.2, 0.5, 0.8],
    }
    await test_db.create_composition_assignment(asgn_data)

    # 5. List assignments
    assignments = await test_db.list_composition_assignments("gen_test_01")
    assert len(assignments) == 1
    assert assignments[0]["pin_number"] == 1
    assert assignments[0]["wardrobe_label"] == "Classic Blue Blazer"
    assert assignments[0]["drop_position"] == {"x": 0.5, "y": 0.4}

    # 6. Delete item
    deleted = await test_db.delete_wardrobe_item("wd_test_01")
    assert bool(deleted) is True

    # 7. Verify soft delete and cascaded assignment deletion
    fetched_after = await test_db.get_wardrobe_item("wd_test_01")
    assert fetched_after is None
    items_after = await test_db.list_wardrobe_items()
    assert len(items_after) == 0
    assignments_after = await test_db.list_composition_assignments("gen_test_01")
    assert len(assignments_after) == 0
    assert len(items_after) == 0


@pytest.mark.asyncio
async def test_wardrobe_service_segmentation(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    os.makedirs(storage_dir, exist_ok=True)

    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    # Mock the Gemini client response
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {
            "label": "Trench Coat",
            "category": "outerwear",
            "bbox": [0.05, 0.1, 0.85, 0.9],
        }
    ])
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    cards = await service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="lookbook.png",
    )

    assert len(cards) == 1
    assert cards[0]["label"] == "Trench Coat"
    assert cards[0]["category"] == "outerwear"
    assert os.path.exists(os.path.join(storage_dir, "wardrobe", "items", f"{cards[0]['id']}.png"))


@pytest.mark.asyncio
async def test_wardrobe_detect_regions(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {
            "label": "Model Upper Body - Blazer",
            "category": "outerwear",
            "bbox": [0.2, 0.3, 0.6, 0.7],
        }
    ])
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    regions = await service.detect_clothing_regions(dummy_image_bytes)
    assert len(regions) == 1
    assert regions[0]["label"] == "Model Upper Body - Blazer"
    assert regions[0]["bbox"] == [0.2, 0.3, 0.6, 0.7]


@pytest.mark.asyncio
async def test_wardrobe_service_gemini_1000_scale_coordinates(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    # Gemini native 0..1000 coordinate output format
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {
            "label": "Pink zip-up hoodie",
            "category": "outerwear",
            "box_2d": [205, 48, 311, 155],
        },
        {
            "label": "Pink sweatpants",
            "category": "bottoms",
            "box_2d": [450, 100, 850, 300],
        }
    ])
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    cards = await service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="outfit_sheet.png",
    )

    assert len(cards) == 2
    # Verify coordinates normalized to 0.0 - 1.0 floats
    assert cards[0]["bbox"][0] == pytest.approx(0.205, rel=1e-2)
    assert cards[0]["bbox"][1] == pytest.approx(0.048, rel=1e-2)
    assert cards[0]["bbox"][2] == pytest.approx(0.311, rel=1e-2)
    assert cards[0]["bbox"][3] == pytest.approx(0.155, rel=1e-2)
    assert os.path.exists(os.path.join(storage_dir, "wardrobe", "items", f"{cards[0]['id']}.png"))


def test_wardrobe_api_endpoints():
    mock_ws = MagicMock()
    mock_ws.list_items = AsyncMock(return_value=[])
    mock_ws.delete_all_items = AsyncMock(return_value=0)
    with patch("app.api.wardrobe.wardrobe_service", mock_ws):
        client = TestClient(app)

        # 1. Test GET /api/wardrobe/items
        resp = client.get("/api/wardrobe/items")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

        # 2. Test DELETE /api/wardrobe/items (bulk delete)
        del_resp = client.delete("/api/wardrobe/items")
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["status"] == "deleted"
        assert "count" in del_data


@pytest.mark.asyncio
async def test_wardrobe_service_subject_grounding(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    # Mock Vision model subject grounding response
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "grounded_pins": [
            {
                "pin_number": 1,
                "target_subject": "The young boy standing on the left side with dark curly hair",
                "body_location": "head and hair region",
                "spatial_anchor": "upper-left quadrant (x: 32%, y: 25%)",
                "current_attire": "currently bare-headed",
            }
        ],
        "unmodified_subjects_guardrail": "The young girl on the right side with blonde hair wearing a pink dress MUST remain completely untouched. Do NOT add any cap or accessories to her.",
    })
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    assignments = [
        {
            "pin_number": 1,
            "item_label": "Baseball Cap",
            "category": "accessories",
            "drop_position": {"x": 0.32, "y": 0.25},
        }
    ]

    result = await service.ground_wardrobe_pins(
        image_bytes=dummy_image_bytes,
        assignments=assignments,
    )

    assert len(result["grounded_pins"]) == 1
    assert result["grounded_pins"][0]["pin_number"] == 1
    assert "young boy standing on the left" in result["grounded_pins"][0]["target_subject"]
    assert "young girl on the right" in result["unmodified_subjects_guardrail"]


@pytest.mark.asyncio
async def test_wardrobe_service_subject_grounding_fallback(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    # Simulate Gemini error / invalid output
    service.client.models.generate_content = MagicMock(side_effect=RuntimeError("API quota exceeded"))

    assignments = [
        {
            "pin_number": 1,
            "item_label": "Baseball Cap",
            "category": "accessories",
            "drop_position": {"x": 0.2, "y": 0.2},
        }
    ]

    result = await service.ground_wardrobe_pins(
        image_bytes=dummy_image_bytes,
        assignments=assignments,
    )

    assert len(result["grounded_pins"]) == 1
    assert result["grounded_pins"][0]["pin_number"] == 1
    assert "left side" in result["grounded_pins"][0]["target_subject"]
    assert "head and hair" in result["grounded_pins"][0]["body_location"]
    assert "Strictly preserve" in result["unmodified_subjects_guardrail"]


@pytest.mark.asyncio
async def test_wardrobe_service_structured_schema_and_decomposition(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "items": [
            {
                "label": "Camel Wool Overcoat",
                "category": "outerwear",
                "box_2d": [100, 150, 600, 450],
            },
            {
                "label": "White Oxford Shirt",
                "category": "tops",
                "box_2d": [200, 200, 400, 400],
            },
            {
                "label": "Charcoal Tailored Trousers",
                "category": "bottoms",
                "box_2d": [550, 200, 900, 400],
            },
            {
                "label": "Black Leather Chelsea Boots",
                "category": "footwear",
                "box_2d": [900, 220, 980, 380],
            },
        ]
    })
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    cards = await service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="decomposed_lookbook.png",
    )

    assert len(cards) == 4
    categories = [c["category"] for c in cards]
    assert "outerwear" in categories
    assert "tops" in categories
    assert "bottoms" in categories
    assert "footwear" in categories


@pytest.mark.asyncio
async def test_wardrobe_service_small_accessory_retention(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    # Accessory with 1.2% dimension (box_2d [100, 200, 112, 212] -> 0.012 height and width)
    # This would have been dropped by the old 2% (0.02) threshold, but is kept with 0.8% (0.008)
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "items": [
            {
                "label": "Gold Aviator Sunglasses",
                "category": "accessories",
                "box_2d": [100, 200, 115, 215],
            }
        ]
    })
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    cards = await service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="accessory_test.png",
    )

    assert len(cards) == 1
    assert cards[0]["label"] == "Gold Aviator Sunglasses"
    assert cards[0]["category"] == "accessories"
    assert cards[0]["bbox"] == [0.1, 0.2, 0.115, 0.215]


@pytest.mark.asyncio
async def test_wardrobe_upscale_background_execution(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    os.makedirs(storage_dir, exist_ok=True)

    mock_gen_service = MagicMock()
    mock_gen_service._call_image_model = AsyncMock(return_value=dummy_image_bytes)

    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
        generation_service=mock_gen_service,
    )

    # 1. Create item record
    item_id = "item_upscale_test"
    item_data = {
        "id": item_id,
        "source_image_path": str(tmp_path / "src.png"),
        "label": "Cashmere Knit Sweater",
        "category": "tops",
        "cropped_image_path": str(tmp_path / "crop.png"),
        "bbox_json": [0.2, 0.2, 0.8, 0.8],
        "upscale_status": "pending",
    }
    await test_db.create_wardrobe_item(item_data)

    # 2. Run background upscale
    await service.upscale_garment_background(
        item_id=item_id,
        crop_bytes=dummy_image_bytes,
        label="Cashmere Knit Sweater",
        category="tops",
    )

    # 3. Verify item is updated to completed with upscaled_image_path
    updated = await test_db.get_wardrobe_item(item_id)
    assert updated is not None
    assert updated["upscale_status"] == "completed"
    assert updated["is_upscaled"] is True
    assert updated["upscaled_image_path"] is not None
    assert os.path.exists(updated["upscaled_image_path"])

    # 4. List items returns upscaled url and status
    cards = await service.list_items()
    assert len(cards) == 1
    assert cards[0]["id"] == item_id
    assert cards[0]["upscale_status"] == "completed"
    assert cards[0]["is_upscaled"] is True
    assert f"/api/wardrobe/items/{item_id}/upscaled-image" in cards[0]["upscaled_image_url"]


@pytest.mark.asyncio
async def test_wardrobe_feature_extraction(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "garment_type": "Vintage Graphic T-Shirt",
        "primary_color": "Faded Black",
        "secondary_colors": ["Sunset Orange", "Cream"],
        "fabric_texture": "Washed heavy jersey cotton",
        "has_graphic_or_print": True,
        "has_text_or_logo": True,
        "exact_text_content": ["RETRO SURF", "1984"],
        "graphic_description": "Distressed sunburst and ocean wave motif",
        "logo_and_print_placement": "Center chest",
        "hardware_and_details": "Ribbed crewneck collar",
    })
    service.client.models.generate_content = MagicMock(return_value=mock_response)

    details = await service.extract_garment_features(
        crop_bytes=dummy_image_bytes,
        label="Graphic T-Shirt",
        category="tops",
    )

    assert details["has_text_or_logo"] is True
    assert details["has_graphic_or_print"] is True
    assert "RETRO SURF" in details["exact_text_content"]
    assert details["logo_and_print_placement"] == "Center chest"


@pytest.mark.asyncio
async def test_wardrobe_composition_with_graphic_locks(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    os.makedirs(storage_dir, exist_ok=True)
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    # 1. Create parent generation
    parent_img = os.path.join(gen_dir, "parent_master.png")
    with open(parent_img, "wb") as f:
        f.write(dummy_image_bytes)

    await test_db.create_generation({
        "id": "gen_parent_01",
        "parent_id": None,
        "moodboard_id": None,
        "is_baseline": True,
        "compiled_prompt": "A model standing in studio",
        "negative_prompt": "blurry",
        "seed": 4289102,
        "master_image_path": parent_img,
        "aspect_ratio": "2:3",
        "resolution_width": 1024,
        "resolution_height": 1536,
    })

    # 2. Create wardrobe item with extracted text/graphic details
    crop_file = tmp_path / "tshirt_crop.png"
    crop_file.write_bytes(dummy_image_bytes)

    await test_db.create_wardrobe_item({
        "id": "wd_tshirt_01",
        "source_image_path": str(parent_img),
        "label": "Vintage Surf T-Shirt",
        "category": "tops",
        "cropped_image_path": str(crop_file),
        "upscaled_image_path": str(crop_file),
        "upscale_status": "completed",
        "extracted_details_json": {
            "has_text_or_logo": True,
            "has_graphic_or_print": True,
            "exact_text_content": ["RETRO SURF", "1984"],
            "graphic_description": "Sunburst wave emblem",
            "logo_and_print_placement": "Center chest",
            "fabric_texture": "heavy cotton",
        },
    })

    # 3. Setup mock GenerationService
    wardrobe_service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )
    gen_service = GenerationService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
        wardrobe_service=wardrobe_service,
    )
    gen_service._call_multi_image_model = AsyncMock(return_value=dummy_image_bytes)

    # Mock grounding
    wardrobe_service.ground_wardrobe_pins = AsyncMock(return_value={
        "grounded_pins": [{
            "pin_number": 1,
            "target_subject": "The model in center frame",
            "body_location": "upper chest and torso",
            "spatial_anchor": "mid-center quadrant",
            "current_attire": "white undershirt",
        }],
        "unmodified_subjects_guardrail": "Preserve other subjects.",
    })

    # 4. Run compose_wardrobe
    result = await gen_service.compose_wardrobe(
        parent_id="gen_parent_01",
        assignments=[{
            "wardrobe_item_id": "wd_tshirt_01",
            "pin_number": 1,
            "drop_position": {"x": 0.5, "y": 0.4},
            "target_description": "chest",
        }],
    )

    assert result["generation_id"] is not None
    assert result["aspect_ratio"] == "2:3"
    assert "RETRO SURF" in result["compiled_prompt"]
    assert "Center chest" in result["compiled_prompt"]
    assert "scrambled text" in result["negative_prompt"]
    assert "altered logos" in result["negative_prompt"]


@pytest.mark.asyncio
async def test_wardrobe_deletion_disk_and_assignment_cleanup(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    crop_path = os.path.join(storage_dir, "wardrobe", "items", "del_test_crop.png")
    upscale_path = os.path.join(storage_dir, "wardrobe", "items", "del_test_upscaled.png")
    os.makedirs(os.path.dirname(crop_path), exist_ok=True)
    with open(crop_path, "wb") as f:
        f.write(dummy_image_bytes)
    with open(upscale_path, "wb") as f:
        f.write(dummy_image_bytes)

    item_id = "wd_del_01"
    await test_db.create_wardrobe_item({
        "id": item_id,
        "source_image_path": crop_path,
        "label": "Silk Scarf",
        "category": "accessories",
        "cropped_image_path": crop_path,
        "upscaled_image_path": upscale_path,
        "upscale_status": "completed",
    })

    # Create associated composition assignment
    await test_db.create_composition_assignment({
        "id": "asgn_del_01",
        "generation_id": "gen_del_parent",
        "wardrobe_item_id": item_id,
        "pin_number": 1,
        "drop_position": {"x": 0.5, "y": 0.2},
    })

    assert os.path.exists(crop_path)
    assert os.path.exists(upscale_path)

    # Perform delete
    deleted = await service.delete_item(item_id)
    assert deleted is True

    # Check files are deleted from disk
    assert not os.path.exists(crop_path)
    assert not os.path.exists(upscale_path)

    # Check assignments are deleted
    asgns = await test_db.list_composition_assignments("gen_del_parent")
    assert len(asgns) == 0


@pytest.mark.asyncio
async def test_wardrobe_upscale_cost_and_token_tracking(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    mock_gen_service = MagicMock()
    mock_gen_service._call_image_model = AsyncMock(return_value=dummy_image_bytes)
    mock_gen_service._last_call_metrics = {
        "cost_usd": 0.045,
        "total_token_count": 1200,
    }

    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
        generation_service=mock_gen_service,
    )

    item_id = "wd_cost_test"
    await test_db.create_wardrobe_item({
        "id": item_id,
        "source_image_path": str(tmp_path / "src.png"),
        "label": "Tweed Overcoat",
        "category": "outerwear",
        "cropped_image_path": str(tmp_path / "crop.png"),
        "cost_usd": 0.005,
        "tokens": 200,
    })

    await service.upscale_garment_background(
        item_id=item_id,
        crop_bytes=dummy_image_bytes,
        label="Tweed Overcoat",
        category="outerwear",
    )

    item = await test_db.get_wardrobe_item(item_id)
    assert item is not None
    assert item["cost_usd"] == pytest.approx(0.050, 0.001)
    assert item["tokens"] == 1400

    cards = await service.list_items()
    assert len(cards) == 1
    assert cards[0]["cost_usd"] == pytest.approx(0.050, 0.001)
    assert cards[0]["tokens"] == 1400


@pytest.mark.asyncio
async def test_wardrobe_service_interactions_api(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    service = WardrobeService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
    )

    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps({
        "garment_type": "Silk Evening Gown",
        "primary_color": "Crimson",
        "secondary_colors": ["Gold"],
        "fabric_texture": "Mulberry Silk",
        "has_graphic_or_print": False,
        "has_text_or_logo": False,
        "exact_text_content": [],
        "graphic_description": None,
        "logo_and_print_placement": None,
        "hardware_and_details": "Gold zipper",
    })
    mock_interaction.usage.prompt_tokens = 150
    mock_interaction.usage.candidates_tokens = 90
    mock_interaction.usage.total_tokens = 240
    service.client.interactions.create = MagicMock(return_value=mock_interaction)

    details = await service.extract_garment_features(
        crop_bytes=dummy_image_bytes,
        label="Evening Gown",
        category="dresses",
    )

    assert details["garment_type"] == "Silk Evening Gown"
    assert details["primary_color"] == "Crimson"
    assert service.client.interactions.create.called


@pytest.mark.asyncio
async def test_compose_wardrobe_with_conversation_and_custom_instruction(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    os.makedirs(os.path.join(storage_dir, "generations"), exist_ok=True)

    parent_img_path = os.path.join(storage_dir, "generations", "parent_gen_01_master.png")
    with open(parent_img_path, "wb") as f:
        f.write(dummy_image_bytes)

    await test_db.create_generation({
        "id": "gen_parent_conv_01",
        "master_image_path": parent_img_path,
        "aspect_ratio": "2:3",
        "seed": 12345,
        "is_baseline": True,
        "accumulated_cost_usd": 0.05,
        "accumulated_tokens": 1000,
    })

    garment_path = os.path.join(storage_dir, "crop_garment.png")
    with open(garment_path, "wb") as f:
        f.write(dummy_image_bytes)

    await test_db.create_wardrobe_item({
        "id": "wd_conv_item_01",
        "source_image_path": garment_path,
        "label": "Leather Bomber Jacket",
        "category": "outerwear",
        "cropped_image_path": garment_path,
    })

    wardrobe_service = WardrobeService(db_manager=test_db, api_key="fake-key", storage_dir=storage_dir)
    wardrobe_service.ground_wardrobe_pins = AsyncMock(return_value={
        "grounded_pins": [{
            "pin_number": 1,
            "target_subject": "The model on left",
            "body_location": "torso",
            "spatial_anchor": "left center",
        }],
        "unmodified_subjects_guardrail": "Preserve right model untouched.",
    })

    gen_service = GenerationService(
        db_manager=test_db,
        api_key="fake-key",
        storage_dir=storage_dir,
        wardrobe_service=wardrobe_service,
    )
    gen_service._call_multi_image_model = AsyncMock(return_value=dummy_image_bytes)

    # Test passing Pydantic CompositionPinAssignment model objects
    pydantic_asgn = CompositionPinAssignment(
        wardrobe_item_id="wd_conv_item_01",
        pin_number=1,
        drop_position={"x": 0.3, "y": 0.4},
        target_description="Leather Jacket",
    )

    result = await gen_service.compose_wardrobe(
        parent_id="gen_parent_conv_01",
        assignments=[pydantic_asgn],
        conversation_id="conv_custom_123",
        custom_instruction="Make the jacket look distressed with vintage patina.",
        imagen_model="gemini-3.1-flash-image",
        vision_model="gemini-3.7-flash",
    )

    assert result["generation_id"].startswith("gen_wardrobe_")
    assert result["conversation_id"] == "conv_custom_123"
    assert "ADDITIONAL USER INSTRUCTION:\nMake the jacket look distressed with vintage patina." in result["compiled_prompt"]
    assert "Leather Bomber Jacket" in result["compiled_prompt"]
    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["grounded_subject"] == "The model on left"

    # Verify DB record stored conversation_id and schema_json correctly
    record = await test_db.get_generation(result["generation_id"])
    assert record is not None
    assert record["conversation_id"] == "conv_custom_123"
    assert record["schema_json"]["custom_instruction"] == "Make the jacket look distressed with vintage patina."
    assert record["schema_json"]["wardrobe_composition"] is True

    # Verify vision_model was passed to ground_wardrobe_pins
    wardrobe_service.ground_wardrobe_pins.assert_called_once()
    _, kwargs = wardrobe_service.ground_wardrobe_pins.call_args
    assert kwargs.get("vision_model") == "gemini-3.7-flash"


@pytest.mark.asyncio
async def test_wardrobe_compose_api_endpoint(test_db):
    mock_result = {
        "generation_id": "gen_wardrobe_mock99",
        "parent_id": "gen_parent_test",
        "conversation_id": "conv_api_test",
        "seed": 4289102,
        "compiled_prompt": "Compose Leather Jacket",
        "negative_prompt": "blurry",
        "image_url": "/api/images/gen_wardrobe_mock99_master.png",
        "created_at": "2026-08-30T12:00:00Z",
        "aspect_ratio": "2:3",
        "resolution": {"width": 1024, "height": 1536},
        "assignments": [
            {
                "wardrobe_item_id": "wd_item_01",
                "pin_number": 1,
                "drop_position": {"x": 0.5, "y": 0.5},
                "target_description": "jacket",
                "grounded_subject": "Subject A",
            }
        ],
        "cost_usd": 0.04,
        "tokens": 1200,
        "accumulated_cost_usd": 0.08,
        "accumulated_tokens": 2200,
    }

    with patch("app.api.wardrobe.generation_service.compose_wardrobe", new_callable=AsyncMock) as mock_compose:
        mock_compose.return_value = mock_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "parent_id": "gen_parent_test",
                "assignments": [
                    {
                        "wardrobe_item_id": "wd_item_01",
                        "pin_number": 1,
                        "drop_position": {"x": 0.5, "y": 0.5},
                        "target_description": "jacket",
                    }
                ],
                "seed": 4289102,
                "seed_mode": "locked",
                "aspect_ratio": "2:3",
                "conversation_id": "conv_api_test",
                "custom_instruction": "Add warm studio lighting",
                "imagen_model": "gemini-3.1-flash-image",
                "vision_model": "gemini-3.7-flash",
            }
            response = await client.post("/api/wardrobe/compose", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["generation_id"] == "gen_wardrobe_mock99"
            assert data["conversation_id"] == "conv_api_test"
            assert data["compiled_prompt"] == "Compose Leather Jacket"
            assert len(data["assignments"]) == 1
            assert data["assignments"][0]["grounded_subject"] == "Subject A"

            # Check that compose_wardrobe was called with expected kwargs
            mock_compose.assert_called_once()
            _, call_kwargs = mock_compose.call_args
            assert call_kwargs["parent_id"] == "gen_parent_test"
            assert call_kwargs["conversation_id"] == "conv_api_test"
            assert call_kwargs["custom_instruction"] == "Add warm studio lighting"
            assert call_kwargs["imagen_model"] == "gemini-3.1-flash-image"
            assert call_kwargs["vision_model"] == "gemini-3.7-flash"


@pytest.mark.asyncio
async def test_wardrobe_composition_white_balance_lock_and_multi_turn_lineage(test_db, dummy_image_bytes, tmp_path):
    """
    Verifies that wardrobe composition prompts include the Color Constancy & White Balance Lock,
    and progressive multi-turn generations include the root-anchored chromatic continuity section.
    """
    from app.utils.prompt_loader import WARDROBE_COMPOSITION_SYSTEM_PROMPT
    from app.utils.image_utils import optimize_reference_image

    # 1. Verify prompt contains White Balance Lock
    assert "Color Constancy & Calibrated White Balance Lock" in WARDROBE_COMPOSITION_SYSTEM_PROMPT
    assert "Kelvin color temperature" in WARDROBE_COMPOSITION_SYSTEM_PROMPT

    # 2. Verify reference image optimization
    opt_bytes, mime = optimize_reference_image(dummy_image_bytes, max_dimension=2048, target_format="PNG")
    assert mime == "image/png"
    assert len(opt_bytes) > 0

    # 3. Create Root Baseline Generation in DB
    base_file = tmp_path / "base_img.png"
    base_file.write_bytes(dummy_image_bytes)
    await test_db.create_generation({
        "id": "gen_root_base_001",
        "parent_id": None,
        "moodboard_id": None,
        "is_baseline": True,
        "created_at": "2026-08-30T10:00:00Z",
        "schema_json": {},
        "compiled_prompt": "Initial baseline scene",
        "negative_prompt": "blurry",
        "seed": 12345,
        "master_image_path": str(base_file),
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
        "model_name": "gemini-3.1-flash-image",
        "cost_usd": 0.04,
        "tokens": 1000,
        "accumulated_cost_usd": 0.04,
        "accumulated_tokens": 1000,
    })

    # Create Turn 1 Generation in DB
    turn1_file = tmp_path / "turn1_img.png"
    turn1_file.write_bytes(dummy_image_bytes)
    await test_db.create_generation({
        "id": "gen_turn1_wardrobe",
        "parent_id": "gen_root_base_001",
        "moodboard_id": None,
        "is_baseline": False,
        "created_at": "2026-08-30T10:05:00Z",
        "schema_json": {"wardrobe_composition": True},
        "compiled_prompt": "Turn 1 shirt swap",
        "negative_prompt": "blurry",
        "seed": 12345,
        "master_image_path": str(turn1_file),
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
        "model_name": "gemini-3.1-flash-image",
        "cost_usd": 0.04,
        "tokens": 1000,
        "accumulated_cost_usd": 0.08,
        "accumulated_tokens": 2000,
    })

    # Create garment item in DB
    item_file = tmp_path / "trousers.png"
    item_file.write_bytes(dummy_image_bytes)
    await test_db.create_wardrobe_item({
        "id": "wd_trouser_item",
        "source_image_path": str(item_file),
        "label": "Linen Trousers",
        "category": "bottoms",
        "cropped_image_path": str(item_file),
        "created_at": "2026-08-30T10:00:00Z",
    })

    # Setup GenerationService with mocks
    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image.data = base64.b64encode(dummy_image_bytes).decode("utf-8")
    mock_interaction.usage.total_tokens = 500
    mock_interaction.usage.prompt_tokens = 250
    mock_interaction.usage.candidates_tokens = 250
    mock_client.interactions.create.return_value = mock_interaction

    wardrobe_service = WardrobeService(db_manager=test_db, api_key="dummy", storage_dir=str(tmp_path), client=mock_client)
    wardrobe_service.ground_wardrobe_pins = AsyncMock(return_value={
        "grounded_pins": [{"pin_number": 1, "target_subject": "Subject A", "body_location": "lower body", "spatial_anchor": "lower-center"}],
        "unmodified_subjects_guardrail": "Preserve all other subjects.",
    })

    gen_service = GenerationService(
        db_manager=test_db,
        api_key="dummy",
        storage_dir=str(tmp_path),
        client=mock_client,
        wardrobe_service=wardrobe_service,
    )

    # Perform Turn 2 Wardrobe Composition (Parent = Turn 1)
    asgn = {
        "wardrobe_item_id": "wd_trouser_item",
        "pin_number": 1,
        "drop_position": {"x": 0.5, "y": 0.7},
        "item_label": "Linen Trousers",
    }

    result = await gen_service.compose_wardrobe(
        parent_id="gen_turn1_wardrobe",
        assignments=[asgn],
    )

    # Verify that Turn 2's prompt includes progressive turn anchor and white balance lock
    compiled_p = result["compiled_prompt"]
    assert "PROGRESSIVE STYLING TURN #2 CHROMATIC ANCHOR" in compiled_p
    assert "Color Constancy & Calibrated White Balance Lock" in compiled_p
    assert "Maintain absolute color temperature and neutral white balance" in compiled_p





