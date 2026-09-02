import io
import os
import base64
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch

from app.services.generation_service import GenerationService
from app.services.image_generator import ImageGenerator
from app.utils.image_utils import (
    normalize_interaction_aspect_ratio,
    to_interaction_image_input,
)
from app.db.database import FirestoreManager
from fake_firestore import FakeFirestoreClient


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


def test_save_generation_image(tmp_path):
    storage_dir = str(tmp_path / "storage")
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    service = GenerationService(db_manager=db_mgr, api_key="fake", storage_dir=storage_dir)

    img_4k = Image.new("RGB", (3840, 2160), color=(255, 0, 0))
    buf = io.BytesIO()
    img_4k.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    storage_path, w, h = service._save_generation_image("local_dev_user", "out_master.png", raw_bytes, "16:9")
    assert (w, h) == (3840, 2160)
    assert os.path.exists(service.storage_service.get_local_file_path(storage_path))


def test_image_generator_generate(tmp_path):
    img_4k = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img_4k.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    mock_interaction.output_image = MagicMock(data=raw_bytes)
    mock_interaction.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=100, total_token_count=200)
    mock_client.interactions.create.return_value = mock_interaction

    generator = ImageGenerator(client=mock_client, default_model="gemini-3-pro-image")
    output = generator.generate(
        prompt="A photo",
        aspect_ratio="16:9",
        image_size="4K",
    )
    assert len(output) > 0
    assert mock_client.interactions.create.called


def test_image_generator_timeout_fails_fast():
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = Exception("Request timed out. This is a client-side timeout.")

    generator = ImageGenerator(client=mock_client, default_model="gemini-3-pro-image")
    with pytest.raises(Exception) as exc_info:
        generator.generate(prompt="Test timeout", aspect_ratio="1:1")
    assert "Request timed out" in str(exc_info.value)
    # Must only call once (fail fast without retrying)
    assert mock_client.interactions.create.call_count == 1


def test_image_generator_transient_retry():
    img_1k = Image.new("RGB", (100, 100), color=(0, 255, 0))
    buf = io.BytesIO()
    img_1k.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    mock_client = MagicMock()
    mock_success = MagicMock()
    mock_success.output_image = MagicMock(data=raw_bytes)
    mock_success.usage_metadata = MagicMock(prompt_token_count=50, candidates_token_count=50, total_token_count=100)

    # First attempt raises 503, second succeeds
    mock_client.interactions.create.side_effect = [
        Exception("503 Service Unavailable"),
        mock_success,
    ]

    generator = ImageGenerator(client=mock_client, default_model="gemini-3-pro-image")
    output = generator.generate(prompt="Test retry", aspect_ratio="1:1")
    assert len(output) > 0
    assert mock_client.interactions.create.call_count == 2

