import io
import json
import zipfile
from PIL import Image
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import DatabaseManager
from app.services.export_service import ExportService

@pytest.fixture
async def setup_test_db_and_image(tmp_path):
    db_path = str(tmp_path / "test_export.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    # Create dummy master image file
    img_dir = tmp_path / "generations"
    img_dir.mkdir(parents=True, exist_ok=True)
    master_path = str(img_dir / "gen_test123_master.png")
    
    img = Image.new("RGB", (2000, 2000), color=(100, 150, 200))
    img.save(master_path)

    # Insert generation record
    gen_data = {
        "id": "gen_test123",
        "parent_id": None,
        "moodboard_id": "mb_456",
        "prompt": "cinematic realism vintage sports car",
        "negative_prompt": "blurry",
        "seed": 42,
        "tags_snapshot": json.dumps([{"id": "c1", "label": "cinematic"}]),
        "master_image_path": master_path,
        "resolution_width": 2000,
        "resolution_height": 2000,
    }
    await db.create_generation(gen_data)

    return db, gen_data, master_path

@pytest.mark.asyncio
async def test_export_service_create_bundle_zip(setup_test_db_and_image):
    db, gen_data, master_path = setup_test_db_and_image
    export_service = ExportService(db_manager=db)

    zip_bytes = await export_service.create_bundle_zip("gen_test123")
    assert len(zip_bytes) > 0

    # Verify zip content
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "01_SocialFeed_1080x1350.png" in namelist
        assert "02_StoryMobile_1080x1920.png" in namelist
        assert "03_WideBanner_1440x780.png" in namelist
        assert "04_Square_1440x1440.png" in namelist
        assert "05_LandscapeDisplay_1730x960.png" in namelist
        assert "metadata.json" in namelist

        metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
        assert metadata["generation_id"] == "gen_test123"
        assert metadata["prompt"] == gen_data["prompt"]
        assert metadata["seed"] == 42
        assert metadata["resolution"] == {"width": 2000, "height": 2000}

@pytest.mark.asyncio
async def test_export_service_nonexistent_generation(setup_test_db_and_image):
    db, _, _ = setup_test_db_and_image
    export_service = ExportService(db_manager=db)
    
    with pytest.raises((ValueError, FileNotFoundError)):
        await export_service.create_bundle_zip("non_existent_gen_id")

@pytest.mark.asyncio
async def test_export_api_endpoint(tmp_path, monkeypatch):
    # Setup test app with custom test db
    db_path = str(tmp_path / "test_api_export.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    img_dir = tmp_path / "generations"
    img_dir.mkdir(parents=True, exist_ok=True)
    master_path = str(img_dir / "gen_api_test_master.png")
    img = Image.new("RGB", (1000, 1000), color=(0, 255, 0))
    img.save(master_path)

    await db.create_generation({
        "id": "gen_api_test",
        "prompt": "test prompt",
        "negative_prompt": "",
        "seed": 1234,
        "tags_snapshot": "[]",
        "master_image_path": master_path,
        "resolution_width": 1000,
        "resolution_height": 1000,
    })

    # Monkeypatch global db_manager in export module
    from app.api import export
    monkeypatch.setattr(export.export_service, "db_manager", db)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/export/bundle", json={"generation_id": "gen_api_test"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert 'filename="bundle_gen_api_test.zip"' in response.headers["content-disposition"]
        
        # Verify body is valid zip
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        assert "01_SocialFeed_1080x1350.png" in zf.namelist()
        assert "metadata.json" in zf.namelist()

        # Test non-existent ID -> 404
        response_404 = await ac.post("/api/export/bundle", json={"generation_id": "gen_not_found"})
        assert response_404.status_code == 404


@pytest.mark.asyncio
async def test_export_service_inpaint_bundle_with_mask(tmp_path):
    db_path = str(tmp_path / "test_inpaint_export.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    img_dir = tmp_path / "generations"
    img_dir.mkdir(parents=True, exist_ok=True)
    master_path = str(img_dir / "gen_inpaint_555_master.png")
    mask_path = str(img_dir / "gen_inpaint_555_mask.png")

    img = Image.new("RGB", (1080, 1620), color=(50, 100, 150))
    img.save(master_path)
    mask = Image.new("RGB", (1080, 1620), color=(255, 255, 255))
    mask.save(mask_path)

    inpaint_meta = {
        "parent_id": "gen_base_111",
        "prompt": "fix sleeve seam",
        "mask_path": mask_path,
        "mask_url": "/api/images/gen_inpaint_555_mask.png",
        "mask_stats": {"coverage_percentage": 2.5},
    }

    await db.create_generation({
        "id": "gen_inpaint_555",
        "parent_id": "gen_base_111",
        "prompt": "[Inpaint Edit] fix sleeve seam",
        "negative_prompt": "blurry",
        "seed": 999,
        "schema_json": {"inpaint_metadata": inpaint_meta},
        "master_image_path": master_path,
        "aspect_ratio": "2:3",
        "resolution_width": 1080,
        "resolution_height": 1620,
    })

    export_service = ExportService(db_manager=db)
    zip_bytes = await export_service.create_bundle_zip("gen_inpaint_555")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "inpaint_mask.png" in namelist
        assert "metadata.json" in namelist
        metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
        assert "inpaint_metadata" in metadata
        assert metadata["inpaint_metadata"]["mask_stats"]["coverage_percentage"] == 2.5


class MockGenerationService:
    def __init__(self, return_bytes: bytes):
        self.return_bytes = return_bytes
        self.called_with = None

    async def _call_image_model(self, **kwargs):
        self.called_with = kwargs
        return self.return_bytes


@pytest.mark.asyncio
async def test_export_service_prepare_export_master(setup_test_db_and_image, tmp_path):
    db, gen_data, master_path = setup_test_db_and_image

    enhanced_img = Image.new("RGB", (2160, 2160), color=(200, 220, 255))
    buf = io.BytesIO()
    enhanced_img.save(buf, format="PNG")
    mock_bytes = buf.getvalue()

    mock_gen_service = MockGenerationService(mock_bytes)
    export_service = ExportService(
        db_manager=db,
        generation_service=mock_gen_service,
        storage_dir=str(tmp_path),
    )

    res = await export_service.prepare_export_master("gen_test123")
    assert res["parent_id"] == "gen_test123"
    assert res["generation_id"].startswith("gen_export_")
    assert res["master_image_url"].endswith(".png")
    assert res["resolution"]["width"] == 3840
    assert res["resolution"]["height"] == 3840

    # Verify Gemini was invoked with reference image bytes and upscale prompt
    assert mock_gen_service.called_with is not None
    assert "authentic raw photo" in mock_gen_service.called_with["prompt"]
    assert mock_gen_service.called_with["reference_image_bytes"] is not None

    # Verify saved in DB as linked child generation
    child_gen = await db.get_generation(res["generation_id"])
    assert child_gen is not None
    assert child_gen["parent_id"] == "gen_test123"
    schema = child_gen["schema_json"] if isinstance(child_gen["schema_json"], dict) else json.loads(child_gen["schema_json"])
    assert schema["is_export_master"] is True


@pytest.mark.asyncio
async def test_export_api_prepare_endpoint(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_api_prepare_export.db")
    db = DatabaseManager(db_path)
    await db.init_db()

    img_dir = tmp_path / "generations"
    img_dir.mkdir(parents=True, exist_ok=True)
    master_path = str(img_dir / "gen_api_prep_master.png")
    img = Image.new("RGB", (2560, 3840), color=(120, 100, 80))
    img.save(master_path)

    await db.create_generation({
        "id": "gen_api_prep",
        "prompt": "high fashion trench coat",
        "negative_prompt": "",
        "seed": 777,
        "tags_snapshot": "[]",
        "master_image_path": master_path,
        "aspect_ratio": "2:3",
        "resolution_width": 2560,
        "resolution_height": 3840,
    })

    enhanced_img = Image.new("RGB", (2560, 3840), color=(120, 100, 80))
    buf = io.BytesIO()
    enhanced_img.save(buf, format="PNG")
    mock_bytes = buf.getvalue()

    mock_gen_service = MockGenerationService(mock_bytes)
    test_export_service = ExportService(
        db_manager=db,
        generation_service=mock_gen_service,
        storage_dir=str(tmp_path),
    )

    from app.api import export
    monkeypatch.setattr(export, "export_service", test_export_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/export/prepare", json={"generation_id": "gen_api_prep"})
        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == "gen_api_prep"
        assert data["generation_id"].startswith("gen_export_")
        assert data["aspect_ratio"] == "2:3"
        assert data["resolution"] == {"width": 2560, "height": 3840}


