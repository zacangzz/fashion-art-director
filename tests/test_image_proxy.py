import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.dependencies import get_storage_service
from app.services.storage_service import StorageService


def test_image_proxy_redirect_to_signed_url():
    fake_bucket = MagicMock()
    fake_blob = MagicMock()
    signed_url = "https://storage.googleapis.com/test-bucket/local_dev_user/generations/test_img.png?signature=xyz"
    fake_blob.generate_signed_url.return_value = signed_url
    fake_bucket.blob.return_value = fake_blob
    storage_service = StorageService(bucket=fake_bucket, environment="local")

    app.dependency_overrides[get_storage_service] = lambda: storage_service
    client = TestClient(app)

    # Disable auto following redirects to assert 307 status code and Location header
    res = client.get("/api/images/local_dev_user/generations/test_img.png", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["Location"] == signed_url

    app.dependency_overrides.clear()
