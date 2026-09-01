import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_db_manager, get_storage_service, get_generation_service, get_vision_service
from fake_firestore import FakeFirestoreClient
from app.db.database import FirestoreManager
from app.services.storage_service import StorageService
from app.services.prompt_compiler import PromptCompiler
from app.services.vision_service import VisionService
from app.services.generation_service import GenerationService


@pytest.fixture
def mock_db_and_storage(tmp_path):
    fake_db = FakeFirestoreClient()
    db_mgr = FirestoreManager(fake_db)
    storage_service = StorageService(environment="local", storage_dir=str(tmp_path / "storage"))
    return db_mgr, storage_service


@pytest.fixture
def client(mock_db_and_storage):
    db_mgr, storage_service = mock_db_and_storage
    app.dependency_overrides[get_db_manager] = lambda: db_mgr
    app.dependency_overrides[get_storage_service] = lambda: storage_service
    yield TestClient(app)
    app.dependency_overrides.clear()


def create_sample_png_bytes(width=100, height=100, color=(200, 100, 50)):
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# 1. Vision Service 3D Spatial Scene Analysis Unit Tests
# --------------------------------------------------------------------------

def test_vision_service_analyze_spatial_scene():
    mock_genai_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = """
    {
      "camera_and_perspective_directive": "Frame with wide 28mm lens at eye level facing directly towards the large window.",
      "subject_spatial_placement_directive": "Position the two brothers standing naturally in the midground in front of the window glass.",
      "photometric_lighting_and_shadow_directive": "Natural golden sunlight streaming through the window creating soft rim lighting on hair and authentic contact floor shadows.",
      "unified_scene_synthesis_prompt": "Editorial fashion photograph of the two brothers standing in front of the floor-to-ceiling glass window."
    }
    """
    mock_response.usage_metadata = MagicMock(prompt_token_count=850, candidates_token_count=180, total_token_count=1030)
    mock_genai_client.interactions.create.return_value = mock_response

    vision_service = VisionService(
        api_key="fake-key",
        client=mock_genai_client,
        model_name="gemini-3.7-flash",
    )

    subj_bytes = create_sample_png_bytes()
    bg_bytes = create_sample_png_bytes()
    staging_params = {
        "subject_x": 0.5,
        "subject_y": 0.65,
        "camera_x": 0.5,
        "camera_y": 0.9,
        "camera_angle": "facing_window",
        "focal_length_mm": 28,
        "zoom_level": "wide",
    }

    result = vision_service.analyze_spatial_scene_reprojection(
        subject_image_bytes=subj_bytes,
        background_image_bytes=bg_bytes,
        user_prompt="with the boys as primary focus, camera facing the window, zoom out slightly",
        staging_params=staging_params,
    )

    assert "wide 28mm" in result["camera_and_perspective_directive"]
    assert "two brothers" in result["subject_spatial_placement_directive"]
    assert "golden sunlight" in result["photometric_lighting_and_shadow_directive"]
    assert result["tokens"]["total_token_count"] == 1030
    assert result["cost_usd"] > 0.0


# --------------------------------------------------------------------------
# 2. Prompt Compiler with Spatial Directives Tests
# --------------------------------------------------------------------------

def test_prompt_compiler_spatial_directives():
    compiled = PromptCompiler.format_background_refinement_prompt(
        prompt="two brothers standing by the window",
        perspective_mode="auto_align",
        depth_of_field="cinematic_bokeh",
        lighting_mode="harmonize_ambient",
        spatial_placement_instruction="Position brothers at (0.5, 0.65) in front of window midground.",
        camera_directive="Camera at 28mm wide angle facing window.",
        lighting_directive="Soft ambient backlight with rim illumination.",
    )

    assert "MASTER PHOTOGRAPHIC SCENE SYNTHESIS" in compiled
    assert "Camera at 28mm wide angle facing window." in compiled
    assert "Position brothers at (0.5, 0.65) in front of window midground." in compiled
    assert "Soft ambient backlight with rim illumination." in compiled
    assert "NO 2D sticker cutouts" in compiled


# --------------------------------------------------------------------------
# 3. Two-Pass Generation Service Refinement with Spatial Staging Tests
# --------------------------------------------------------------------------

def test_generation_service_spatial_staging_two_pass(mock_db_and_storage):
    db_mgr, storage_service = mock_db_and_storage

    # Create parent generation
    storage_service.upload_bytes("test_user", "generations", "parent.png", create_sample_png_bytes())
    db_mgr.create_generation(
        user_id="test_user",
        gen_data={
            "id": "gen_parent_spatial",
            "user_id": "test_user",
            "master_image_path": "test_user/generations/parent.png",
            "seed": 123456,
            "accumulated_cost_usd": 0.05,
            "accumulated_tokens": 1000,
        },
    )

    # Create background reference
    storage_service.upload_bytes("test_user", "backgrounds", "bg_window.png", create_sample_png_bytes())
    db_mgr.create_background_reference(
        user_id="test_user",
        bg_data={
            "id": "bg_window_ref",
            "original_filename": "window.png",
            "image_path": "test_user/backgrounds/bg_window.png",
        },
    )

    mock_vision = MagicMock()
    mock_vision.analyze_spatial_scene_reprojection.return_value = {
        "camera_and_perspective_directive": "Camera 24mm wide angle facing the glass window.",
        "subject_spatial_placement_directive": "Brothers in front of window.",
        "photometric_lighting_and_shadow_directive": "Window ambient backlighting.",
        "unified_scene_synthesis_prompt": "Brothers at window scene.",
        "cost_usd": 0.0035,
        "tokens": {"total_token_count": 500},
    }

    mock_img_gen = MagicMock()
    mock_img_gen.last_call_metrics = {
        "cost_usd": 0.151,
        "total_token_count": 1200,
        "cost_breakdown": {"prompt_cost_usd": 0.001, "images_cost_usd": 0.15},
    }
    mock_img_gen.generate.return_value = create_sample_png_bytes()

    gen_service = GenerationService(
        db_manager=db_mgr,
        storage_service=storage_service,
        vision_service=mock_vision,
        image_generator=mock_img_gen,
    )

    result = gen_service.refine_generation(
        parent_id="gen_parent_spatial",
        prompt="boys facing the window, zoom out",
        seed=123456,
        background_reference_id="bg_window_ref",
        spatial_staging={
            "subject_x": 0.5,
            "subject_y": 0.65,
            "camera_angle": "facing_window",
            "focal_length_mm": 24,
            "zoom_level": "wide",
        },
        user_id="test_user",
    )

    # Verify Vision pass was executed
    mock_vision.analyze_spatial_scene_reprojection.assert_called_once()

    # Verify multi-image was called with dual reference [parent, bg]
    mock_img_gen.generate.assert_called_once()
    call_args = mock_img_gen.generate.call_args
    passed_refs = call_args.kwargs.get("reference_images") or []
    assert len(passed_refs) == 2  # [parent_bytes, bg_bytes]


    # Verify combined cost & tokens
    assert result["cost_usd"] == pytest.approx(0.151 + 0.0035, rel=1e-3)
    assert result["tokens"] == 1200 + 500
    assert result["background_harmonization_meta"]["spatial_staging"]["focal_length_mm"] == 24


# --------------------------------------------------------------------------
# 4. API Route POST /api/refine with Spatial Staging Tests
# --------------------------------------------------------------------------

def test_api_refine_with_spatial_staging(client, mock_db_and_storage):
    db_mgr, storage_service = mock_db_and_storage

    storage_service.upload_bytes("test_user", "generations", "parent.png", create_sample_png_bytes())
    db_mgr.create_generation(
        user_id="test_user",
        gen_data={"id": "gen_p1", "user_id": "test_user", "master_image_path": "test_user/generations/parent.png", "seed": 999},
    )

    mock_gen_service = MagicMock()
    mock_gen_service.refine_generation.return_value = {
        "generation_id": "gen_spatial_child",
        "parent_id": "gen_p1",
        "seed": 999,
        "compiled_prompt": "MASTER PHOTOGRAPHIC SCENE SYNTHESIS ...",
        "negative_prompt": "blurry",
        "image_url": "/api/images/test_user/generations/gen_spatial_child_master.png",
        "created_at": "2026-09-01T12:00:00Z",
        "aspect_ratio": "1.8:1",
        "resolution": {"width": 5504, "height": 3072},
        "background_reference_id": "bg_001",
        "background_harmonization_meta": {
            "spatial_staging": {"subject_x": 0.5, "subject_y": 0.65, "focal_length_mm": 24},
            "vision_spatial_prompt": "Two brothers at window wide shot",
        },
        "cost_usd": 0.1545,
        "tokens": 1700,
        "accumulated_cost_usd": 0.2045,
        "accumulated_tokens": 2700,
    }

    app.dependency_overrides[get_generation_service] = lambda: mock_gen_service

    payload = {
        "parent_id": "gen_p1",
        "prompt": "Camera facing the window, zoom out",
        "seed": 999,
        "background_reference_id": "bg_001",
        "spatial_staging": {
            "subject_x": 0.5,
            "subject_y": 0.65,
            "camera_angle": "facing_window",
            "focal_length_mm": 24,
            "zoom_level": "wide",
        },
    }

    res = client.post("/api/refine", json=payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["generation_id"] == "gen_spatial_child"
    assert res_data["background_harmonization_meta"]["spatial_staging"]["focal_length_mm"] == 24
    mock_gen_service.refine_generation.assert_called_once()
