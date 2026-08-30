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


@pytest.mark.asyncio
async def test_inpaint_region_uses_interactions_4k(tmp_path):
    storage_dir = str(tmp_path / "storage")
    db_mgr = AsyncMock()

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    img_4k = Image.new("RGB", (3840, 2160), color=(10, 20, 30))
    buf = io.BytesIO()
    img_4k.save(buf, format="PNG")
    raw_4k_bytes = buf.getvalue()

    mock_interaction.output_image.data = base64.b64encode(raw_4k_bytes).decode("utf-8")
    mock_interaction.usage.total_tokens = 2000
    mock_client.interactions.create.return_value = mock_interaction

    db_mgr.get_generation.return_value = {
        "id": "gen_parent_169",
        "aspect_ratio": "16:9",
        "seed": 4289102,
        "moodboard_id": "mb_123",
        "accumulated_cost_usd": 0.05,
        "accumulated_tokens": 1000,
    }

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake",
        storage_dir=storage_dir,
        client=mock_client,
    )

    mask = Image.new("L", (100, 100), color=255)
    mask_buf = io.BytesIO()
    mask.save(mask_buf, format="PNG")
    mask_bytes = mask_buf.getvalue()

    result = await service.inpaint_region(
        parent_id="gen_parent_169",
        image_bytes=raw_4k_bytes,
        mask_bytes=mask_bytes,
        prompt="Swap jacket to leather bomber",
    )

    assert result["aspect_ratio"] == "16:9"
    assert result["resolution"] == {"width": 3840, "height": 2160}
    mock_client.interactions.create.assert_called_once()
    _, kwargs = mock_client.interactions.create.call_args
    assert kwargs["response_format"] == {
        "type": "image",
        "aspect_ratio": "16:9",
        "image_size": "4K",
    }


@pytest.mark.asyncio
async def test_compose_wardrobe_preserves_parent_aspect_ratio_and_returns_it(tmp_path):
    storage_dir = str(tmp_path / "storage")
    gen_dir = os.path.join(storage_dir, "generations")
    os.makedirs(gen_dir, exist_ok=True)

    parent_img = os.path.join(gen_dir, "parent_169.png")
    img_4k = Image.new("RGB", (3840, 2160), color=(50, 60, 70))
    img_4k.save(parent_img, format="PNG")

    garment_crop = os.path.join(storage_dir, "garment.png")
    img_4k.save(garment_crop, format="PNG")

    db_mgr = AsyncMock()
    db_mgr.get_generation.return_value = {
        "id": "gen_parent_169",
        "aspect_ratio": "16:9",
        "master_image_path": parent_img,
        "seed": 4289102,
        "moodboard_id": "mb_123",
        "accumulated_cost_usd": 0.05,
        "accumulated_tokens": 1000,
    }
    db_mgr.get_wardrobe_item.return_value = {
        "id": "item_top_1",
        "label": "Silk Camisole",
        "category": "tops",
        "upscaled_image_path": garment_crop,
    }

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    with open(parent_img, "rb") as f:
        parent_bytes = f.read()

    mock_interaction.output_image.data = base64.b64encode(parent_bytes).decode("utf-8")
    mock_interaction.usage.total_tokens = 2000
    mock_client.interactions.create.return_value = mock_interaction

    wardrobe_service = MagicMock()
    wardrobe_service.ground_wardrobe_pins = AsyncMock(return_value={
        "grounded_pins": [{
            "pin_number": 1,
            "target_subject": "The model",
            "body_location": "torso",
        }],
    })

    service = GenerationService(
        db_manager=db_mgr,
        api_key="fake",
        storage_dir=storage_dir,
        client=mock_client,
        wardrobe_service=wardrobe_service,
    )

    result = await service.compose_wardrobe(
        parent_id="gen_parent_169",
        assignments=[{
            "wardrobe_item_id": "item_top_1",
            "pin_number": 1,
            "drop_position": {"x": 0.5, "y": 0.5},
            "target_description": "Silk Camisole",
        }],
    )

    assert result["aspect_ratio"] == "16:9"
    assert result["resolution"] == {"width": 3840, "height": 2160}
    mock_client.interactions.create.assert_called_once()
    _, kwargs = mock_client.interactions.create.call_args
    assert kwargs["response_format"] == {
        "type": "image",
        "aspect_ratio": "16:9",
        "image_size": "4K",
    }


def test_resolve_model_image_size():
    from app.services.image_generator import resolve_model_image_size

    assert resolve_model_image_size("gemini-3.1-flash-lite-image", "4K") == "1K"
    assert resolve_model_image_size("gemini-3.1-flash-lite-image", "2K") == "1K"
    assert resolve_model_image_size("gemini-3.1-flash-lite-image", "1K") == "1K"
    assert resolve_model_image_size("gemini-3.1-flash-lite-image", None) is None

    assert resolve_model_image_size("gemini-3.1-flash-image", "4K") == "4K"
    assert resolve_model_image_size("gemini-3.1-flash-image", "2K") == "2K"
    assert resolve_model_image_size("gemini-3-pro-image", "4K") == "4K"


@pytest.mark.asyncio
async def test_lite_model_generation_clamps_to_1k(tmp_path):
    storage_dir = str(tmp_path / "storage")
    db_mgr = MagicMock()

    mock_client = MagicMock()
    mock_interaction = MagicMock()
    img_1k = Image.new("RGB", (1024, 1024), color=(0, 0, 255))
    buf = io.BytesIO()
    img_1k.save(buf, format="PNG")
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
        prompt="A high fashion model in Milan",
        aspect_ratio="1:1",
        model_name="gemini-3.1-flash-lite-image",
    )

    assert result_bytes == raw_bytes
    mock_client.interactions.create.assert_called_once()
    _, kwargs = mock_client.interactions.create.call_args
    assert kwargs["model"] == "gemini-3.1-flash-lite-image"
    assert kwargs["response_format"] == {
        "type": "image",
        "aspect_ratio": "1:1",
        "image_size": "1K",
    }

