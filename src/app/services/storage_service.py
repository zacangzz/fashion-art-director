import io
import mimetypes
from datetime import timedelta
from typing import Optional, Any
from PIL import Image
from app.utils.logger import get_logger

logger = get_logger("storage_service")


class StorageService:
    """
    Unified synchronous Cloud Storage service for uploading, downloading,
    and generating signed edge delivery URLs for all studio media assets.
    """
    def __init__(self, bucket: Any, environment: str = "local"):
        self.bucket = bucket
        self.environment = environment

    def upload_bytes(
        self,
        user_id: str,
        category: str,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        clean_cat = category.strip("/")
        clean_fn = filename.lstrip("/")
        gcs_path = f"{user_id}/{clean_cat}/{clean_fn}"

        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "image/png"

        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(data, content_type=content_type)
        logger.info(f"Uploaded {len(data)} bytes to gs://{getattr(self.bucket, 'name', 'bucket')}/{gcs_path} ({content_type})")
        return gcs_path

    def upload_pil_image(
        self,
        user_id: str,
        category: str,
        filename: str,
        image: Image.Image,
        format: str = "PNG",
        **kwargs,
    ) -> str:
        buf = io.BytesIO()
        image.save(buf, format=format, **kwargs)
        return self.upload_bytes(
            user_id=user_id,
            category=category,
            filename=filename,
            data=buf.getvalue(),
            content_type=f"image/{format.lower()}",
        )

    def download_bytes(self, gcs_path: str) -> bytes:
        blob = self.bucket.blob(gcs_path)
        if not blob.exists():
            raise FileNotFoundError(f"Blob gs://{getattr(self.bucket, 'name', 'bucket')}/{gcs_path} does not exist.")
        return blob.download_as_bytes()

    def get_signed_download_url(self, gcs_path: str, expiration_minutes: int = 60) -> str:
        blob = self.bucket.blob(gcs_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )

    def delete_file(self, gcs_path: str) -> bool:
        blob = self.bucket.blob(gcs_path)
        if blob.exists():
            blob.delete()
            logger.info(f"Deleted gs://{getattr(self.bucket, 'name', 'bucket')}/{gcs_path}")
            return True
        return False
