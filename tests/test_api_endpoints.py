import io
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db_manager, get_vision_service, get_generation_service, get_storage_service
from fake_firestore import FakeFirestoreClient
from app.db.database import FirestoreManager
from app.services.storage_service import StorageService


@pytest.fixture
def client():
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.generate_signed_url.return_value = "https://storage.googleapis.com/test/img.png"
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    app.dependency_overrides[get_db_manager] = lambda: db_mgr
    app.dependency_overrides[get_storage_service] = lambda: storage_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "Art Director" in response.json()["title"] or "API" in response.json()["title"]


def test_analyze_and_baselines_endpoint(client):
    mock_vision = MagicMock()
    mock_vision.extract_tag_studio_state.return_value = {
        "narrative": "A test editorial scene.",
        "categories": {
            "subject_details": [
                {"id": "t1", "category": "subject_details", "label": "model", "enabled": True, "locked": False, "weight": 1.0, "isCustom": False}
            ]
        },
    }
    mock_gen = MagicMock()
    mock_gen.generate_4_baselines.return_value = [
        {"id": "gen_base_01", "seed": 111, "image_url": "/api/images/gen_base_01.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_02", "seed": 222, "image_url": "/api/images/gen_base_02.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_03", "seed": 333, "image_url": "/api/images/gen_base_03.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_04", "seed": 444, "image_url": "/api/images/gen_base_04.png", "created_at": "2026-08-24T00:00:00Z"},
    ]

    app.dependency_overrides[get_vision_service] = lambda: mock_vision
    app.dependency_overrides[get_generation_service] = lambda: mock_gen

    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    files = [("files", ("test.png", io.BytesIO(file_content), "image/png"))]

    response = client.post("/api/moodboard/analyze-and-baselines", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "moodboard_id" in data
    assert data["narrative"] == "A test editorial scene."
    assert "subject_details" in data["categories"]
    assert len(data["baselines"]) == 4
    assert data["baselines"][0]["seed"] == 111


def test_fine_tune_endpoint(client):
    mock_gen = MagicMock()
    mock_gen.fine_tune_generation.return_value = {
        "generation_id": "gen_child_01",
        "parent_id": "gen_base_01",
        "seed": 999,
        "compiled_prompt": "Refined prompt",
        "negative_prompt": "blurry",
        "image_url": "/api/images/gen_child_01_master.png",
        "created_at": "2026-08-24T00:00:00Z",
    }
    app.dependency_overrides[get_generation_service] = lambda: mock_gen

    payload = {
        "parent_id": "gen_base_01",
        "schema_data": {"narrative": "Refined direction"},
        "seed": 999,
    }
    response = client.post("/api/generate/fine-tune", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["generation_id"] == "gen_child_01"
    assert data["parent_id"] == "gen_base_01"
