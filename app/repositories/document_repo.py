"""Document repository for database operations on Document entities."""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    """Encapsulates data access queries for Documents."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_and_user(self, document_id: str, user_id: str) -> Optional[Document]:
        """Retrieves a document strictly verifying user ownership."""
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.user_id == user_id)
            .first()
        )

    def get_by_id(self, document_id: str) -> Optional[Document]:
        """Retrieves a document by id (for internal/admin access)."""
        return self.db.query(Document).filter(Document.id == document_id).first()

    def list_by_user(
        self, user_id: str, skip: int = 0, limit: int = 50
    ) -> tuple[list[Document], int]:
        """Lists user documents with pagination ordered by latest creation."""
        query = self.db.query(Document).filter(Document.user_id == user_id)
        total = query.count()
        items = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_status(
        self, document: Document, status: str, error_message: Optional[str] = None
    ) -> Document:
        document.status = status
        if error_message is not None:
            document.error_message = error_message
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.commit()

