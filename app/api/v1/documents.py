"""Document upload, preview, and management routes."""

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
import io

from app.api.dependencies import get_current_user, get_doc_service
from app.models.user import User
from app.schemas.api_schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentAppService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    doc_service: DocumentAppService = Depends(get_doc_service),
):
    """Uploads and validates a source PDF document.

    Enforces file size, extension, magic bytes, and password protection checks.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded.pdf"

    doc = doc_service.upload_document(
        user_id=current_user.id,
        filename=filename,
        file_bytes=file_bytes,
    )
    return DocumentUploadResponse.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    doc_service: DocumentAppService = Depends(get_doc_service),
):
    """Lists uploaded documents belonging to the authenticated user."""
    return doc_service.list_documents(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: str,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentAppService = Depends(get_doc_service),
):
    """Retrieves document detail, status, and related processing identifiers."""
    return doc_service.get_document_detail(
        user_id=current_user.id,
        document_id=document_id,
    )


@router.get("/{document_id}/preview")
def preview_source_pdf(
    document_id: str,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentAppService = Depends(get_doc_service),
):
    """Streams the source PDF bytes for in-browser PDF.js preview with authorization."""
    pdf_bytes, filename = doc_service.get_source_pdf_bytes(
        user_id=current_user.id,
        document_id=document_id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    doc_service: DocumentAppService = Depends(get_doc_service),
):
    """Deletes a document and its associated storage files."""
    doc_service.delete_document(
        user_id=current_user.id,
        document_id=document_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

