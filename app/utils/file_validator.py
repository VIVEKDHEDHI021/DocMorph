"""File validation service for DocMorph.

Validates PDF file signatures, extensions, size constraints, encryption status,
and guards against path traversal and corrupted files.
"""

from pathlib import Path
import re
from typing import BinaryIO
import pymupdf

from app.core.config import Settings, settings
from app.core.exceptions import (
    EmptyFileError,
    EncryptedPDFError,
    FileTooLargeError,
    InvalidFileTypeError,
    InvalidPDFError,
    SecurityValidationError,
)

PDF_MAGIC_BYTES = b"%PDF-"
MAX_HEADER_SCAN_BYTES = 1024


class FileValidator:
    """Reusable PDF validation utility for file and in-memory streams."""

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitizes an untrusted filename, stripping directory paths and unsafe characters.

        Args:
            filename: The original untrusted filename.

        Returns:
            Sanitized base filename.

        Raises:
            SecurityValidationError: If dangerous patterns like null bytes or traversal are detected.
            InvalidFileTypeError: If the filename does not have a valid extension.
        """
        if not filename or not filename.strip():
            raise SecurityValidationError("Filename cannot be empty.")

        if "\0" in filename:
            raise SecurityValidationError("Filename contains null byte characters.")

        # Check for explicit directory traversal attempts
        if ".." in filename:
            raise SecurityValidationError("Directory traversal sequence ('..') detected in filename.")

        # Extract only the base name (no path components)
        base_name = Path(filename).name.strip()
        if not base_name:
            raise SecurityValidationError("Filename resolves to an empty name.")

        # Replace characters that are dangerous in file systems or headers
        cleaned = re.sub(r'[^\w\-. ]', '_', base_name)
        return cleaned

    @classmethod
    def validate_filename(
        cls,
        filename: str,
        allowed_extensions: tuple[str, ...] = settings.ALLOWED_EXTENSIONS,
    ) -> str:
        """Validates that a filename has an allowed extension and no path traversal.

        Args:
            filename: Filename to validate.
            allowed_extensions: Tuple of allowed extensions (lowercase).

        Returns:
            The validated and sanitized filename.

        Raises:
            SecurityValidationError: If path traversal or null bytes are present.
            InvalidFileTypeError: If file extension is unsupported.
        """
        sanitized = cls.sanitize_filename(filename)
        suffix = Path(sanitized).suffix.lower()

        if suffix not in [ext.lower() for ext in allowed_extensions]:
            raise InvalidFileTypeError(
                f"Unsupported file extension '{suffix}'. Only {', '.join(allowed_extensions)} files are accepted."
            )

        return sanitized

    @classmethod
    def validate_file_size(
        cls,
        size_bytes: int,
        max_bytes: int = settings.max_file_size_bytes,
    ) -> None:
        """Validates file size against lower (empty) and upper limits.

        Args:
            size_bytes: Size of the file in bytes.
            max_bytes: Maximum allowed file size in bytes.

        Raises:
            EmptyFileError: If file has 0 bytes.
            FileTooLargeError: If file exceeds max_bytes.
        """
        if size_bytes == 0:
            raise EmptyFileError("The uploaded file is empty (0 bytes).")

        if size_bytes > max_bytes:
            max_mb = max_bytes / (1024 * 1024)
            size_mb = size_bytes / (1024 * 1024)
            raise FileTooLargeError(
                f"File size ({size_mb:.2f} MB) exceeds maximum allowed limit of {max_mb:.1f} MB."
            )

    @classmethod
    def validate_pdf_signature(cls, header_bytes: bytes) -> None:
        """Validates that raw bytes start with or contain the PDF magic byte signature.

        According to ISO 32000-1, the %PDF- header must appear within the first 1024 bytes.

        Args:
            header_bytes: Initial bytes of the file (at least 1024 bytes recommended).

        Raises:
            InvalidFileTypeError: If the PDF magic header is missing.
        """
        if not header_bytes:
            raise EmptyFileError("File header is empty.")

        # Strip standard UTF-8 BOM if present
        clean_header = header_bytes
        if clean_header.startswith(b"\xef\xbb\xbf"):
            clean_header = clean_header[3:]

        # PDF header must appear at the beginning or within standard header scan window
        if not clean_header.lstrip().startswith(PDF_MAGIC_BYTES) and PDF_MAGIC_BYTES not in clean_header[:MAX_HEADER_SCAN_BYTES]:
            raise InvalidFileTypeError(
                "The file signature does not match a valid PDF. Expected '%PDF-' magic bytes."
            )

    @classmethod
    def validate_file_path(
        cls,
        file_path: Path | str,
        base_dir: Path | None = None,
        config: Settings = settings,
    ) -> Path:
        """Validates an on-disk file path for existence, security, size, and signature.

        Args:
            file_path: Path to the PDF file.
            base_dir: Optional boundary directory to prevent path traversal outside it.
            config: Configuration settings instance.

        Returns:
            Resolved Path object of the validated file.

        Raises:
            SecurityValidationError: If path traversal is detected.
            InvalidFileTypeError: If file extension or signature is invalid.
            EmptyFileError: If file size is 0.
            FileTooLargeError: If file exceeds maximum size.
            InvalidPDFError: If file cannot be read or does not exist.
        """
        path_str = str(file_path)

        # Check raw string for path traversal if base_dir is enforced or if checking filename
        if "\0" in path_str:
            raise SecurityValidationError("Path contains null bytes.")

        path_obj = Path(file_path)

        if not path_obj.exists():
            raise InvalidPDFError("Specified file does not exist.")

        if not path_obj.is_file():
            raise InvalidPDFError("Specified path is not a regular file.")

        resolved = path_obj.resolve()

        if base_dir is not None:
            resolved_base = base_dir.resolve()
            if not resolved.is_relative_to(resolved_base):
                raise SecurityValidationError("Path traversal detected: file is outside the allowed directory.")

        # Validate extension
        cls.validate_filename(path_obj.name, allowed_extensions=config.ALLOWED_EXTENSIONS)

        # Validate size
        file_size = resolved.stat().st_size
        cls.validate_file_size(file_size, max_bytes=config.max_file_size_bytes)

        # Validate PDF magic bytes signature
        try:
            with open(resolved, "rb") as f:
                header = f.read(MAX_HEADER_SCAN_BYTES)
                cls.validate_pdf_signature(header)
        except (IOError, OSError) as e:
            raise InvalidPDFError("Unable to read file header.") from e

        return resolved

    @classmethod
    def validate_bytes(
        cls,
        data: bytes,
        filename: str = "upload.pdf",
        config: Settings = settings,
    ) -> None:
        """Validates in-memory PDF bytes (useful for web framework uploads).

        Args:
            data: Raw binary PDF data.
            filename: Untrusted filename provided during upload.
            config: Configuration settings instance.

        Raises:
            SecurityValidationError: If filename contains traversal or null bytes.
            InvalidFileTypeError: If extension or signature is invalid.
            EmptyFileError: If data is empty.
            FileTooLargeError: If data exceeds maximum size.
        """
        cls.validate_filename(filename, allowed_extensions=config.ALLOWED_EXTENSIONS)
        cls.validate_file_size(len(data), max_bytes=config.max_file_size_bytes)
        cls.validate_pdf_signature(data[:MAX_HEADER_SCAN_BYTES])

    @classmethod
    def validate_pdf_document(cls, doc: pymupdf.Document) -> None:
        """Validates an opened PyMuPDF Document object for encryption and page integrity.

        Args:
            doc: Opened PyMuPDF Document instance.

        Raises:
            EncryptedPDFError: If document is password-protected or encrypted.
            InvalidPDFError: If document is corrupted or contains no pages.
        """
        if not getattr(doc, "is_pdf", False):
            raise InvalidPDFError("Document is not recognized as a valid PDF.")

        # Check for password-protection or encryption
        if getattr(doc, "is_encrypted", False) or getattr(doc, "needs_pass", 0) > 0:
            raise EncryptedPDFError(
                "The PDF document is password-protected or encrypted and cannot be processed."
            )

        if doc.page_count <= 0:
            raise InvalidPDFError("The PDF document contains no pages.")

