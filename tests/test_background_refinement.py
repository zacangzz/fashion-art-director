import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_db_manager, get_storage_service, get_generation_service
from fake_firestore import FakeFirestoreClient
from app.db.database import FirestoreManager
from app.services.storage_service import StorageService
from app.services.prompt_compiler import PromptCompiler
from app.services.generation_service import GenerationService


@pytest.fixture
def mock_db_and_storage(tmp_path):
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    storage_service = StorageService(environment="local", storage_dir=str(tmp_path / "storage"))
    return db_mgr, storage_service


@pytest.fixture
def client(mock_db_and_storage):
    db_mgr, storage_service = mock_db_and_storage
    app.dependency_overrides[get_db_manager] = lambda: db_mgr
    app.dependency_overrides[get_storage_service] = lambda: storage_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_sample_png_bytes(width=100, height=100, color=(200, 100, 50)):
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# 1. Database Layer Unit Tests
# --------------------------------------------------------------------------

def test_firestore_background_references_crud(mock_db_and_storage):
    db_mgr, _ = mock_db_and_storage
    user_id = "test_user_bg_1"

    # Create background reference
    bg_data = {
        "id": "bg_test_001",
        "original_filename": "modern_arch.png",
        "image_path": f"{user_id}/backgrounds/bg_test_001.png",
        "thumbnail_path": f"{user_id}/backgrounds/bg_test_001_thumb.png",
        "aspect_ratio": "16:9",
        "tags": ["architectural", "exterior"],
    }
    created = db_mgr.create_background_reference(user_id=user_id, bg_data=bg_data)
    assert created["id"] == "bg_test_001"
    assert created["image_url"] == f"/api/images/{user_id}/backgrounds/bg_test_001.png"
    assert created["thumbnail_url"] == f"/api/images/{user_id}/backgrounds/bg_test_001_thumb.png"

    # Get single background reference
    fetched = db_mgr.get_background_reference("bg_test_001")
    assert fetched is not None
    assert fetched["original_filename"] == "modern_arch.png"
    assert fetched["aspect_ratio"] == "16:9"

    # List background references
    items = db_mgr.list_background_references(user_id=user_id)
    assert len(items) == 1
    assert items[0]["id"] == "bg_test_001"

    # Soft delete background reference
    deleted = db_mgr.delete_background_reference(user_id=user_id, bg_id="bg_test_001")
    assert deleted is True

    # Verify soft-deleted item is no longer retrieved
    assert db_mgr.get_background_reference("bg_test_001") is None
    assert len(db_mgr.list_background_references(user_id=user_id)) == 0


# --------------------------------------------------------------------------
# 2. Prompt Compiler Unit Tests
# --------------------------------------------------------------------------

def test_prompt_compiler_background_harmonization():
    prompt = "Place model standing next to concrete wall"
    
    # Auto-align & cinematic bokeh
    compiled_auto = PromptCompiler.format_background_refinement_prompt(
        prompt=prompt,
        perspective_mode="auto_align",
        depth_of_field="cinematic_bokeh",
        lighting_mode="harmonize_ambient",
    )
    assert "MASTER PHOTOGRAPHIC SCENE SYNTHESIS" in compiled_auto
    assert "horizon" in compiled_auto.lower() or "perspective" in compiled_auto.lower()
    assert "bokeh" in compiled_auto.lower() or "f/1.4" in compiled_auto
    assert "ambient light spill" in compiled_auto.lower()
    assert prompt in compiled_auto

    # Preserve BG angle & crisp architectural
    compiled_preserve = PromptCompiler.format_background_refinement_prompt(
        prompt=prompt,
        perspective_mode="preserve_bg",
        depth_of_field="crisp_architectural",
        lighting_mode="match_white_balance",
    )
    assert "perspective geometry" in compiled_preserve.lower()
    assert "architectural clarity" in compiled_preserve.lower()

    assert "neutral white balance" in compiled_preserve.lower()


# --------------------------------------------------------------------------
# 3. API Route Tests
# --------------------------------------------------------------------------

def test_upload_and_list_background_api(client):
    png_bytes = create_sample_png_bytes(320, 240)
    files = {"file": ("gallery_setting.png", io.BytesIO(png_bytes), "image/png")}

    # Upload
    upload_res = client.post("/api/backgrounds/upload", files=files)
    assert upload_res.status_code == 200
    data = upload_res.json()
    assert data["id"].startswith("bg_")
    assert data["original_filename"] == "gallery_setting.png"
    assert "/api/images/" in data["image_url"]
    assert "/api/images/" in data["thumbnail_url"]

    bg_id = data["id"]

    # List
    list_res = client.get("/api/backgrounds")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(b["id"] == bg_id for b in list_data["items"])

    # Delete
    del_res = client.delete(f"/api/backgrounds/{bg_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify deleted
    list_res_after = client.get("/api/backgrounds")
    assert not any(b["id"] == bg_id for b in list_res_after.json()["items"])


def test_refine_with_background_reference_api(client, mock_db_and_storage):
    db_mgr, storage_service = mock_db_and_storage

    # Create parent generation
    parent_gen_data = {
        "id": "gen_parent_test",
        "user_id": "test_user",
        "master_image_path": "test_user/generations/parent.png",
        "seed": 555555,
        "aspect_ratio": "2:3",
        "compiled_prompt": "Initial baseline model portrait",
    }
    # Save dummy image for parent
    storage_service.upload_bytes("test_user", "generations", "parent.png", create_sample_png_bytes())
    db_mgr.create_generation(user_id="test_user", gen_data=parent_gen_data)

    # Create background reference
    bg_storage_path = storage_service.upload_bytes("test_user", "backgrounds", "bg_sample.png", create_sample_png_bytes())
    bg_record = db_mgr.create_background_reference(
        user_id="test_user",
        bg_data={
            "id": "bg_ref_123",
            "original_filename": "courtyard.png",
            "image_path": bg_storage_path,
            "aspect_ratio": "16:9",
        },
    )

    mock_gen_service = MagicMock()
    mock_gen_service.refine_generation.return_value = {
        "generation_id": "gen_refine_bg_01",
        "parent_id": "gen_parent_test",
        "conversation_id": "conv_test",
        "seed": 555555,
        "prompt": "Set background to modern courtyard",
        "compiled_prompt": "MULTIMODAL BACKGROUND REPLACEMENT ...",
        "negative_prompt": "blurry",
        "image_url": "/api/images/test_user/generations/gen_refine_bg_01_master.png",
        "created_at": "2026-09-01T12:00:00Z",
        "aspect_ratio": "2:3",
        "resolution": {"width": 1440, "height": 2160},
        "background_reference_id": "bg_ref_123",
        "background_harmonization_meta": {
            "perspective_mode": "auto_align",
            "depth_of_field": "cinematic_bokeh",
            "lighting_mode": "harmonize_ambient",
        },
        "cost_usd": 0.04,
        "tokens": 1200,
        "accumulated_cost_usd": 0.08,
        "accumulated_tokens": 2400,
    }

    app.dependency_overrides[get_generation_service] = lambda: mock_gen_service

    payload = {
        "parent_id": "gen_parent_test",
        "prompt": "Set background to modern courtyard",
        "seed": 555555,
        "seed_mode": "locked",
        "aspect_ratio": "2:3",
        "background_reference_id": "bg_ref_123",
        "perspective_mode": "auto_align",
        "depth_of_field": "cinematic_bokeh",
        "lighting_mode": "harmonize_ambient",
    }

    response = client.post("/api/refine", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["generation_id"] == "gen_refine_bg_01"
    assert res_data["background_reference_id"] == "bg_ref_123"
    assert res_data["background_harmonization_meta"]["perspective_mode"] == "auto_align"
    mock_gen_service.refine_generation.assert_called_once()
