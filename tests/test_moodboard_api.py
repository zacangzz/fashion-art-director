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

    mock_vision = MagicMock()
    mock_gen = MagicMock()

    app.dependency_overrides[get_db_manager] = lambda: db_mgr
    app.dependency_overrides[get_storage_service] = lambda: storage_service
    app.dependency_overrides[get_vision_service] = lambda: mock_vision
    app.dependency_overrides[get_generation_service] = lambda: mock_gen
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_analyze_moodboard_no_files(client):
    response = client.post("/api/moodboard/analyze")
    assert response.status_code in (422, 400)


def test_analyze_moodboard_too_many_files(client):
    files = [("files", (f"img_{i}.png", b"fake_bytes", "image/png")) for i in range(6)]
    response = client.post("/api/moodboard/analyze", files=files)
    assert response.status_code == 400
    assert "Between 1 and 5 files" in response.json()["detail"]


def test_analyze_moodboard_invalid_mime_type(client):
    files = [("files", ("doc.txt", b"hello world", "text/plain"))]
    response = client.post("/api/moodboard/analyze", files=files)
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_analyze_moodboard_pdf_success(client):
    files = [("files", ("moodboard.pdf", b"%PDF-1.5 fake pdf content", "application/pdf"))]
    mock_state = {
        "master_prompt": "Editorial PDF scene",
        "narrative": "A high-fashion scene from PDF",
        "categories": {
            "mood_era": [{"id": "chip_1", "category": "mood_era", "label": "editorial", "weight": 1.0, "enabled": True, "locked": False}]
        },
    }

    mock_vision = MagicMock()
    mock_vision.extract_tag_studio_state.return_value = mock_state
    app.dependency_overrides[get_vision_service] = lambda: mock_vision

    response = client.post("/api/moodboard/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["moodboard_id"].startswith("mb_")
    assert data["master_prompt"] == "Editorial PDF scene"
    assert len(data["extracted_chips"]) == 1
    assert data["extracted_chips"][0]["label"] == "editorial"


def test_analyze_moodboard_success(client):
    files = [("files", ("sample.jpg", b"\xff\xd8fakejpeg", "image/jpeg"))]
    mock_state = {
        "master_prompt": "Cinematic golden hour scene",
        "narrative": "A cinematic high fashion shot",
        "categories": {
            "mood_era": [{"id": "chip_1", "category": "mood_era", "label": "cinematic", "weight": 1.0, "enabled": True, "locked": False}],
            "lighting": [{"id": "chip_2", "category": "lighting", "label": "golden hour", "weight": 1.0, "enabled": True, "locked": False}],
        },
    }

    mock_vision = MagicMock()
    mock_vision.extract_tag_studio_state.return_value = mock_state
    app.dependency_overrides[get_vision_service] = lambda: mock_vision

    response = client.post("/api/moodboard/analyze", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["narrative"] == "A cinematic high fashion shot"
    assert "mood_era" in data["categories"]
    assert "lighting" in data["categories"]


def test_generate_baselines_api(client):
    mock_gen_service = MagicMock()
    mock_gen_service.generate_4_baselines.return_value = [
        {
            "id": f"gen_{i}",
            "seed": 1000 + i,
            "image_url": f"/api/images/gen_{i}_master.png",
            "created_at": "2026-08-25T10:00:00Z",
            "aspect_ratio": "1.8:1",
            "resolution": {"width": 1800, "height": 1000},
            "compiled_prompt": "Prompt for gen",
            "temperature": 1.0,
        }
        for i in range(4)
    ]
    app.dependency_overrides[get_generation_service] = lambda: mock_gen_service

    payload = {
        "moodboard_id": "mb_12345",
        "master_prompt": "A test prompt",
        "narrative": "A test narrative",
        "categories": {},
    }
    response = client.post("/api/moodboard/generate-baselines", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["baselines"]) == 4
    assert data["baselines"][0]["id"] == "gen_0"
