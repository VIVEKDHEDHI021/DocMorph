"""Personalized output repository."""

from typing import Optional
from sqlalchemy.orm import Session

from app.models.personalized_output import PersonalizedOutput


class PersonalizedOutputRepository:
    """Encapsulates data access queries for PersonalizedOutputs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_document_id(self, document_id: str) -> Optional[PersonalizedOutput]:
        return (
            self.db.query(PersonalizedOutput)
            .filter(PersonalizedOutput.document_id == document_id)
            .order_by(PersonalizedOutput.created_at.desc())
            .first()
        )

    def get_by_job_id(self, job_id: str) -> Optional[PersonalizedOutput]:
        return (
            self.db.query(PersonalizedOutput)
            .filter(PersonalizedOutput.job_id == job_id)
            .first()
        )

    def create(self, output: PersonalizedOutput) -> PersonalizedOutput:
        self.db.add(output)
        self.db.commit()
        self.db.refresh(output)
        return output

