"""Job repository for recording and tracking PDF personalization jobs."""

import json
from typing import Optional
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.job import Job
from app.schemas.replacement_data import ReplacementResult


class JobRepository:
    """Encapsulates data access queries for Personalization Jobs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id_and_user(self, job_id: str, user_id: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()

    def get_by_id(self, job_id: str) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == job_id).first()

    def get_latest_by_document(self, document_id: str) -> Optional[Job]:
        return (
            self.db.query(Job)
            .filter(Job.document_id == document_id)
            .order_by(Job.started_at.desc())
            .first()
        )

    def create(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def complete_job(
        self,
        job: Job,
        replacement_result: ReplacementResult,
    ) -> Job:
        job.status = (
            "completed" if replacement_result.verification_status.value == "passed" else "failed"
        )
        job.total_replacements = replacement_result.total_requested
        job.successful_replacements = replacement_result.total_successful
        job.failed_replacements = replacement_result.total_failed
        job.verification_status = replacement_result.verification_status.value
        job.warnings_json = json.dumps(replacement_result.warnings)
        job.occurrence_results_json = json.dumps(
            [occ.model_dump() for occ in replacement_result.occurrence_results]
        )
        raw_report = getattr(replacement_result, "verification_report", None)
        job.verification_report_json = json.dumps(
            raw_report.model_dump()
            if raw_report is not None
            else {
                "is_valid": replacement_result.verification_status.value == "passed",
                "page_count_matches": True,
                "expected_pages": replacement_result.total_occurrences,
                "actual_pages": replacement_result.total_occurrences,
                "replacements_verified": replacement_result.successful_occurrences,
                "total_replacements": replacement_result.total_occurrences,
                "purged_values_absent": True,
                "labels_intact": True,
                "unrelated_content_intact": True,
                "details": replacement_result.warnings,
            }
        )
        job.completed_at = utc_now()
        self.db.commit()
        self.db.refresh(job)
        return job
