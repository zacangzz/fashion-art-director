import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.schemas.domain import TagChip, TagCategory

@pytest.mark.asyncio
async def test_analyze_moodboard_no_files():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/analyze")
        assert response.status_code == 422 or response.status_code == 400

@pytest.mark.asyncio
async def test_analyze_moodboard_too_many_files():
    files = [("files", (f"img_{i}.png", b"fake_bytes", "image/png")) for i in range(6)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/analyze", files=files)
        assert response.status_code == 400
        assert "Between 1 and 5 files" in response.json()["detail"]

@pytest.mark.asyncio
async def test_analyze_moodboard_invalid_mime_type():
    files = [("files", ("doc.txt", b"hello world", "text/plain"))]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/analyze", files=files)
        assert response.status_code == 400
        assert "Unsupported image/document format" in response.json()["detail"] or "Unsupported" in response.json()["detail"]

@pytest.mark.asyncio
async def test_analyze_moodboard_pdf_success():
    files = [("files", ("moodboard.pdf", b"%PDF-1.5 fake pdf content", "application/pdf"))]
    mock_chips = [
        TagChip(id="chip_1", category=TagCategory.MOOD_ERA, label="editorial"),
    ]

    with patch("app.api.moodboard.vision_service.analyze_moodboard", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_chips

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/moodboard/analyze", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["moodboard_id"].startswith("mb_")
            assert len(data["extracted_chips"]) == 1
            assert data["extracted_chips"][0]["label"] == "editorial"

@pytest.mark.asyncio
async def test_analyze_moodboard_success():
    files = [("files", ("sample.jpg", b"\xff\xd8fakejpeg", "image/jpeg"))]
    mock_chips = [
        TagChip(id="chip_1", category=TagCategory.MOOD_ERA, label="cinematic"),
        TagChip(id="chip_2", category=TagCategory.LIGHTING, label="golden hour"),
    ]

    with patch("app.api.moodboard.vision_service.analyze_moodboard", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_chips

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/moodboard/analyze", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["moodboard_id"].startswith("mb_")
            assert len(data["extracted_chips"]) == 2
            assert data["extracted_chips"][0]["label"] == "cinematic"


@pytest.mark.asyncio
async def test_analyze_and_baselines_with_aspect_ratio():
    files = [("files", ("sample.jpg", b"\xff\xd8fakejpeg", "image/jpeg"))]
    mock_state = {
        "master_prompt": "Cinematic scene",
        "narrative": "A high fashion scene",
        "categories": {},
    }
    mock_baselines = [
        {
            "id": "gen_base_1",
            "seed": 111222,
            "image_url": "/api/images/base1.png",
            "created_at": "2026-08-26T00:00:00Z",
            "aspect_ratio": "1.8:1",
            "resolution": {"width": 1920, "height": 1080},
            "compiled_prompt": "Cinematic scene",
        }
    ]

    with patch("app.api.moodboard.vision_service.extract_tag_studio_state", new_callable=AsyncMock) as mock_extract, \
         patch("app.api.moodboard.generation_service.generate_4_baselines", new_callable=AsyncMock) as mock_gen:
        mock_extract.return_value = mock_state
        mock_gen.return_value = mock_baselines

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/moodboard/analyze-and-baselines",
                files=files,
                data={"prompt": "Editorial vibe", "aspect_ratio": "1.8:1"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["moodboard_id"].startswith("mb_")
            assert len(data["baselines"]) == 1
            assert data["baselines"][0]["aspect_ratio"] == "1.8:1"
            assert data["baselines"][0]["resolution"]["width"] == 1920
            assert data["baselines"][0]["resolution"]["height"] == 1080
            mock_gen.assert_called_once()
            _, kwargs = mock_gen.call_args
            assert kwargs.get("aspect_ratio") == "1.8:1"

