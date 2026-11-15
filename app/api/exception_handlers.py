"""Custom exception handlers for FastAPI translation of domain exceptions."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    DocMorphError,
    FieldNotFoundError,
    InvalidReplacementRequestError,
    PDFCorruptedError,
    PDFEncryptedError,
    PDFNotFoundError,
    PDFValidationError,
    ReplacementCollisionError,
    TextDoesNotFitError,
    UnconfirmedFieldError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Registers domain-specific exception handlers on the FastAPI application."""

    @app.exception_handler(PDFNotFoundError)
    async def pdf_not_found_handler(request: Request, exc: PDFNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "code": "NOT_FOUND"},
        )

    @app.exception_handler(FieldNotFoundError)
    async def field_not_found_handler(request: Request, exc: FieldNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc), "code": "FIELD_NOT_FOUND"},
        )

    @app.exception_handler(UnconfirmedFieldError)
    async def unconfirmed_field_handler(request: Request, exc: UnconfirmedFieldError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc), "code": "UNCONFIRMED_FIELD"},
        )

    @app.exception_handler(PDFValidationError)
    async def pdf_validation_handler(request: Request, exc: PDFValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(PDFCorruptedError)
    async def pdf_corrupted_handler(request: Request, exc: PDFCorruptedError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "code": "CORRUPTED_PDF"},
        )

    @app.exception_handler(PDFEncryptedError)
    async def pdf_encrypted_handler(request: Request, exc: PDFEncryptedError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "code": "ENCRYPTED_PDF"},
        )

    @app.exception_handler(ReplacementCollisionError)
    async def collision_handler(request: Request, exc: ReplacementCollisionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "code": "TEXT_COLLISION"},
        )

    @app.exception_handler(TextDoesNotFitError)
    async def text_does_not_fit_handler(request: Request, exc: TextDoesNotFitError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "code": "TEXT_DOES_NOT_FIT"},
        )

    @app.exception_handler(InvalidReplacementRequestError)
    async def invalid_request_handler(request: Request, exc: InvalidReplacementRequestError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "code": "INVALID_REQUEST"},
        )

    @app.exception_handler(DocMorphError)
    async def docmorph_generic_handler(request: Request, exc: DocMorphError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "code": "DOCMORPH_ERROR"},
        )

