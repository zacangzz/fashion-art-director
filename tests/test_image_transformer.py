import io
from PIL import Image
import pytest
from app.services.image_transformer import resize_and_crop, generate_all_presets, PRESETS

def create_synthetic_image(width: int, height: int, color=(255, 0, 0)) -> Image.Image:
    """Helper to create a solid color image for testing."""
    return Image.new("RGB", (width, height), color)

def test_resize_and_crop_square_to_portrait():
    # Source 1000x1000 square -> Target 1080x1350 (4:5 portrait)
    src = create_synthetic_image(1000, 1000)
    resized = resize_and_crop(src, 1080, 1350)
    assert resized.size == (1080, 1350)

def test_resize_and_crop_landscape_to_banner():
    # Source 3840x2160 (16:9 landscape) -> Target 1440x780 (~1.85:1 banner)
    src = create_synthetic_image(3840, 2160)
    resized = resize_and_crop(src, 1440, 780)
    assert resized.size == (1440, 780)

def test_generate_all_presets():
    # Master image 3840x2160
    src = create_synthetic_image(3840, 2160)
    presets = generate_all_presets(src)
    
    assert len(presets) == len(PRESETS)
    expected_filenames = {f"{key}.png" for key in PRESETS.keys()}
    assert set(presets.keys()) == expected_filenames
    
    for filename, img_bytes in presets.items():
        assert len(img_bytes) > 0
        img = Image.open(io.BytesIO(img_bytes))
        preset_key = filename.replace(".png", "")
        expected_size = PRESETS[preset_key]
        assert img.size == expected_size
        # Verify 300 DPI metadata in info
        if "dpi" in img.info:
            assert round(img.info["dpi"][0]) == 300
