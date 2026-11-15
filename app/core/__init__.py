"""Core module containing application configuration and custom exceptions."""

from app.core.config import Settings, settings
from app.core.exceptions import (
    DocMorphError,
    EmptyFileError,
    EncryptedPDFError,
    FieldNotFoundError,
    FileTooLargeError,
    InvalidBoundingBoxError,
    InvalidFileTypeError,
    InvalidPDFError,
    InvalidReplacementRequestError,
    OutputVerificationError,
    PDFCorruptedError,
    PDFEncryptedError,
    PDFNotFoundError,
    PDFProcessingError,
    PDFReplacementError,
    PDFValidationError,
    ReplacementCollisionError,
    SecurityValidationError,
    TextDoesNotFitError,
    UnconfirmedFieldError,
)

__all__ = [
    "DocMorphError",
    "EmptyFileError",
    "EncryptedPDFError",
    "FieldNotFoundError",
    "FileTooLargeError",
    "InvalidBoundingBoxError",
    "InvalidFileTypeError",
    "InvalidPDFError",
    "InvalidReplacementRequestError",
    "OutputVerificationError",
    "PDFProcessingError",
    "PDFReplacementError",
    "PDFValidationError",
    "ReplacementCollisionError",
    "SecurityValidationError",
    "Settings",
    "TextDoesNotFitError",
    "UnconfirmedFieldError",
    "settings",
]

