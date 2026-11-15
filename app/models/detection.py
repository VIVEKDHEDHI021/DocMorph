"""Detection and Occurrence models for persisted field recognition and manual review."""

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Detection(Base):
    """Represents a recognized student credential field associated with a document."""

    __tablename__ = "detections"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    field_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_value: Mapped[str] = mapped_column(String(255), nullable=False)
    suggested_value: Mapped[str] = mapped_column(String(255), nullable=False)
    corrected_value: Mapped[str] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    is_ambiguous: Mapped[bool] = mapped_column(default=False, nullable=False)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    # Relationships
    document = relationship("Document", back_populates="detections")
    occurrences = relationship("DetectionOccurrence", back_populates="detection", cascade="all, delete-orphan")


class DetectionOccurrence(Base):
    """Represents a physical coordinate occurrence of a detected field on a specific page."""

    __tablename__ = "detection_occurrences"

    detection_id: Mapped[str] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    bbox_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    value_bbox_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    label_bbox_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    # Relationships
    detection = relationship("Detection", back_populates="occurrences")

