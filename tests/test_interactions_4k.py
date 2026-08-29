import io
import os
import base64
import pytest
from PIL import Image
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.generation_service import GenerationService
from app.utils.image_utils import (
    normalize_interaction_aspect_ratio,
    to_interaction_image_input,
)
from app.db.database import DatabaseManager


def test_normalize_interaction_aspect_ratio():
    assert normalize_interaction_aspect_ratio("1.8:1") == "16:9"
    assert normalize_interaction_aspect_ratio("1.85:1") == "16:9"
    assert normalize_interaction_aspect_ratio("2.39:1") == "21:9"
    assert normalize_interaction_aspect_ratio("1:1") == "1:1"
    assert normalize_interaction_aspect_ratio("2:3") == "2:3"
    assert normalize_interaction_aspect_ratio("16:9") == "16:9"
    assert normalize_interaction_aspect_ratio("unknown_ratio") == "16:9"


def test_to_interaction_image_input():
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    result = to_interaction_image_input(raw_bytes, optimize=False)
    assert result["type"] == "image"
    assert result["mime_type"] == "image/png"
    assert len(base64.b64decode(result["data"])) == len(raw_bytes)


def test_process_and_save_image_preserves_raw_4k_without_stretching(tmp_path):
    storage_dir = str(tmp_path / "storage")
    db_mgr = MagicMock()
    service = GenerationService(db_manager=db_mgr, api_key="fake", storage_dir=storage_dir)

    # 4K image (3840x2160)
    img_4k = Image.new("RGB", (3840, 2160), color=(255, 0, 0))
    buf = io.BytesIO()
    img_4k.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    out_file = str(tmp_path / "out_master.png")
    w, h = service._process_and_save_image(raw_bytes, out_file, "16:9")

    assert (w, h) == (3840, 2160)
    assert os.path.exists(out_file)
    with open(out_file, "rb") as f:
        saved_bytes = f.read()
    assert saved_bytes == raw_bytes  # Exact raw bytes preserved


@pytest.mark.asyncio
async def test_call_image_model_uses_interactions_4k(tmp_path):
    storage_dir = str(tmp_path / "storage")
    db_mgr = MagicMock()

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    img_4k = Image.new("RGB", (5504, 3072), color=(0, 255, 0))
    buf = io.BytesIO()
    img_4k.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    mock_interaction.output_image.data = base64.b64encode(raw_bytes).decode("utf-8")
    mock_client.interactions.create.return_value = mock_interaction

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake",
        storage_dir=storage_dir,
        client=mock_client,
    )

    result_bytes = await service._call_image_model(
        prompt="A high fashion model in Paris",
        aspect_ratio="1.8:1",  # Maps to 16:9
        model_name="gemini-3.1-flash-image",
    )

    assert result_bytes == raw_bytes
    mock_client.interactions.create.assert_called_once()
    _, kwargs = mock_client.interactions.create.call_args
    assert kwargs["model"] == "gemini-3.1-flash-image"
    assert kwargs["response_format"] == {
        "type": "image",
        "aspect_ratio": "16:9",
        "image_size": "4K",
    }
