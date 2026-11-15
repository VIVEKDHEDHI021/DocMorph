"""Job model for tracking PDF personalization tasks and verification results."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utc_now


class Job(Base):
    """Represents an execution run of the PDF Personalization & Replacement Engine."""

    __tablename__ = "jobs"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), default="processing", index=True, nullable=False)
    total_replacements: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_replacements: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_replacements: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    occurrence_results_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    verification_report_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="jobs")
    user = relationship("User", back_populates="jobs")
    outputs = relationship("PersonalizedOutput", back_populates="job", cascade="all, delete-orphan")

