import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.dependencies import get_db_manager, get_storage_service, get_generation_service
from fake_firestore import FakeFirestoreClient
from app.db.database import FirestoreManager


@pytest.fixture
def client():
    fake_db_client = FakeFirestoreClient()
    db_manager = FirestoreManager(fake_db_client)

    app.dependency_overrides[get_db_manager] = lambda: db_manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_models_config_endpoint(client):
    res = client.get("/api/models/config")
    assert res.status_code == 200
    data = res.json()
    assert "available_vision_models" in data
    assert "available_imagen_models" in data


def test_history_endpoint_empty(client):
    res = client.get("/api/history")
    assert res.status_code == 200
    assert res.json() == {"generations": []}


def test_history_endpoint_populated(client):
    db_manager = app.dependency_overrides[get_db_manager]()
    db_manager.create_generation(
        user_id="local_dev_user",
        gen_data={
            "id": "gen_1001",
            "prompt": "Luxury haute couture gown",
            "cost_usd": 0.04,
            "tokens": 1500,
        }
    )

    res = client.get("/api/history")
    assert res.status_code == 200
    items = res.json()["generations"]
    assert len(items) == 1
    assert items[0]["id"] == "gen_1001"
