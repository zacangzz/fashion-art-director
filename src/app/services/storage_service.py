import os
import io
import mimetypes
from datetime import timedelta
from typing import Optional, Any
from PIL import Image
from app.utils.logger import get_logger

logger = get_logger("storage_service")


class StorageService:
    """
    Unified Storage abstraction for local filesystem and Google Cloud Storage.
    Encapsulates environment-specific drivers (Local Disk vs GCS) behind a single,
    consistent `{user_id}/{category}/{filename}` path structure.
    """
    def __init__(
        self,
        bucket: Any = None,
        environment: str = "local",
        storage_dir: str = "./storage",
    ):
        self.bucket = bucket
        self.environment = environment
        self.storage_dir = storage_dir
        self.is_local = (self.environment == "local")
        if self.is_local:
            os.makedirs(self.storage_dir, exist_ok=True)

    def _get_storage_path(self, user_id: str, category: str, filename: str) -> str:
        clean_cat = category.strip("/")
        clean_fn = filename.lstrip("/")
        return f"{user_id}/{clean_cat}/{clean_fn}"

    def get_local_file_path(self, relative_path: str) -> str:
        """Returns the absolute or storage_dir-relative local filesystem path."""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(self.storage_dir, relative_path.lstrip("/"))

    def upload_bytes(
        self,
        user_id: str,
        category: str,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        storage_path = self._get_storage_path(user_id, category, filename)

        if not content_type:
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or "image/png"

        if self.is_local:
            # Local Dev: Write directly to ./storage/{user_id}/{category}/{filename}
            local_full_path = self.get_local_file_path(storage_path)
            os.makedirs(os.path.dirname(local_full_path), exist_ok=True)
            with open(local_full_path, "wb") as f:
                f.write(data)
            logger.info(f"Saved {len(data)} bytes to local disk: {local_full_path}")
        else:
            # Hosted GCP: Upload to Cloud Storage bucket blob
            if self.bucket is None:
                raise RuntimeError("Cloud Storage bucket is not configured for hosted environment.")
            blob = self.bucket.blob(storage_path)
            blob.upload_from_string(data, content_type=content_type)
            logger.info(f"Uploaded {len(data)} bytes to gs://{getattr(self.bucket, 'name', 'bucket')}/{storage_path}")

        return storage_path

    def upload_pil_image(
        self,
        user_id: str,
        category: str,
        filename: str,
        image: Image.Image,
        format: str = "PNG",
        **kwargs,
    ) -> str:
        eff_format = format.upper()
        if "icc_profile" not in kwargs:
            try:
                from app.utils.image_utils import get_standard_srgb_profile_bytes
                srgb_bytes = get_standard_srgb_profile_bytes()
                if srgb_bytes:
                    kwargs["icc_profile"] = srgb_bytes
            except Exception:
                pass

        buf = io.BytesIO()
        image.save(buf, format=eff_format, **kwargs)
        return self.upload_bytes(
            user_id=user_id,
            category=category,
            filename=filename,
            data=buf.getvalue(),
            content_type=f"image/{eff_format.lower()}",
        )

    def download_bytes(self, storage_path: str) -> bytes:
        if os.path.isabs(storage_path) and os.path.exists(storage_path):
            with open(storage_path, "rb") as f:
                return f.read()

        if self.is_local:
            local_full_path = self.get_local_file_path(storage_path)
            if not os.path.exists(local_full_path):
                if os.path.exists(storage_path):
                    with open(storage_path, "rb") as f:
                        return f.read()
                raise FileNotFoundError(f"File not found in local storage: {local_full_path}")
            with open(local_full_path, "rb") as f:
                return f.read()
        else:
            if self.bucket is None:
                raise RuntimeError("Cloud Storage bucket is not configured for hosted environment.")
            blob = self.bucket.blob(storage_path)
            if not blob.exists():
                raise FileNotFoundError(f"Blob gs://{getattr(self.bucket, 'name', 'bucket')}/{storage_path} does not exist.")
            return blob.download_as_bytes()

    def get_signed_download_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        """
        Returns the unified delivery URL path for an image.
        In both local and hosted environments, images are served via `/api/images/{storage_path}`.
        """
        clean_path = storage_path.lstrip("/")
        return f"/api/images/{clean_path}"

    def delete_file(self, storage_path: str) -> bool:
        if self.is_local:
            local_full_path = self.get_local_file_path(storage_path)
            if os.path.exists(local_full_path):
                os.remove(local_full_path)
                return True
            return False
        else:
            if self.bucket is None:
                return False
            blob = self.bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
                return True
            return False
