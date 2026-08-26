import os
import io
import json
import pytest
import aiosqlite
from unittest.mock import MagicMock, AsyncMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService


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
    assert deleted is True

    # 7. Verify soft delete
    fetched_after = await test_db.get_wardrobe_item("wd_test_01")
    assert fetched_after is None
    items_after = await test_db.list_wardrobe_items()
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


