"""Local Disk Storage Provider for DocMorph.

Stores documents in private local directories with path-traversal prevention.
Ensures zero direct static exposure to clients.
"""

from pathlib import Path
import re
import uuid

from app.core.config import settings
from app.core.exceptions import PDFValidationError
from app.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem implementation of StorageProvider."""

    def __init__(self, base_storage_dir: Path | None = None) -> None:
        self.base_dir = (base_storage_dir or settings.STORAGE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_target_dir(self, subdirectory: str) -> Path:
        """Resolves and validates the target subdirectory within base_dir."""
        # Sanitize subdirectory name
        clean_sub = re.sub(r"[^a-zA-Z0-9_\-]", "", subdirectory)
        target = (self.base_dir / clean_sub).resolve()
        if not target.is_relative_to(self.base_dir):
            raise PDFValidationError(f"Invalid storage path traversal attempt: {subdirectory}")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _resolve_file_path(self, storage_key: str, subdirectory: str) -> Path:
        """Resolves the absolute file path and verifies boundary containment."""
        target_dir = self._get_target_dir(subdirectory)
        # Ensure storage_key contains only safe filename characters
        safe_key = Path(storage_key).name
        file_path = (target_dir / safe_key).resolve()
        if not file_path.is_relative_to(target_dir):
            raise PDFValidationError(f"Invalid storage key path traversal: {storage_key}")
        return file_path

    def save_file(self, data: bytes, filename: str, subdirectory: str = "uploads") -> str:
        """Saves file bytes and returns a unique, randomized storage key."""
        target_dir = self._get_target_dir(subdirectory)

        # Sanitize original filename base
        safe_stem = re.sub(r"[^\w\-.]", "_", Path(filename).stem)[:50]
        ext = Path(filename).suffix.lower()
        if not ext:
            ext = ".pdf"

        storage_key = f"{uuid.uuid4().hex}_{safe_stem}{ext}"
        dest_path = target_dir / storage_key

        dest_path.write_bytes(data)
        return storage_key

    def get_file(self, storage_key: str, subdirectory: str = "uploads") -> bytes:
        """Reads and returns file bytes."""
        file_path = self._resolve_file_path(storage_key, subdirectory)
        if not file_path.is_file():
            raise FileNotFoundError(f"Stored file not found: {storage_key}")
        return file_path.read_bytes()

    def get_file_path(self, storage_key: str, subdirectory: str = "uploads") -> Path:
        """Returns the local path to the file."""
        file_path = self._resolve_file_path(storage_key, subdirectory)
        if not file_path.is_file():
            raise FileNotFoundError(f"Stored file not found: {storage_key}")
        return file_path

    def delete_file(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Deletes a stored file if it exists."""
        try:
            file_path = self._resolve_file_path(storage_key, subdirectory)
            if file_path.is_file():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False

    def file_exists(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Checks if the file exists on disk."""
        try:
            file_path = self._resolve_file_path(storage_key, subdirectory)
            return file_path.is_file()
        except Exception:
            return False

