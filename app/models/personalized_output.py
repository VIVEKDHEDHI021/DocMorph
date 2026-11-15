"""PersonalizedOutput model for tracking generated personalized PDFs."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PersonalizedOutput(Base):
    """Represents a successfully generated and verified personalized PDF file."""

    __tablename__ = "personalized_outputs"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="outputs")
    job = relationship("Job", back_populates="outputs")

