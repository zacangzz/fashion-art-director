import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.dependencies import get_storage_service
from app.services.storage_service import StorageService
from app.config import get_settings


def test_image_proxy_serves_local_file(tmp_path):
    storage_dir = str(tmp_path)
    test_gen_dir = os.path.join(storage_dir, "local_dev_user", "generations")
    os.makedirs(test_gen_dir, exist_ok=True)
    img_file = os.path.join(test_gen_dir, "test_img.png")
    with open(img_file, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\nfake_png_data")

    storage_service = StorageService(bucket=None, environment="local", storage_dir=storage_dir)

    app.dependency_overrides[get_storage_service] = lambda: storage_service
    client = TestClient(app)

    res = client.get("/api/images/local_dev_user/generations/test_img.png")
    assert res.status_code == 200
    assert res.content == b"\x89PNG\r\n\x1a\nfake_png_data"
    assert res.headers["content-type"] == "image/png"

    app.dependency_overrides.clear()


def test_image_proxy_redirect_to_signed_url_in_production(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    signed_url = "https://storage.googleapis.com/test-bucket/prod_user/generations/cloud_img.png?signature=xyz"
    fake_blob.generate_signed_url.return_value = signed_url
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="production", storage_dir="/tmp/nonexistent")

    app.dependency_overrides[get_storage_service] = lambda: storage_service
    client = TestClient(app)

    # In production, when file is not on local disk, it redirects with 307 to signed GCS URL
    res = client.get("/api/images/prod_user/generations/cloud_img.png", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["Location"] == signed_url

    app.dependency_overrides.clear()
