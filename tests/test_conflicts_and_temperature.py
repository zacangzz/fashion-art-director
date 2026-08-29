import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.utils.image_utils import optimize_reference_image, to_image_part
from app.schemas.domain import PromptConflict, GenerateBaselinesRequest


def _create_sample_png_bytes(width: int = 3000, height: int = 2000) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_optimize_reference_image_reduces_size():
    raw_png = _create_sample_png_bytes(width=3000, height=2000)
    assert len(raw_png) > 0

    opt_bytes, mime = optimize_reference_image(raw_png, max_dimension=1024, target_format="WEBP", quality=85)
    assert mime == "image/webp"
    assert len(opt_bytes) < len(raw_png)

    # Validate output image dimensions
    pil_opt = Image.open(io.BytesIO(opt_bytes))
    assert pil_opt.width <= 1024
    assert pil_opt.height <= 1024


def test_optimize_reference_image_skips_pdf():
    pdf_bytes = b"%PDF-1.5 fake pdf bytes"
    opt_bytes, mime = optimize_reference_image(pdf_bytes)
    assert opt_bytes == pdf_bytes
    assert mime == "application/pdf"


@pytest.mark.asyncio
async def test_check_conflicts_endpoint_success():
    mock_conflicts = [
        {
            "id": "conflict_1",
            "severity": "warning",
            "conflicting_elements": ["harsh afternoon sunlight", "soft studio strobe"],
            "categories": ["lighting"],
            "explanation": "Contradictory lighting setups.",
            "recommendation": "Use single lighting source.",
        }
    ]

    with patch("app.api.moodboard.vision_service.check_prompt_conflicts", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = mock_conflicts

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "master_prompt": "A model standing under harsh afternoon sunlight in soft studio strobe setup.",
                "narrative": "Studio portrait",
                "categories": {
                    "lighting": [{"label": "harsh afternoon sunlight"}, {"label": "soft studio strobe"}]
                },
            }
            response = await client.post("/api/moodboard/check-conflicts", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "conflicts" in data
            assert len(data["conflicts"]) == 1
            assert data["conflicts"][0]["id"] == "conflict_1"
            assert data["conflicts"][0]["conflicting_elements"] == ["harsh afternoon sunlight", "soft studio strobe"]


@pytest.mark.asyncio
async def test_generate_baselines_with_temperature():
    mock_baselines = [
        {
            "id": "gen_base_123",
            "seed": 4289102,
            "image_url": "/api/images/gen_base_123_master.png",
            "created_at": "2026-08-30T00:00:00Z",
            "aspect_ratio": "1.8:1",
            "resolution": {"width": 3840, "height": 2133},
            "compiled_prompt": "Master prompt...",
            "temperature": 1.45,
        }
    ]

    with patch("app.api.moodboard.generation_service.generate_4_baselines", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_baselines

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "moodboard_id": "mb_12345",
                "master_prompt": "High fashion editorial photo.",
                "narrative": "Editorial portrait",
                "categories": {"mood_era": [{"label": "cinematic"}]},
                "aspect_ratio": "1.8:1",
                "temperature": 1.45,
            }
            response = await client.post("/api/moodboard/generate-baselines", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert len(data["baselines"]) == 1
            assert data["baselines"][0]["temperature"] == 1.45

            # Verify generation_service received temperature=1.45
            mock_gen.assert_called_once()
            _, kwargs = mock_gen.call_args
            assert kwargs.get("temperature") == 1.45


@pytest.mark.asyncio
async def test_resync_prompt_returns_conflicts():
    mock_resync_result = {
        "master_prompt": "Resynced master prompt",
        "narrative": "Updated narrative",
        "conflicts": [
            {
                "id": "conflict_2",
                "severity": "warning",
                "conflicting_elements": ["winter parka", "beach swimwear"],
                "categories": ["wardrobe_hair"],
                "explanation": "Contradictory attire seasons.",
                "recommendation": "Pick one seasonal attire.",
            }
        ],
    }

    with patch("app.api.moodboard.vision_service.resync_master_prompt", new_callable=AsyncMock) as mock_resync:
        mock_resync.return_value = mock_resync_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "narrative": "Updated narrative",
                "categories": {"wardrobe_hair": [{"label": "winter parka"}, {"label": "beach swimwear"}]},
                "previous_master_prompt": "Previous prompt",
            }
            response = await client.post("/api/moodboard/resync-prompt", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["master_prompt"] == "Resynced master prompt"
            assert "conflicts" in data
            assert len(data["conflicts"]) == 1
            assert data["conflicts"][0]["id"] == "conflict_2"
