import io
from pathlib import Path
from typing import Dict, Union
from PIL import Image

PRESETS: Dict[str, tuple[int, int]] = {
    "01_SocialFeed_1080x1350": (1080, 1350),      # 4:5 Social Feed
    "02_StoryMobile_1080x1920": (1080, 1920),     # 9:16 Story / Mobile
    "03_WideBanner_1440x780": (1440, 780),        # ~1.85:1 Banner
    "04_Square_1440x1440": (1440, 1440),          # 1:1 High-Res Square
    "05_LandscapeDisplay_1730x960": (1730, 960),  # ~1.8:1 Landscape
}

def resize_and_crop(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Resizes and center-crops an image to the exact target dimensions with zero visual distortion.
    Uses Pillow's Lanczos resampling for high quality downscaling.
    """
    src_width, src_height = image.size
    target_ratio = target_width / target_height
    src_ratio = src_width / src_height

    if src_ratio > target_ratio:
        # Source is wider than target: crop horizontal sides evenly
        crop_width = src_height * target_ratio
        crop_height = float(src_height)
        left = (src_width - crop_width) / 2.0
        top = 0.0
        right = left + crop_width
        bottom = crop_height
    elif src_ratio < target_ratio:
        # Source is taller than target: crop top/bottom sides evenly
        crop_width = float(src_width)
        crop_height = src_width / target_ratio
        left = 0.0
        top = (src_height - crop_height) / 2.0
        right = crop_width
        bottom = top + crop_height
    else:
        # Aspect ratios match exactly
        left = 0.0
        top = 0.0
        right = float(src_width)
        bottom = float(src_height)

    crop_box = (
        int(round(left)),
        int(round(top)),
        int(round(right)),
        int(round(bottom)),
    )

    cropped_image = image.crop(crop_box)
    resized_image = cropped_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    return resized_image

def generate_all_presets(master_image_input: Union[str, Path, Image.Image]) -> Dict[str, bytes]:
    """
    Processes a master image against all 5 predefined target resolution presets.
    Returns a dictionary mapping filename (e.g. '01_SocialFeed_1080x1350.png') to PNG bytes.
    """
    if isinstance(master_image_input, (str, Path)):
        image = Image.open(master_image_input)
    elif isinstance(master_image_input, Image.Image):
        image = master_image_input
    else:
        raise ValueError(f"Invalid image input type: {type(master_image_input)}")

    # Ensure image mode is RGB for saving as PNG
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")

    preset_outputs: Dict[str, bytes] = {}

    for preset_name, (w, h) in PRESETS.items():
        processed_img = resize_and_crop(image, w, h)
        buffer = io.BytesIO()
        processed_img.save(buffer, format="PNG")
        filename = f"{preset_name}.png"
        preset_outputs[filename] = buffer.getvalue()

    return preset_outputs
