"""Document model for tracking uploaded PDFs and processing states."""

from enum import Enum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DocumentStatus(str, Enum):
    """Document lifecycle processing states."""

    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    AWAITING_REVIEW = "awaiting_review"
    READY_TO_PERSONALIZE = "ready_to_personalize"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    """Represents an uploaded source PDF document and its lifecycle."""

    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=DocumentStatus.UPLOADED.value, index=True, nullable=False)
    error_message: Mapped[str] = mapped_column(String(500), nullable=True)

    # Relationships
    user = relationship("User", back_populates="documents")
    detections = relationship("Detection", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")
    outputs = relationship("PersonalizedOutput", back_populates="document", cascade="all, delete-orphan")

