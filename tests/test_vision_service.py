import json
from unittest.mock import MagicMock, patch
import pytest

from app.services.vision_service import VisionService
from app.schemas.domain import TagCategory


def test_extract_tag_studio_state_mocked():
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
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        state = service.extract_tag_studio_state([b"fake_image_bytes"])

        assert state["narrative"] == "A high-fashion summer editorial in Milan with vibrant colors."
        assert "subject_details" in state["categories"]
        assert len(state["categories"]["subject_details"]) == 1
        assert state["categories"]["subject_details"][0]["label"] == "striking female model with copper hair"
        assert state["categories"]["wardrobe_hair"][0]["label"] == "silk emerald green slip dress"


def test_extract_tag_studio_state_preserves_locked_categories():
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
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        state = service.extract_tag_studio_state(
            [b"fake_image_bytes"],
            locked_categories=["camera_optics"],
            existing_categories=existing_categories,
        )

        assert "camera_optics" in state["categories"]
        assert len(state["categories"]["camera_optics"]) == 1
        assert state["categories"]["camera_optics"][0]["label"] == "85mm prime f/1.4"
        assert state["categories"]["camera_optics"][0]["locked"] is True


def test_extract_tag_studio_state_fallback_when_empty():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "invalid json response"
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        state = service.extract_tag_studio_state([b"fake_image_bytes"])

        assert state is not None
        assert "categories" in state
        assert "subject_details" in state["categories"]
        assert len(state["categories"]["subject_details"]) >= 1


def test_extract_scene_schema_backwards_compatibility():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "narrative": "Compatible narrative",
        "categories": {
            "lighting": [{"label": "soft diffused window light", "weight": 1.0}]
        }
    })
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        schema = service.extract_scene_schema([b"fake_image_bytes"])

        assert schema["narrative"] == "Compatible narrative"
        assert "lighting" in schema["categories"]


def test_resync_prompt_from_levers():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "master_prompt": "Haute couture masterpiece featuring a silk emerald slip dress in an Italian courtyard.",
        "narrative": "Refined Italian courtyard elegance.",
        "conflicts": [
            {
                "id": "c1",
                "severity": "info",
                "conflicting_elements": ["warm tone", "cool dress"],
                "categories": ["lighting", "wardrobe_hair"],
                "explanation": "Harmonious contrast.",
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        result = service.resync_prompt_from_levers(
            narrative="Starting narrative",
            categories={
                "wardrobe_hair": [{"label": "silk emerald slip dress", "enabled": True}]
            }
        )

        assert "Haute couture masterpiece" in result["master_prompt"]
        assert result["narrative"] == "Refined Italian courtyard elegance."
        assert len(result["conflicts"]) == 1


def test_resync_levers_from_prompt():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "narrative": "Extracted runway narrative.",
        "categories": {
            "subject_details": ["tall avant-garde model"],
            "wardrobe_hair": ["architectural black blazer"],
            "lighting": ["stark high-contrast spotlight"],
        },
        "conflicts": []
    })
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        result = service.resync_levers_from_prompt(
            master_prompt="A stunning avant-garde runway shot with architectural black blazer under stark spotlight."
        )

        assert result["narrative"] == "Extracted runway narrative."
        assert "wardrobe_hair" in result["categories"]
        assert result["categories"]["wardrobe_hair"][0]["label"] == "architectural black blazer"
        assert result["categories"]["lighting"][0]["label"] == "stark high-contrast spotlight"


def test_check_prompt_conflicts():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "conflicts": [
            {
                "id": "conflict_1",
                "severity": "critical",
                "conflicting_elements": ["pitch dark night", "bright midday sun"],
                "categories": ["lighting", "environment"],
                "explanation": "Contradictory environmental lighting conditions specified.",
                "recommendation": "Choose either daylight or nighttime setting."
            }
        ]
    })
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key", model_name="gemini-3.5-flash-lite", client=mock_client)
        conflicts = service.check_prompt_conflicts(
            master_prompt="A model in pitch dark night with bright midday sun illuminating the background.",
            categories={
                "lighting": [{"label": "bright midday sun"}],
                "environment": [{"label": "pitch dark night"}],
            }
        )

        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "critical"
        assert "Contradictory" in conflicts[0]["explanation"]
