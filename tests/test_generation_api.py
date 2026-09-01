import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_generation_service


def test_generate_image_endpoint():
    payload = {
        "moodboard_id": "mb_12345",
        "chips": [
            {
                "id": "chip_1",
                "category": "subject_details",
                "label": "vintage leather jacket",
                "enabled": True,
                "locked": False,
                "weight": 1.0,
                "isCustom": False
            },
            {
                "id": "chip_2",
                "category": "lighting",
                "label": "neon rim lighting",
                "enabled": True,
                "locked": False,
                "weight": 1.2,
                "isCustom": False
            }
        ],
        "seed_mode": "locked",
        "seed": 4289102,
        "negative_prompt": "blurry, low quality",
        "aspect_ratio": "1:1"
    }

    mock_gen_response = {
        "generation_id": "gen_55667788",
        "created_at": "2026-08-23T22:51:30Z",
        "compiled_prompt": "vintage leather jacket. (neon rim lighting:1.2)",
        "seed": 4289102,
        "master_image_url": "/api/images/gen_55667788_master.png",
        "resolution": {"width": 1440, "height": 1440}
    }

    mock_gen = MagicMock()
    mock_gen.generate_image.return_value = mock_gen_response
    app.dependency_overrides[get_generation_service] = lambda: mock_gen

    client = TestClient(app)
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["generation_id"] == "gen_55667788"
    assert data["compiled_prompt"] == "vintage leather jacket. (neon rim lighting:1.2)"
    assert data["seed"] == 4289102

    app.dependency_overrides.clear()
