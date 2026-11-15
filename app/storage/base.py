"""Storage Provider Base Protocol for DocMorph.

Defines the interface for storing and retrieving PDF documents.
Decouples application logic from the underlying storage mechanism (Local Disk, Cloudflare R2, S3).
"""

from abc import ABC, abstractmethod
from pathlib import Path


class StorageProvider(ABC):
    """Abstract interface for document file storage."""

    @abstractmethod
    def save_file(self, data: bytes, filename: str, subdirectory: str = "uploads") -> str:
        """Saves file bytes and returns a unique storage key/identifier."""
        pass

    @abstractmethod
    def get_file(self, storage_key: str, subdirectory: str = "uploads") -> bytes:
        """Retrieves raw file bytes by storage key."""
        pass

    @abstractmethod
    def get_file_path(self, storage_key: str, subdirectory: str = "uploads") -> Path:
        """Retrieves the physical or cached local path of the file."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Deletes a file by storage key."""
        pass

    @abstractmethod
    def file_exists(self, storage_key: str, subdirectory: str = "uploads") -> bool:
        """Checks if a file exists in storage."""
        pass

