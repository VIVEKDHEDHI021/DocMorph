"""S3 and Cloudflare R2 Remote Storage Provider for DocMorph.

Provides production object storage integration for AWS S3, Cloudflare R2, and MinIO.
Ensures private bucket access, randomized object keys, and local caching for PDF operations.
"""

from pathlib import Path
import re
import tempfile
import uuid

from app.core.config import settings
from app.core.exceptions import PDFValidationError
from app.storage.base import StorageProvider


class S3StorageProvider(StorageProvider):
    """S3/R2 remote object storage provider."""

    def __init__(
        self,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for S3StorageProvider. Install with: pip install boto3"
            ) from exc

        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.S3_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.S3_SECRET_ACCESS_KEY
        self.region = region or settings.S3_REGION

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )
        self.cache_dir = Path(tempfile.gettempdir()) / "docmorph_s3_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_s3_key(self, storage_key: str, subdirectory: str) -> str:
        """Constructs an S3 object key with path sanitization."""
        clean_sub = re.sub(r"[^a-zA-Z0-9_\-]", "", subdirectory)
        safe_name = Path(storage_key).name
        return f"{clean_sub}/{safe_name}"

    def save_file(self, data: bytes, filename: str, subdirectory: str = "uploads") -> str:
        """Uploads binary data to S3 and returns a randomized storage key."""
        safe_stem = re.sub(r"[^\w\-.]", "_", Path(filename).stem)[:50]
        ext = Path(filename).suffix.lower() or ".pdf"
        storage_key = f"{uuid.uuid4().hex}_{safe_stem}{ext}"

        s3_key = self._get_s3_key(storage_key, subdirectory)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=data,
            ContentType="application/pdf",
        )
        return storage_key

    def get_file(self, storage_key: str, subdirectory: str = "uploads") -> bytes:
        """Downloads raw bytes from S3 object."""
        s3_key = self._get_s3_key(storage_key, subdirectory)
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response["Body"].read()
        except Exception as e:
            raise FileNotFoundError(f"S3 object '{s3_key}' not found: {e}") from e

    def get_file_path(self, storage_key: str, subdirectory: str = "uploads") -> Path:
        """Downloads the S3 object to a local temporary cache path for PyMuPDF processing."""
        cached_path = self.cache_dir / f"{subdirectory}_{Path(storage_key).name}"
        if not cached_path.exists():
            data = self.get_file(storage_key, subdirectory)
            cached_path.write_bytes(data)
        return cached_path

    def delete_file(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Deletes an object from S3."""
        s3_key = self._get_s3_key(storage_key, subdirectory)
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            cached_path = self.cache_dir / f"{subdirectory}_{Path(storage_key).name}"
            cached_path.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def file_exists(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Checks if the object exists in S3."""
        s3_key = self._get_s3_key(storage_key, subdirectory)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception:
            return False

