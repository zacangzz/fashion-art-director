import io
import pytest
from PIL import Image
from app.services.storage_service import StorageService

class FakeBlob:
    def __init__(self, name: str, storage_dict: dict):
        self.name = name
        self.storage_dict = storage_dict
        self.content_type = None

    def exists(self) -> bool:
        return self.name in self.storage_dict

    def upload_from_string(self, data: bytes, content_type: str = "image/png"):
        self.content_type = content_type
        self.storage_dict[self.name] = (data, content_type)

    def download_as_bytes(self) -> bytes:
        if not self.exists():
            raise FileNotFoundError(f"Blob {self.name} not found")
        return self.storage_dict[self.name][0]

    def generate_signed_url(self, version: str = "v4", expiration=None, method: str = "GET") -> str:
        return f"https://storage.googleapis.com/test-bucket/{self.name}?signed=true"

    def delete(self):
        if not self.exists():
            raise FileNotFoundError(f"Blob {self.name} not found")
        del self.storage_dict[self.name]


class FakeBucket:
    def __init__(self, name: str = "test-bucket"):
        self.name = name
        self._blobs = {}

    def blob(self, path: str):
        return FakeBlob(path, self._blobs)


@pytest.fixture
def fake_bucket():
    return FakeBucket()


@pytest.fixture
def storage_service(fake_bucket):
    return StorageService(bucket=fake_bucket, environment="local")


def test_storage_upload_and_download(storage_service):
    user_id = "user_123"
    category = "moodboards"
    filename = "mb_test_0.png"
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024

    path = storage_service.upload_bytes(
        user_id=user_id,
        category=category,
        filename=filename,
        data=data,
        content_type="image/png",
    )
    assert path == "user_123/moodboards/mb_test_0.png"

    downloaded = storage_service.download_bytes(path)
    assert downloaded == data


def test_storage_upload_pil_image(storage_service):
    user_id = "user_456"
    category = "generations"
    filename = "gen_test.png"

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    path = storage_service.upload_pil_image(
        user_id=user_id,
        category=category,
        filename=filename,
        image=img,
        format="PNG",
    )
    assert path == "user_456/generations/gen_test.png"

    downloaded_bytes = storage_service.download_bytes(path)
    downloaded_img = Image.open(io.BytesIO(downloaded_bytes))
    assert downloaded_img.size == (100, 100)
    assert downloaded_img.format == "PNG"


def test_storage_missing_blob_raises_404(storage_service):
    with pytest.raises(FileNotFoundError):
        storage_service.download_bytes("nonexistent/path/image.png")


def test_storage_signed_url_generation(fake_bucket):
    prod_service = StorageService(bucket=fake_bucket, environment="production")
    url = prod_service.get_signed_download_url("user_123/generations/test.png", expiration_minutes=60)
    assert url == "/api/images/user_123/generations/test.png"


def test_storage_delete_file(storage_service):
    user_id = "user_123"
    path = storage_service.upload_bytes(user_id, "test", "file.txt", b"hello", "text/plain")
    assert storage_service.delete_file(path) is True
    assert storage_service.delete_file(path) is False
