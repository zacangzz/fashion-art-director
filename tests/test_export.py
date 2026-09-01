import io
import json
import zipfile
from PIL import Image
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import FirestoreManager
from app.services.export_service import ExportService
from app.services.image_generator import ImageGenerator
from app.services.storage_service import StorageService
from app.dependencies import get_db_manager, get_export_service
from fake_firestore import FakeFirestoreClient


@pytest.fixture
def setup_test_db_and_image(tmp_path):
    fake_db = FakeFirestoreClient()
    db = FirestoreManager(fake_db)

    # Create dummy master image file
    img_dir = tmp_path / "generations"
    img_dir.mkdir(parents=True, exist_ok=True)
    master_path = str(img_dir / "gen_test123_master.png")
    
    img = Image.new("RGB", (2000, 2000), color=(100, 150, 200))
    img.save(master_path)

    gen_data = {
        "id": "gen_test123",
        "parent_id": None,
        "moodboard_id": "mb_456",
        "compiled_prompt": "cinematic realism vintage sports car",
        "negative_prompt": "blurry",
        "seed": 42,
        "master_image_path": master_path,
        "aspect_ratio": "1:1",
        "resolution_width": 2000,
        "resolution_height": 2000,
        "accumulated_cost_usd": 0.04,
    }
    db.create_generation(user_id="local_dev_user", gen_data=gen_data)

    return db, gen_data, master_path


def test_export_service_bundle_export_presets(setup_test_db_and_image):
    db, gen_data, master_path = setup_test_db_and_image
    export_service = ExportService(db_manager=db)

    zip_bytes = export_service.bundle_export_presets("gen_test123", user_id="local_dev_user")
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "01_SocialFeed_1080x1350.png" in namelist
        assert "02_StoryMobile_1080x1920.png" in namelist
        assert "03_WideBanner_1440x780.png" in namelist
        assert "04_Square_1440x1440.png" in namelist
        assert "05_LandscapeDisplay_1730x960.png" in namelist
        assert "manifest.json" in namelist

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["generation_id"] == "gen_test123"
        assert manifest["seed"] == 42


def test_export_api_bundle_endpoint(setup_test_db_and_image):
    db, gen_data, master_path = setup_test_db_and_image
    export_service = ExportService(db_manager=db)

    app.dependency_overrides[get_db_manager] = lambda: db
    app.dependency_overrides[get_export_service] = lambda: export_service

    client = TestClient(app)
    response = client.post("/api/export/bundle", json={"generation_id": "gen_test123"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "bundle_gen_test123.zip" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content), "r") as zf:
        assert len(zf.namelist()) == 10  # 1 master + 8 presets + 1 manifest

    app.dependency_overrides.clear()
