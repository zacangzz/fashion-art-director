import io
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "Image Gen Pipeline Studio" in response.json()["title"]


@pytest.mark.asyncio
@patch("app.api.moodboard.vision_service.extract_tag_studio_state")
@patch("app.api.moodboard.generation_service.generate_4_baselines")
async def test_analyze_and_baselines_endpoint(mock_gen_baselines, mock_vision):
    mock_vision.return_value = {
        "narrative": "A test editorial scene.",
        "categories": {
            "subject_details": [
                {"id": "t1", "category": "subject_details", "label": "model", "enabled": True, "locked": False, "weight": 1.0, "isCustom": False}
            ]
        },
    }
    mock_gen_baselines.return_value = [
        {"id": "gen_base_01", "seed": 111, "image_url": "/api/images/gen_base_01.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_02", "seed": 222, "image_url": "/api/images/gen_base_02.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_03", "seed": 333, "image_url": "/api/images/gen_base_03.png", "created_at": "2026-08-24T00:00:00Z"},
        {"id": "gen_base_04", "seed": 444, "image_url": "/api/images/gen_base_04.png", "created_at": "2026-08-24T00:00:00Z"},
    ]

    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    files = [("files", ("test.png", io.BytesIO(file_content), "image/png"))]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/analyze-and-baselines", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "moodboard_id" in data
        assert data["narrative"] == "A test editorial scene."
        assert "subject_details" in data["categories"]
        assert len(data["baselines"]) == 4
        assert data["baselines"][0]["seed"] == 111


@pytest.mark.asyncio
@patch("app.api.moodboard.vision_service.extract_tag_studio_state")
@patch("app.api.moodboard.generation_service.generate_4_baselines")
async def test_analyze_and_baselines_with_prompt_endpoint(mock_gen_baselines, mock_vision):
    mock_vision.return_value = {
        "narrative": "Sun-drenched midcentury living room with travertine table",
        "categories": {
            "environment": [
                {"id": "t2", "category": "environment", "label": "midcentury living room", "enabled": True, "locked": False, "weight": 1.0, "isCustom": False}
            ]
        },
    }
    mock_gen_baselines.return_value = [
        {"id": "gen_base_01", "seed": 111, "image_url": "/api/images/gen_base_01.png", "created_at": "2026-08-24T00:00:00Z"},
    ]

    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
    files = [("files", ("test.png", io.BytesIO(file_content), "image/png"))]
    data_payload = {"prompt": "Sun-drenched midcentury living room with travertine table"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/analyze-and-baselines", files=files, data=data_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["narrative"] == "Sun-drenched midcentury living room with travertine table"
        mock_vision.assert_called_once()
        assert mock_vision.call_args.kwargs["prompt"] == "Sun-drenched midcentury living room with travertine table"


@pytest.mark.asyncio
@patch("app.api.generation.generation_service.fine_tune_generation")
async def test_fine_tune_generation_api(mock_fine_tune):
    mock_fine_tune.return_value = {
        "generation_id": "gen_child_01",
        "parent_id": "gen_base_01",
        "seed": 918231,
        "compiled_prompt": "fine tuned prompt",
        "negative_prompt": "blurry",
        "image_url": "/api/images/gen_child_01.png",
        "created_at": "2026-08-24T00:00:00Z",
    }

    payload = {
        "parent_id": "gen_base_01",
        "narrative": "Refined campaign narrative",
        "categories": {
            "lighting": [{"label": "soft sunlight", "weight": 1.0, "enabled": True}]
        },
        "seed_mode": "locked",
        "seed": 918231,
        "use_image_reference": True,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/generate/fine-tune", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["generation_id"] == "gen_child_01"
        assert data["parent_id"] == "gen_base_01"
        assert data["seed"] == 918231


@pytest.mark.asyncio
async def test_history_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/history")
        assert response.status_code == 200
        data = response.json()
        assert "generations" in data
        assert isinstance(data["generations"], list)

