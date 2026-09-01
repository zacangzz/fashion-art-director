import io
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.dependencies import get_generation_service


def _create_dummy_image_bytes():
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_inpaint_endpoint_success():
    img_bytes = _create_dummy_image_bytes()
    mask_bytes = _create_dummy_image_bytes()

    mock_inpaint_response = {
        "generation_id": "gen_inpaint_12345678",
        "parent_id": "gen_base_11223344",
        "seed": 4289102,
        "compiled_prompt": "[Inpaint Edit] change jacket to navy blue",
        "negative_prompt": "blurry, low quality",
        "image_url": "/api/images/gen_inpaint_12345678_master.png",
        "mask_url": "/api/images/gen_inpaint_12345678_mask.png",
        "mask_stats": {
            "width": 100,
            "height": 100,
            "total_pixels": 10000,
            "masked_pixels": 500,
            "coverage_percentage": 5.0,
            "bounding_box": {"min_x": 10, "min_y": 10, "max_x": 30, "max_y": 30, "width": 21, "height": 21},
        },
        "created_at": "2026-08-25T12:00:00Z",
        "aspect_ratio": "16:9",
        "resolution": {"width": 3840, "height": 2160},
    }

    mock_gen = MagicMock()
    mock_gen.inpaint_region.return_value = mock_inpaint_response
    app.dependency_overrides[get_generation_service] = lambda: mock_gen

    client = TestClient(app)
    files = {
        "image": ("source.png", img_bytes, "image/png"),
        "mask": ("mask.png", mask_bytes, "image/png"),
    }
    data = {
        "prompt": "change jacket to navy blue",
        "generation_id": "gen_base_11223344",
        "seed": "4289102",
        "aspect_ratio": "16:9",
    }
    response = client.post("/api/inpaint", files=files, data=data)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["generation_id"] == "gen_inpaint_12345678"
    assert res_json["parent_id"] == "gen_base_11223344"

    app.dependency_overrides.clear()
