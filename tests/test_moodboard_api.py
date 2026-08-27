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


@pytest.mark.asyncio
async def test_upload_direct_photo_success():
    import io
    from PIL import Image
    img_byte_arr = io.BytesIO()
    Image.new("RGB", (200, 300), color=(255, 0, 0)).save(img_byte_arr, format="PNG")
    png_bytes = img_byte_arr.getvalue()

    files = {"file": ("my_photo.png", png_bytes, "image/png")}

    mock_result = {
        "generation_id": "gen_upload_test1234",
        "image_url": "/api/images/gen_upload_test1234_master.png",
        "seed": 555666,
        "aspect_ratio": "2:3",
        "resolution": {"width": 200, "height": 300},
        "compiled_prompt": "Uploaded Reference Image",
        "created_at": "2026-08-27T00:00:00Z",
    }

    with patch("app.api.moodboard.generation_service.register_uploaded_photo", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = mock_result
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/moodboard/upload-direct-photo", files=files)
            assert response.status_code == 200
            data = response.json()
            assert data["generation_id"] == "gen_upload_test1234"
            assert data["aspect_ratio"] == "2:3"
            assert data["compiled_prompt"] == "Uploaded Reference Image"
            assert data["resolution"]["width"] == 200
            assert data["resolution"]["height"] == 300
            assert "/api/images/" in data["image_url"]
            mock_reg.assert_called_once()


@pytest.mark.asyncio
async def test_upload_direct_photo_with_custom_aspect_ratio():
    import io
    from PIL import Image
    img_byte_arr = io.BytesIO()
    Image.new("RGB", (400, 400), color=(0, 255, 0)).save(img_byte_arr, format="PNG")
    png_bytes = img_byte_arr.getvalue()

    files = {"file": ("square.png", png_bytes, "image/png")}

    mock_result = {
        "generation_id": "gen_upload_test5678",
        "image_url": "/api/images/gen_upload_test5678_master.png",
        "seed": 777888,
        "aspect_ratio": "16:9",
        "resolution": {"width": 400, "height": 400},
        "compiled_prompt": "Uploaded Reference Image",
        "created_at": "2026-08-27T00:00:00Z",
    }

    with patch("app.api.moodboard.generation_service.register_uploaded_photo", new_callable=AsyncMock) as mock_reg:
        mock_reg.return_value = mock_result
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/moodboard/upload-direct-photo",
                files=files,
                data={"aspect_ratio": "16:9"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["aspect_ratio"] == "16:9"
            mock_reg.assert_called_once()
            _, kwargs = mock_reg.call_args
            assert kwargs.get("custom_aspect_ratio") == "16:9"


@pytest.mark.asyncio
async def test_upload_direct_photo_invalid_mime():
    files = {"file": ("document.pdf", b"%PDF fake", "application/pdf")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/upload-direct-photo", files=files)
        assert response.status_code == 400
        assert "Unsupported format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_direct_photo_empty():
    files = {"file": ("empty.png", b"", "image/png")}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/moodboard/upload-direct-photo", files=files)
        assert response.status_code == 400


