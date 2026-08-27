import json
from unittest.mock import MagicMock, patch
import pytest

from app.services.vision_service import VisionService
from app.schemas.domain import TagCategory


@pytest.mark.asyncio
async def test_extract_tag_studio_state_mocked():
    mock_client = MagicMock()

    extracted_payload = {
        "narrative": "A high-fashion summer editorial in Milan with vibrant colors.",
        "categories": {
            "subject_details": [{"label": "striking female model with copper hair", "weight": 1.0}],
            "objects_props": [{"label": "vintage leather armchair", "weight": 1.0}],
            "wardrobe_hair": [{"label": "silk emerald green slip dress", "weight": 1.0}],
            "environment": [{"label": "sun-drenched Italian courtyard", "weight": 1.0}],
            "layout_framing": [{"label": "medium-close portrait", "weight": 1.0}],
            "lighting": [{"label": "direct golden hour sunlight", "weight": 1.0}],
            "color_profile": [{"label": "warm terracotta and emerald green palette", "weight": 1.0}],
            "camera_optics": [{"label": "shot on 35mm f/1.8 lens", "weight": 1.0}],
            "mood_era": [{"label": "1990s retro luxury vibe", "weight": 1.0}],
        },
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(extracted_payload)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.1-flash-lite")
        state = await service.extract_tag_studio_state([b"fake_image_bytes"])

        assert state["narrative"] == "A high-fashion summer editorial in Milan with vibrant colors."
        assert "subject_details" in state["categories"]
        assert len(state["categories"]["subject_details"]) == 1
        assert state["categories"]["subject_details"][0]["label"] == "striking female model with copper hair"
        assert state["categories"]["wardrobe_hair"][0]["label"] == "silk emerald green slip dress"


@pytest.mark.asyncio
async def test_extract_tag_studio_state_preserves_locked_categories():
    mock_client = MagicMock()

    extracted_payload = {
        "narrative": "New extracted narrative.",
        "categories": {
            "subject_details": [{"label": "new subject", "weight": 1.0}],
            "camera_optics": [{"label": "50mm f/2.8", "weight": 1.0}],
        },
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(extracted_payload)
    mock_client.models.generate_content.return_value = mock_response

    existing_categories = {
        "camera_optics": [
            {"id": "tag_cam_locked", "category": "camera_optics", "label": "85mm prime f/1.4", "enabled": True, "locked": True, "isCustom": False}
        ]
    }

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        state = await service.extract_tag_studio_state(
            [b"fake_image_bytes"],
            locked_categories=["camera_optics"],
            existing_categories=existing_categories,
        )

        assert "camera_optics" in state["categories"]
        assert state["categories"]["camera_optics"][0]["label"] == "85mm prime f/1.4"


@pytest.mark.asyncio
async def test_analyze_moodboard_returns_all_chips():
    mock_client = MagicMock()
    extracted_payload = {
        "narrative": "Scene narrative",
        "categories": {
            "subject_details": [{"label": "test subject", "weight": 1.0}],
            "lighting": [{"label": "test lighting", "weight": 1.0}],
        },
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(extracted_payload)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        chips = await service.analyze_moodboard([b"fake_image_bytes"])

        assert len(chips) >= 2
        labels = [c.label for c in chips]
        assert "test subject" in labels
        assert "test lighting" in labels
