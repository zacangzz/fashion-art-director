import pytest
import io
import os
import json
import base64
from PIL import Image
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def client():
    return TestClient(app)


def test_get_model_config(client):
    """Verify /api/models/config returns the allowed vision and imagen models with defaults."""
    response = client.get("/api/models/config")
    assert response.status_code == 200
    data = response.json()
    assert "available_vision_models" in data
    assert "available_imagen_models" in data
    assert "gemini-3.5-flash-lite" in data["available_vision_models"]
    assert "gemini-3.7-flash" in data["available_vision_models"]
    assert "gemini-3.1-flash-lite-image" in data["available_imagen_models"]
    assert "gemini-3.1-flash-image" in data["available_imagen_models"]
    assert "gemini-3-pro-image" in data["available_imagen_models"]
    assert data["inpaint_model"] == "gemini-3-pro-image"


def test_database_model_name_field():
    """Verify database schema contains model_name and persists it correctly."""
    fake_db = FakeFirestoreClient()
    db = FirestoreManager(fake_db)

    gen_id = "test_gen_model_1"
    record = {
        "id": gen_id,
        "parent_id": None,
        "moodboard_id": "mb_123",
        "is_baseline": True,
        "created_at": "2026-08-28T00:00:00Z",
        "schema_json": {"test": "data", "model_name": "gemini-3.1-flash-lite-image"},
        "compiled_prompt": "prompt",
        "negative_prompt": "neg",
        "seed": 12345,
        "master_image_path": "/tmp/test.png",
        "aspect_ratio": "1:1",
        "resolution_width": 1024,
        "resolution_height": 1024,
        "model_name": "gemini-3.1-flash-lite-image",
    }
    db.create_generation(user_id="local_dev_user", gen_data=record)

    saved = db.get_generation(gen_id)
    assert saved is not None
    assert saved["model_name"] == "gemini-3.1-flash-lite-image"
