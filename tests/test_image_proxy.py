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


def test_image_proxy_serves_cloud_storage_in_production(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.exists.return_value = True
    fake_blob.download_as_bytes.return_value = b"\x89PNG\r\n\x1a\nfake_cloud_png"
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="production", storage_dir="/tmp/nonexistent")

    app.dependency_overrides[get_storage_service] = lambda: storage_service
    client = TestClient(app)

    # In production, serves bytes directly from Cloud Storage
    res = client.get("/api/images/prod_user/generations/cloud_img.png")
    assert res.status_code == 200
    assert res.content == b"\x89PNG\r\n\x1a\nfake_cloud_png"
    assert res.headers["content-type"] == "image/png"
    assert "public, max-age=" in res.headers.get("cache-control", "")

    app.dependency_overrides.clear()


def test_image_proxy_returns_404_when_cloud_blob_not_found(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    fake_blob.exists.return_value = False
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="production", storage_dir="/tmp/nonexistent")

    app.dependency_overrides[get_storage_service] = lambda: storage_service
    client = TestClient(app)

    res = client.get("/api/images/prod_user/generations/missing.png")
    assert res.status_code == 404
    assert "Image not found on cloud storage" in res.json()["detail"]

    app.dependency_overrides.clear()
