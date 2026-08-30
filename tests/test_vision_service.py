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


@pytest.mark.asyncio
async def test_resync_prompt_from_levers_synthesizes_master_prompt():
    mock_client = MagicMock()
    resync_payload = {
        "master_prompt": "A chic model in a ruby red satin evening gown on a Venetian canal at sunset.",
        "narrative": "A high-fashion evening editorial in Venice.",
        "conflicts": [],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(resync_payload)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        result = await service.resync_prompt_from_levers(
            narrative="Venice evening",
            categories={
                "wardrobe_hair": [{"label": "ruby red satin evening gown", "enabled": True}],
                "environment": [{"label": "Venetian canal", "enabled": True}],
            },
        )

        assert result["master_prompt"] == "A chic model in a ruby red satin evening gown on a Venetian canal at sunset."
        assert result["narrative"] == "A high-fashion evening editorial in Venice."
        assert result["conflicts"] == []


@pytest.mark.asyncio
async def test_resync_levers_from_prompt_extracts_categories():
    mock_client = MagicMock()
    resync_payload = {
        "categories": {
            "subject_details": ["chic model with sleek dark hair"],
            "wardrobe_hair": ["ruby red satin evening gown"],
            "environment": ["Venetian canal", "waterway architecture"],
            "lighting": ["sunset ambient lighting"],
            "camera_optics": ["85mm prime lens f/1.4"],
        },
        "narrative": "A high-fashion evening editorial in Venice.",
        "conflicts": [],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(resync_payload)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        result = await service.resync_levers_from_prompt(
            master_prompt="A chic model in a ruby red satin evening gown on a Venetian canal at sunset.",
            narrative="Venice evening",
        )

        assert "categories" in result
        assert "wardrobe_hair" in result["categories"]
        assert len(result["categories"]["wardrobe_hair"]) == 1
        assert result["categories"]["wardrobe_hair"][0]["label"] == "ruby red satin evening gown"
        assert result["categories"]["environment"][0]["label"] == "Venetian canal"
        assert result["narrative"] == "A high-fashion evening editorial in Venice."


@pytest.mark.asyncio
async def test_resync_master_prompt_extracts_and_updates_categories():
    mock_client = MagicMock()
    resync_payload = {
        "master_prompt": "A chic model in a ruby red satin evening gown on a Venetian canal at sunset.",
        "narrative": "A high-fashion evening editorial in Venice.",
        "categories": {
            "subject_details": ["chic model with sleek dark hair"],
            "wardrobe_hair": ["ruby red satin evening gown"],
            "environment": ["Venetian canal", "waterway architecture"],
            "lighting": ["sunset ambient lighting"],
            "camera_optics": ["85mm prime lens f/1.4"],
        },
        "conflicts": [],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(resync_payload)
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        result = await service.resync_master_prompt(
            previous_master_prompt="User typed a new prompt with ruby red evening gown in Venice",
            narrative="Venice evening",
            categories={},
        )

        assert result["master_prompt"] == "A chic model in a ruby red satin evening gown on a Venetian canal at sunset."
        assert result["narrative"] == "A high-fashion evening editorial in Venice."
        assert "categories" in result
        assert "wardrobe_hair" in result["categories"]
        assert len(result["categories"]["wardrobe_hair"]) == 1
        assert result["categories"]["wardrobe_hair"][0]["label"] == "ruby red satin evening gown"
        assert result["categories"]["environment"][0]["label"] == "Venetian canal"


@pytest.mark.asyncio
async def test_vision_service_interactions_api_execution():
    mock_client = MagicMock()
    extracted_payload = {
        "master_prompt": "A chic model in high-fashion couture in Paris.",
        "narrative": "Parisian luxury editorial.",
        "categories": {
            "subject_details": ["Parisian female model"],
            "wardrobe_hair": ["haute couture silk trench coat"],
        },
    }
    mock_interaction = MagicMock()
    mock_interaction.output_text = json.dumps(extracted_payload)
    mock_interaction.usage.prompt_tokens = 120
    mock_interaction.usage.candidates_tokens = 80
    mock_interaction.usage.total_tokens = 200
    mock_client.interactions.create.return_value = mock_interaction

    with patch("app.services.vision_service.genai.Client", return_value=mock_client):
        service = VisionService(api_key="fake_key")
        result = await service.extract_tag_studio_state([b"fake_image_bytes"])

        assert result["master_prompt"] == "A chic model in high-fashion couture in Paris."
        assert result["narrative"] == "Parisian luxury editorial."
        assert "subject_details" in result["categories"]
        assert mock_client.interactions.create.called
        _, kwargs = mock_client.interactions.create.call_args
        assert kwargs["response_format"] == {
            "type": "text",
            "mime_type": "application/json",
        }


