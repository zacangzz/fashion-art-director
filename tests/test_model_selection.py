import pytest
import io
import os
import json
import base64
from PIL import Image
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import DatabaseManager


@pytest.fixture
def client():
    return TestClient(app)


def create_test_image_bytes(width=100, height=100, color=(255, 0, 0)):
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_get_model_config(client):
    """Verify /api/models/config returns the allowed vision and imagen models with defaults."""
    response = client.get("/api/models/config")
    assert response.status_code == 200
    data = response.json()
    assert "available_vision_models" in data
    assert "available_imagen_models" in data
    assert "gemini-3.5-flash-lite" in data["available_vision_models"]
    assert "gemini-3.7-flash" in data["available_vision_models"]
    assert "gemini-3.1-flash-lite-image" in data["available_imagen_models"]
    assert "gemini-3.1-flash-image" in data["available_imagen_models"]
    assert "gemini-3-pro-image" in data["available_imagen_models"]
    assert data["inpaint_model"] == "gemini-3-pro-image"


@pytest.mark.asyncio
async def test_database_model_name_column(tmp_path):
    """Verify database schema contains model_name and persists it correctly."""
    db_path = os.path.join(tmp_path, "test_models.db")
    db = DatabaseManager(db_path=db_path)
    await db.init_db()

    gen_id = "test_gen_model_1"
    record = {
        "id": gen_id,
        "parent_id": None,
        "moodboard_id": "mb_123",
        "is_baseline": True,
        "created_at": "2026-08-28T00:00:00Z",
        "schema_json": {"test": "data", "model_name": "gemini-3.1-flash-lite-image"},
        "compiled_prompt": "prompt",
        "negative_prompt": "neg",
        "seed": 12345,
        "master_image_path": "/tmp/test.png",
        "aspect_ratio": "1:1",
        "resolution_width": 1024,
        "resolution_height": 1024,
        "model_name": "gemini-3.1-flash-lite-image",
    }
    await db.create_generation(record)

    fetched = await db.get_generation(gen_id)
    assert fetched is not None
    assert fetched.get("model_name") == "gemini-3.1-flash-lite-image"


@pytest.mark.asyncio
async def test_generation_service_custom_model_tracking(tmp_path):
    """Verify GenerationService passes custom imagen_model to _call_image_model and records it in DB."""
    from app.services.generation_service import GenerationService

    db_path = os.path.join(tmp_path, "test_gen_service.db")
    db = DatabaseManager(db_path=db_path)
    await db.init_db()

    gen_service = GenerationService(
        db_manager=db,
        api_key="fake-key",
        storage_dir=str(tmp_path),
        model_name="gemini-3.1-flash-image",
        inpaint_model_name="gemini-3-pro-image",
    )

    test_img = create_test_image_bytes()
    with patch.object(gen_service, "_call_image_model", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = test_img

        result = await gen_service.generate_single_baseline(
            moodboard_id="mb_test",
            state_dict={"narrative": "test narrative"},
            positive_prompt="high fashion dress",
            negative_prompt="blurry",
            seed=99999,
            aspect_ratio="1:1",
            imagen_model="gemini-3-pro-image",
        )

        assert mock_call.called
        assert mock_call.call_args.kwargs["model_name"] == "gemini-3-pro-image"

        # Verify record in DB has model_name set
        record = await db.get_generation(result["id"])
        assert record is not None
        assert record.get("model_name") == "gemini-3-pro-image"
        assert record["schema_json"].get("imagen_model") == "gemini-3-pro-image"


@pytest.mark.asyncio
async def test_inpaint_strictly_uses_gemini_3_pro_image(tmp_path):
    """Verify inpaint_region strictly uses gemini-3-pro-image regardless of defaults via Interactions API."""
    from app.services.generation_service import GenerationService

    db_path = os.path.join(tmp_path, "test_inpaint.db")
    db = DatabaseManager(db_path=db_path)
    await db.init_db()

    gen_service = GenerationService(
        db_manager=db,
        api_key="fake-key",
        storage_dir=str(tmp_path),
        model_name="gemini-3.1-flash-lite-image",
        inpaint_model_name="gemini-3-pro-image",
    )

    source_bytes = create_test_image_bytes(200, 200, (100, 100, 100))
    mask_bytes = create_test_image_bytes(200, 200, (255, 255, 255))
    output_bytes = create_test_image_bytes(200, 200, (0, 255, 0))

    mock_interaction = MagicMock()
    mock_interaction.output_image.data = base64.b64encode(output_bytes).decode("utf-8")
    mock_interaction.usage.total_tokens = 500

    with patch.object(gen_service.client.interactions, "create", return_value=mock_interaction) as mock_create:
        result = await gen_service.inpaint_region(
            parent_id="",
            image_bytes=source_bytes,
            mask_bytes=mask_bytes,
            prompt="change color to red",
        )

        assert mock_create.called
        assert mock_create.call_args.kwargs["model"] == "gemini-3-pro-image"

        saved_gen = await db.get_generation(result["generation_id"])
        assert saved_gen is not None
        assert saved_gen.get("model_name") == "gemini-3-pro-image"
        assert saved_gen["schema_json"].get("inpaint_model") == "gemini-3-pro-image"
