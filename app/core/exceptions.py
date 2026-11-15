"""Custom domain exceptions for the DocMorph PDF engine.

All exceptions provide user-safe error messages that do not expose sensitive
system paths or internal server infrastructure details.
"""

from typing import Any


class DocMorphError(Exception):
    """Base exception for all DocMorph domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    @property
    def user_message(self) -> str:
        """User-safe message suitable for returning in API responses or CLI output."""
        return self.message


class PDFValidationError(DocMorphError):
    """Base exception for PDF validation failures."""


class InvalidFileTypeError(PDFValidationError):
    """Raised when the file extension or file signature does not match PDF format."""


class FileTooLargeError(PDFValidationError):
    """Raised when the file size exceeds the configured maximum limit."""


class EmptyFileError(PDFValidationError):
    """Raised when the uploaded file contains 0 bytes."""


class InvalidPDFError(PDFValidationError):
    """Raised when the PDF structure is corrupted, damaged, or cannot be parsed."""


class EncryptedPDFError(PDFValidationError):
    """Raised when the PDF is password-protected or encrypted."""


class SecurityValidationError(PDFValidationError):
    """Raised when security violations (e.g. path traversal) are detected."""


class PDFNotFoundError(DocMorphError):
    """Raised when a requested PDF document or file is not found."""


# Aliases for consistent naming
PDFCorruptedError = InvalidPDFError
PDFEncryptedError = EncryptedPDFError


class PDFProcessingError(DocMorphError):
    """Raised when an unexpected error occurs during PDF processing or text extraction."""


# --- Phase 3 Personalization & Replacement Exceptions ---

class UnconfirmedFieldError(DocMorphError):
    """Raised when attempting to personalize an unconfirmed or rejected field."""


class InvalidReplacementRequestError(DocMorphError):
    """Raised when replacement parameters, values, or target IDs are invalid."""


class FieldNotFoundError(DocMorphError):
    """Raised when a requested field ID is not found in the document detection results."""


class InvalidBoundingBoxError(DocMorphError):
    """Raised when an occurrence has missing, empty, or inverted coordinates."""


class ReplacementCollisionError(DocMorphError):
    """Raised when replacement text collides with or overlaps an adjacent document element."""


class TextDoesNotFitError(DocMorphError):
    """Raised when replacement text cannot fit into the available space even after scaling."""


class PDFReplacementError(DocMorphError):
    """Raised when text redaction or replacement insertion fails."""


class OutputVerificationError(DocMorphError):
    """Raised when independent verification of the personalized output PDF fails."""

