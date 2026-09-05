import os
import io
import json
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import FirestoreManager
from app.services.prop_service import PropService
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
    img = Image.new("RGB", (200, 200), color=(140, 180, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_prop_db_crud(test_db, dummy_image_bytes, tmp_path):
    item_img = tmp_path / "prop_crop1.png"
    item_img.write_bytes(dummy_image_bytes)

    source_img = tmp_path / "prop_source1.png"
    source_img.write_bytes(dummy_image_bytes)

    item_data = {
        "id": "prop_test_01",
        "source_image_path": str(source_img),
        "label": "Nordic Ceramic Vase",
        "category": "decor",
        "cropped_image_path": str(item_img),
        "bbox_json": [0.1, 0.1, 0.6, 0.6],
        "created_at": "2026-09-05T10:00:00Z",
        "scale_preset": "medium",
    }
    test_db.create_prop_item(user_id="local_dev_user", item_data=item_data)

    fetched = test_db.get_prop_item("prop_test_01")
    assert fetched is not None
    assert fetched["label"] == "Nordic Ceramic Vase"
    assert fetched["category"] == "decor"
    assert fetched["bbox"] == [0.1, 0.1, 0.6, 0.6]

    items = test_db.list_prop_items(user_id="local_dev_user")
    assert len(items) == 1
    assert items[0]["id"] == "prop_test_01"

    asgn_data = {
        "id": "prop_asgn_01",
        "generation_id": "gen_test_01",
        "prop_item_id": "prop_test_01",
        "pin_number": 1,
        "bounding_box": {"ymin": 0.4, "xmin": 0.4, "ymax": 0.6, "xmax": 0.6},
        "scale_preset": "medium",
        "scale_factor": 0.3,
        "notes": "place on marble coffee table",
    }
    test_db.create_prop_assignment(user_id="local_dev_user", assignment_data=asgn_data)

    assignments = test_db.list_prop_assignments("gen_test_01")
    assert len(assignments) == 1
    assert assignments[0]["pin_number"] == 1
    assert assignments[0]["prop_label"] == "Nordic Ceramic Vase"
    assert assignments[0]["bounding_box"]["ymin"] == 0.4

    # Test cascade soft-delete
    deleted = test_db.delete_prop_item("prop_test_01")
    assert bool(deleted) is True

    fetched_after = test_db.get_prop_item("prop_test_01")
    assert fetched_after is None
    items_after = test_db.list_prop_items(user_id="local_dev_user")
    assert len(items_after) == 0

    assignments_after = test_db.list_prop_assignments("gen_test_01")
    assert len(assignments_after) == 0


def test_prop_service_segmentation_mocked(test_db, dummy_image_bytes, tmp_path):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "items": [
            {
                "label": "Vintage Brass Table Lamp",
                "category": "lighting",
                "bounding_box": [10, 10, 80, 80],
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.upload_bytes.side_effect = lambda *args, **kw: f"mock/{kw.get('filename', 'test.png')}"
    mock_storage.get_signed_download_url.side_effect = lambda p: f"http://mock-storage/{p}"

    prop_service = PropService(
        db_manager=test_db,
        storage_service=mock_storage,
        api_key="dummy_key",
        vision_model="gemini-3.7-flash",
        imagen_model="gemini-3.1-flash-image",
        client=mock_client,
    )

    items = prop_service.segment_and_save_sheet(
        image_bytes=dummy_image_bytes,
        original_filename="prop_sheet.png",
        vision_model="gemini-3.7-flash",
        user_id="local_dev_user",
    )

    assert len(items) == 1
    assert items[0]["label"] == "Vintage Brass Table Lamp"
    assert items[0]["category"] == "lighting"
    assert items[0]["is_upscaled"] is False

    saved_items = test_db.list_prop_items(user_id="local_dev_user")
    assert len(saved_items) == 1
    assert saved_items[0]["label"] == "Vintage Brass Table Lamp"


def test_prop_service_single_upload_mocked(test_db, dummy_image_bytes):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "material_finish": "Brushed anodized aluminum, matte rubber accents",
        "color_palette": ["#111111", "#a1a1aa"],
        "placement_hint": "Desk, tabletop, or handheld",
        "scale_preset": "small",
        "details": "Minimalist portable smart speaker with metallic mesh grille",
    })
    mock_client.models.generate_content.return_value = mock_response

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.upload_bytes.side_effect = lambda *args, **kw: f"mock/{kw.get('filename', 'test.png')}"
    mock_storage.get_signed_download_url.side_effect = lambda p: f"http://mock-storage/{p}"

    prop_service = PropService(
        db_manager=test_db,
        storage_service=mock_storage,
        api_key="dummy_key",
        vision_model="gemini-3.7-flash",
        imagen_model="gemini-3.1-flash-image",
        client=mock_client,
    )

    item = prop_service.upload_single_prop(
        image_bytes=dummy_image_bytes,
        filename="smart_speaker.png",
        category="tech",
        vision_model="gemini-3.7-flash",
        user_id="local_dev_user",
    )

    assert item["label"] == "Smart Speaker"
    assert item["category"] == "tech"
    assert item["extracted_details"]["scale_preset"] == "small"
    assert len(item["extracted_details"]["color_palette"]) == 2


def test_props_api_endpoints(test_db, dummy_image_bytes):
    from app.dependencies import get_db_manager, get_prop_service, get_storage_service
    from app.auth.firebase_auth import get_current_user

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.upload_bytes.side_effect = lambda *args, **kw: f"mock/{kw.get('filename', 'test.png')}"
    mock_storage.get_signed_download_url.side_effect = lambda p: f"http://mock-storage/{p}"

    mock_prop_service = MagicMock(spec=PropService)
    mock_prop_service.segment_and_save_sheet.return_value = [
        {
            "id": "prop_api_01",
            "label": "Armchair",
            "category": "furniture",
            "image_url": "http://mock/armchair.png",
            "is_upscaled": False,
            "upscale_status": "pending",
        }
    ]
    mock_prop_service.upload_single_prop.return_value = {
        "id": "prop_api_02",
        "label": "Coffee Mug",
        "category": "tableware",
        "image_url": "http://mock/mug.png",
        "is_upscaled": False,
        "upscale_status": "pending",
    }
    mock_prop_service.upscale_prop.return_value = {
        "id": "prop_api_01",
        "label": "Armchair",
        "category": "furniture",
        "upscale_status": "completed",
        "is_upscaled": True,
        "upscaled_image_url": "http://mock/armchair_hd.png",
        "cost_sgd": 0.05,
        "cost_usd": 0.038,
    }

    app.dependency_overrides[get_db_manager] = lambda: test_db
    app.dependency_overrides[get_prop_service] = lambda: mock_prop_service
    app.dependency_overrides[get_storage_service] = lambda: mock_storage
    app.dependency_overrides[get_current_user] = lambda: {"uid": "local_dev_user", "email": "dev@studio.local"}

    client = TestClient(app)

    try:
        # 1. Upload sheet
        files = {"file": ("sheet.png", dummy_image_bytes, "image/png")}
        res = client.post("/api/props/upload-sheet", files=files)
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["label"] == "Armchair"

        # 2. Upload single
        files_single = {"file": ("mug.png", dummy_image_bytes, "image/png")}
        res_single = client.post("/api/props/upload-single", files=files_single, data={"category": "tableware"})
        assert res_single.status_code == 200
        data_single = res_single.json()
        assert len(data_single["items"]) == 1
        assert data_single["items"][0]["category"] == "tableware"

        # 3. List items (from db)
        test_db.create_prop_item(
            user_id="local_dev_user",
            item_data={
                "id": "prop_api_01",
                "label": "Armchair",
                "category": "furniture",
                "cropped_image_path": "mock/armchair.png",
            },
        )
        res_list = client.get("/api/props/items")
        assert res_list.status_code == 200
        assert len(res_list.json()["items"]) == 1

        # 4. Upscale item
        res_upscale = client.post("/api/props/items/prop_api_01/upscale")
        assert res_upscale.status_code == 200
        assert res_upscale.json()["upscale_status"] == "completed"

        # 5. Delete single item
        res_del = client.delete("/api/props/items/prop_api_01")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "deleted"

        # 6. Delete all items
        res_del_all = client.delete("/api/props/items")
        assert res_del_all.status_code == 200
        assert res_del_all.json()["status"] == "deleted"

    finally:
        app.dependency_overrides.clear()


def test_prop_composition_service(test_db, dummy_image_bytes, tmp_path):
    storage_dir = str(tmp_path / "storage")
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.download_as_bytes.return_value = dummy_image_bytes
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local", storage_dir=storage_dir)

    # Upload image bytes so local StorageService finds them
    root_path = storage_service.upload_bytes(
        user_id="local_dev_user",
        category="generations",
        filename="root.png",
        data=dummy_image_bytes,
    )
    prop_crop_path = storage_service.upload_bytes(
        user_id="local_dev_user",
        category="props/items",
        filename="vase_crop.png",
        data=dummy_image_bytes,
    )

    # Seed root baseline generation
    root_gen = {
        "id": "gen_prop_root",
        "user_id": "local_dev_user",
        "master_image_path": root_path,
        "seed": 100001,
        "aspect_ratio": "1:1",
        "is_baseline": True,
        "parent_id": None,
    }
    test_db.create_generation(user_id="local_dev_user", gen_data=root_gen)

    # Seed prop item
    prop_item = {
        "id": "prop_vase_01",
        "label": "Nordic Ceramic Vase",
        "category": "decor",
        "cropped_image_path": prop_crop_path,
        "scale_preset": "medium",
    }
    test_db.create_prop_item(user_id="local_dev_user", item_data=prop_item)

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image = MagicMock(data=dummy_image_bytes)
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=150, candidates_token_count=200, total_token_count=350)
    mock_client.interactions.create.return_value = mock_interaction

    image_generator = ImageGenerator(
        client=mock_client,
        default_model="gemini-3.1-flash-image",
    )

    prop_service = PropService(
        db_manager=test_db,
        storage_service=storage_service,
        api_key="dummy_key",
        vision_model="gemini-3.7-flash",
        imagen_model="gemini-3.1-flash-image",
        client=mock_client,
        image_generator=image_generator,
    )
    prop_service.ground_prop_boxes = MagicMock(return_value={
        "grounded_props": [
            {
                "pin_number": 1,
                "label": "Nordic Ceramic Vase",
                "category": "decor",
                "host_surface": "wooden coffee table",
                "scale_context": "medium tabletop scale (approx 25-30cm height)",
                "contact_shadows": "soft ambient occlusion shadow on tabletop surface",
                "depth_placement": "midground, resting stably on table plane",
            }
        ],
        "scene_guardrails": "Strictly preserve model identity, clothing, and background architecture.",
    })

    gen_service = GenerationService(
        db_manager=test_db,
        storage_service=storage_service,
        image_generator=image_generator,
        prop_service=prop_service,
    )

    asgn = {
        "prop_item_id": "prop_vase_01",
        "pin_number": 1,
        "bounding_box": {"ymin": 0.4, "xmin": 0.4, "ymax": 0.6, "xmax": 0.6},
        "scale_preset": "medium",
        "scale_factor": 0.3,
        "item_label": "Nordic Ceramic Vase",
        "notes": "rest on wooden table with soft contact shadows",
    }

    res = gen_service.compose_props(
        parent_id="gen_prop_root",
        assignments=[asgn],
        user_id="local_dev_user",
    )

    assert res["generation_id"] is not None
    assert "Nordic Ceramic Vase" in res["compiled_prompt"]
    assert "wooden coffee table" in res["compiled_prompt"]
    assert "Strictly preserve model identity" in res["compiled_prompt"]

    # Verify assignments recorded in DB
    assignments_in_db = test_db.list_prop_assignments(res["generation_id"])
    assert len(assignments_in_db) == 1
    assert assignments_in_db[0]["pin_number"] == 1

