"""Document application service orchestrating file validation, storage, and persistence."""

from pathlib import Path
from typing import Optional
import pymupdf
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DocMorphError,
    InvalidPDFError,
    PDFNotFoundError,
    PDFValidationError,
)
from app.models.document import Document, DocumentStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.output_repo import PersonalizedOutputRepository
from app.schemas.api_schemas import DocumentDetailResponse, DocumentListItem, DocumentListResponse
from app.storage.base import StorageProvider
from app.utils.file_validator import FileValidator


class DocumentAppService:
    """Service handling document lifecycle operations."""

    def __init__(
        self,
        db: Session,
        storage: StorageProvider,
    ) -> None:
        self.db = db
        self.storage = storage
        self.doc_repo = DocumentRepository(db)
        self.output_repo = PersonalizedOutputRepository(db)

    def upload_document(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> Document:
        """Validates, stores, and registers a new PDF document."""
        # Step 1: Validate file bytes (Magic bytes, extension, size)
        FileValidator.validate_bytes(file_bytes, filename=filename)

        # Step 2: Determine page count and validate PDF structure safely
        try:
            with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
                FileValidator.validate_pdf_document(doc)
                page_count = doc.page_count
        except (PDFValidationError, DocMorphError):
            raise
        except Exception as exc:
            from app.core.exceptions import InvalidPDFError

            raise InvalidPDFError(f"The PDF document is corrupted or damaged: {type(exc).__name__}") from exc

        # Step 3: Save file in private storage
        storage_key = self.storage.save_file(
            data=file_bytes,
            filename=filename,
            subdirectory="uploads",
        )

        # Step 4: Persist Document entity
        doc_entity = Document(
            user_id=user_id,
            original_filename=Path(filename).name,
            source_storage_key=storage_key,
            page_count=page_count,
            file_size=len(file_bytes),
            status=DocumentStatus.UPLOADED.value,
        )
        return self.doc_repo.create(doc_entity)

    def get_document(self, user_id: str, document_id: str) -> Document:
        """Retrieves a document, strictly validating user ownership."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")
        return doc

    def get_document_detail(self, user_id: str, document_id: str) -> DocumentDetailResponse:
        """Retrieves document detail including detection and output indicators."""
        doc = self.get_document(user_id, document_id)
        has_output = self.output_repo.get_by_document_id(document_id) is not None
        latest_job = doc.jobs[-1] if doc.jobs else None

        return DocumentDetailResponse(
            id=doc.id,
            original_filename=doc.original_filename,
            page_count=doc.page_count,
            file_size=doc.file_size,
            status=doc.status,
            error_message=doc.error_message,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            detections_count=len(doc.detections),
            has_personalized_output=has_output,
            latest_job_id=latest_job.id if latest_job else None,
        )

    def list_documents(
        self, user_id: str, page: int = 1, page_size: int = 50
    ) -> DocumentListResponse:
        """Lists user documents with pagination."""
        skip = (page - 1) * page_size
        items, total = self.doc_repo.list_by_user(user_id, skip=skip, limit=page_size)
        dtos = [DocumentListItem.model_validate(item) for item in items]
        return DocumentListResponse(
            items=dtos,
            total=total,
            page=page,
            page_size=page_size,
        )

    def delete_document(self, user_id: str, document_id: str) -> None:
        """Deletes a document and its stored files."""
        doc = self.get_document(user_id, document_id)

        # Delete source storage file
        if doc.source_storage_key:
            self.storage.delete_file(doc.source_storage_key, subdirectory="uploads")

        # Delete any personalized output files
        for output in doc.outputs:
            if output.storage_key:
                self.storage.delete_file(output.storage_key, subdirectory="personalized")

        self.doc_repo.delete(doc)

    def get_source_pdf_bytes(self, user_id: str, document_id: str) -> tuple[bytes, str]:
        """Returns raw bytes and original filename for authenticated PDF.js preview."""
        doc = self.get_document(user_id, document_id)
        data = self.storage.get_file(doc.source_storage_key, subdirectory="uploads")
        return data, doc.original_filename
