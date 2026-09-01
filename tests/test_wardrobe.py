import os
import io
import json
import base64
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import FirestoreManager
from app.services.wardrobe_service import WardrobeService
from app.services.generation_service import GenerationService
from app.services.storage_service import StorageService
from app.services.image_generator import ImageGenerator
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def test_db():
    fake_client = FakeFirestoreClient()
    return FirestoreManager(fake_client)


@pytest.fixture
def dummy_image_bytes():
    img = Image.new("RGB", (200, 200), color=(120, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_wardrobe_db_crud(test_db, dummy_image_bytes, tmp_path):
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
    test_db.create_wardrobe_item(user_id="local_dev_user", item_data=item_data)

    fetched = test_db.get_wardrobe_item("wd_test_01")
    assert fetched is not None
    assert fetched["label"] == "Classic Blue Blazer"
    assert fetched["category"] == "outerwear"
    assert fetched["bbox"] == [0.1, 0.1, 0.6, 0.6]

    items = test_db.list_wardrobe_items(user_id="local_dev_user")
    assert len(items) == 1
    assert items[0]["id"] == "wd_test_01"

    asgn_data = {
        "id": "asgn_01",
        "generation_id": "gen_test_01",
        "wardrobe_item_id": "wd_test_01",
        "pin_number": 1,
        "drop_position": {"x": 0.5, "y": 0.4},
        "target_description": "jacket region",
        "region_bbox": [0.1, 0.2, 0.5, 0.8],
    }
    test_db.create_composition_assignment(user_id="local_dev_user", assignment_data=asgn_data)

    assignments = test_db.list_composition_assignments("gen_test_01")
    assert len(assignments) == 1
    assert assignments[0]["pin_number"] == 1
    assert assignments[0]["wardrobe_label"] == "Classic Blue Blazer"
    assert assignments[0]["drop_position"] == {"x": 0.5, "y": 0.4}

    deleted = test_db.delete_wardrobe_item("wd_test_01")
    assert bool(deleted) is True

    fetched_after = test_db.get_wardrobe_item("wd_test_01")
    assert fetched_after is None
    items_after = test_db.list_wardrobe_items(user_id="local_dev_user")
    assert len(items_after) == 0


def test_segment_and_save_sheet_mocked(test_db, dummy_image_bytes, tmp_path):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "items": [
            {
                "label": "Red Silk Blouse",
                "category": "tops",
                "bounding_box": [10, 10, 80, 80],
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response

    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.download_as_bytes.return_value = dummy_image_bytes
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    service = WardrobeService(
        db_manager=test_db,
        storage_service=storage_service,
        api_key="fake-key",
        storage_dir=storage_dir,
        client=mock_client,
    )

    results = service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="sheet.png",
        user_id="local_dev_user",
    )

    assert len(results) == 1
    assert results[0]["label"] == "Red Silk Blouse"
    assert results[0]["category"] == "tops"
    assert results[0]["bbox"] is not None


def test_upscale_garment_flow(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    crop_path = tmp_path / "crop.png"
    crop_path.write_bytes(dummy_image_bytes)

    test_db.create_wardrobe_item(
        user_id="local_dev_user",
        item_data={
            "id": "item_123",
            "label": "Tweed Jacket",
            "category": "outerwear",
            "cropped_image_path": str(crop_path),
            "created_at": "2026-08-25T10:00:00Z",
        }
    )

    fake_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image = MagicMock(data=dummy_image_bytes)
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100, total_token_count=200)
    fake_client.interactions.create.return_value = mock_interaction

    image_generator = ImageGenerator(client=fake_client)

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.download_as_bytes.return_value = dummy_image_bytes
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    service = WardrobeService(
        db_manager=test_db,
        storage_service=storage_service,
        api_key="fake-key",
        storage_dir=storage_dir,
        client=fake_client,
        image_generator=image_generator,
    )

    res = service.upscale_garment("item_123", user_id="local_dev_user")
    assert res["id"] == "item_123"
    assert res["upscale_status"] == "completed"

    updated = test_db.get_wardrobe_item("item_123")
    assert updated["upscale_status"] == "completed"
    assert updated["upscaled_image_path"] is not None


def test_wardrobe_api_endpoints(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.download_as_bytes.return_value = dummy_image_bytes
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    mock_client = MagicMock()
    mock_seg_response = MagicMock()
    mock_seg_response.text = json.dumps({
        "items": [
            {
                "label": "Emerald Silk Shirt",
                "category": "tops",
                "bounding_box": [10, 10, 80, 80],
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_seg_response

    mock_interaction = MagicMock()
    mock_interaction.output_image = MagicMock(data=dummy_image_bytes)
    mock_interaction.text = json.dumps({
        "items": [
            {
                "label": "Emerald Silk Shirt",
                "category": "tops",
                "bounding_box": [10, 10, 80, 80],
            }
        ]
    })
    mock_interaction.output_text = mock_interaction.text
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100, total_token_count=200)
    mock_client.interactions.create.return_value = mock_interaction

    image_generator = ImageGenerator(client=mock_client)
    wardrobe_service = WardrobeService(
        db_manager=test_db,
        storage_service=storage_service,
        api_key="fake-key",
        storage_dir=storage_dir,
        client=mock_client,
        image_generator=image_generator,
    )

    from app.dependencies import get_db_manager, get_storage_service, get_wardrobe_service
    app.dependency_overrides[get_db_manager] = lambda: test_db
    app.dependency_overrides[get_storage_service] = lambda: storage_service
    app.dependency_overrides[get_wardrobe_service] = lambda: wardrobe_service

    client = TestClient(app)

    try:
        # 1. Test GET /api/wardrobe/items when empty
        res = client.get("/api/wardrobe/items")
        assert res.status_code == 200
        assert res.json() == {"items": []}

        # 2. Test POST /api/wardrobe/upload
        upload_res = client.post(
            "/api/wardrobe/upload",
            files={"file": ("test_sheet.png", dummy_image_bytes, "image/png")},
        )
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["label"] == "Emerald Silk Shirt"
        assert item["category"] == "tops"
        assert item["image_url"].startswith("/api/images/")
        item_id = item["id"]

        # 3. Test GET /api/wardrobe/items with item populated
        list_res = client.get("/api/wardrobe/items")
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == item_id
        assert items[0]["image_url"].startswith("/api/images/")

        # 4. Test POST /api/wardrobe/items/{item_id}/upscale
        upscale_res = client.post(f"/api/wardrobe/items/{item_id}/upscale", json={})
        assert upscale_res.status_code == 200
        upscale_data = upscale_res.json()
        assert upscale_data["id"] == item_id
        assert upscale_data["upscale_status"] == "completed"
        assert upscale_data["is_upscaled"] is True
        assert upscale_data["upscaled_image_url"].startswith("/api/images/")

        # 5. Test DELETE /api/wardrobe/items/{item_id}
        del_res = client.delete(f"/api/wardrobe/items/{item_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # 6. Verify empty list after delete
        list_res_after = client.get("/api/wardrobe/items")
        assert list_res_after.status_code == 200
        assert len(list_res_after.json()["items"]) == 0
    finally:
        app.dependency_overrides.clear()
