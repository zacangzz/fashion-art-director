import io
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from PIL import Image
from app.main import app


def _create_dummy_image_bytes():
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_inpaint_endpoint_success():
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

    with patch("app.api.inpaint.generation_service.inpaint_region", new_callable=AsyncMock) as mock_inpaint:
        mock_inpaint.return_value = mock_inpaint_response

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
            response = await client.post("/api/inpaint", files=files, data=data)
            assert response.status_code == 200
            res_json = response.json()
            assert res_json["generation_id"] == "gen_inpaint_12345678"
            assert res_json["parent_id"] == "gen_base_11223344"
            assert res_json["image_url"] == "/api/images/gen_inpaint_12345678_master.png"
            assert res_json["mask_url"] == "/api/images/gen_inpaint_12345678_mask.png"
            assert res_json["aspect_ratio"] == "16:9"
            assert res_json["mask_stats"]["coverage_percentage"] == 5.0
            mock_inpaint.assert_called_once()
            _, kwargs = mock_inpaint.call_args
            assert kwargs["aspect_ratio"] == "16:9"



@pytest.mark.asyncio
async def test_inpaint_endpoint_empty_prompt():
    img_bytes = _create_dummy_image_bytes()
    mask_bytes = _create_dummy_image_bytes()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {
            "image": ("source.png", img_bytes, "image/png"),
            "mask": ("mask.png", mask_bytes, "image/png"),
        }
        data = {
            "prompt": "   ",
        }
        response = await client.post("/api/inpaint", files=files, data=data)
        assert response.status_code == 400
        assert "prompt cannot be empty" in response.json()["detail"]
