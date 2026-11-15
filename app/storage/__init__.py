"""Storage package exports for DocMorph."""

from app.core.config import settings
from app.storage.base import StorageProvider
from app.storage.cleanup import cleanup_storage_cache
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider

_storage_instance: StorageProvider | None = None


def get_storage() -> StorageProvider:
    """Returns the configured global storage provider instance (local or S3)."""
    global _storage_instance
    if _storage_instance is None:
        if settings.STORAGE_BACKEND.lower() == "s3":
            _storage_instance = S3StorageProvider()
        else:
            _storage_instance = LocalStorageProvider()
    return _storage_instance


__all__ = [
    "StorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "get_storage",
    "cleanup_storage_cache",
]
