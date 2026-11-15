"""Personalization application service orchestrating Phase 3 replacement and verification."""

import json
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.core.exceptions import (
    FieldNotFoundError,
    PDFNotFoundError,
    UnconfirmedFieldError,
)
from app.models.document import DocumentStatus
from app.models.job import Job
from app.models.personalized_output import PersonalizedOutput
from app.repositories.detection_repo import DetectionRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.repositories.output_repo import PersonalizedOutputRepository
from app.schemas.api_schemas import (
    JobDetailResponse,
    JobOccurrenceResultDTO,
    PersonalizeFieldItem,
    VerificationReportDTO,
)
from app.schemas.detection_data import (
    BoundingBox,
    ConfidenceLevel,
    DetectedField,
    DetectionResult,
    DetectionSummary,
    FieldOccurrence,
    FieldType,
    ReviewStatus,
)
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementRequest,
)
from app.services.pdf_replacer import PDFReplacer
from app.storage.base import StorageProvider


class PersonalizationAppService:
    """Service orchestrating text redaction, adaptive font fitting, and verification."""

    def __init__(
        self,
        db: Session,
        storage: StorageProvider,
        pdf_replacer: Optional[PDFReplacer] = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.doc_repo = DocumentRepository(db)
        self.det_repo = DetectionRepository(db)
        self.job_repo = JobRepository(db)
        self.output_repo = PersonalizedOutputRepository(db)
        self.replacer = pdf_replacer or PDFReplacer()

    def personalize_document(
        self,
        user_id: str,
        document_id: str,
        replacements: list[PersonalizeFieldItem],
    ) -> JobDetailResponse:
        """Validates confirmation, executes PDFReplacer, verifies output, and stores result."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")

        # Step 1: Validate detections and enforce CONFIRMED / CORRECTED status
        db_detections = self.det_repo.list_by_document(document_id)
        det_map = {d.field_id: d for d in db_detections}

        replacement_items: list[ReplacementItem] = []

        for req_item in replacements:
            det = det_map.get(req_item.field_id)
            if not det:
                raise FieldNotFoundError(
                    f"Field '{req_item.field_id}' not found in document detections."
                )

            # Security rule: Never personalize unconfirmed or rejected fields
            if det.review_status not in ("confirmed", "corrected"):
                raise UnconfirmedFieldError(
                    f"Field '{det.field_id}' ({det.field_type}) is unconfirmed (status '{det.review_status}'). "
                    f"Only CONFIRMED or CORRECTED fields can be personalized."
                )

            replacement_items.append(
                ReplacementItem(
                    field_id=det.field_id,
                    field_type=FieldType(det.field_type),
                    original_value=det.original_value,
                    new_value=req_item.new_value,
                    review_status=ReviewStatus(det.review_status),
                )
            )

        # Step 2: Initialize Job record
        job = Job(
            document_id=document_id,
            user_id=user_id,
            status="processing",
            total_replacements=len(replacement_items),
        )
        job = self.job_repo.create(job)
        self.doc_repo.update_status(doc, DocumentStatus.PROCESSING.value)

        try:
            # Step 3: Reconstruct DetectionResult schema from DB models
            reconstructed_fields: list[DetectedField] = []
            for d in db_detections:
                occurrences: list[FieldOccurrence] = []
                for occ in d.occurrences:
                    raw_bbox = json.loads(occ.bbox_json or "{}")
                    raw_val_bbox = json.loads(occ.value_bbox_json or "{}")
                    raw_lbl_bbox = json.loads(occ.label_bbox_json or "{}")

                    occurrences.append(
                        FieldOccurrence(
                            page_number=occ.page_number,
                            bbox=BoundingBox(**raw_bbox) if raw_bbox else BoundingBox(),
                            value_bbox=BoundingBox(**raw_val_bbox) if raw_val_bbox else None,
                            label_bbox=BoundingBox(**raw_lbl_bbox) if raw_lbl_bbox else None,
                            raw_text=occ.raw_text,
                        )
                    )

                reconstructed_fields.append(
                    DetectedField(
                        field_id=d.field_id,
                        field_type=FieldType(d.field_type),
                        original_value=d.original_value,
                        suggested_value=d.suggested_value,
                        confidence=d.confidence,
                        confidence_level=(
                            ConfidenceLevel.HIGH
                            if d.confidence >= 0.90
                            else ConfidenceLevel.MEDIUM
                            if d.confidence >= 0.70
                            else ConfidenceLevel.LOW
                        ),
                        status=ReviewStatus(d.review_status),
                        occurrences=occurrences,
                    )
                )

            detection_result = DetectionResult(
                document_id=document_id,
                filename=doc.original_filename,
                total_pages=doc.page_count,
                detected_fields=reconstructed_fields,
                detection_summary=DetectionSummary(
                    total_fields_detected=len(reconstructed_fields)
                ),
            )

            # Step 4: Execute PDFReplacer with validated source path
            source_path = self.storage.get_file_path(
                doc.source_storage_key, subdirectory="uploads"
            )
            repl_request = ReplacementRequest(
                document_id=document_id,
                source_file=str(source_path),
                replacements=replacement_items,
            )

            repl_result = self.replacer.replace_fields(
                source_pdf=source_path,
                detection_result=detection_result,
                request=repl_request,
            )

            # Step 5: Read generated file and register in private personalized storage
            generated_file = Path(repl_result.output_path)
            output_bytes = generated_file.read_bytes()

            personalized_filename = f"personalized_{doc.original_filename}"
            output_storage_key = self.storage.save_file(
                data=output_bytes,
                filename=personalized_filename,
                subdirectory="personalized",
            )

            # Step 6: Create PersonalizedOutput record
            output_record = PersonalizedOutput(
                document_id=document_id,
                job_id=job.id,
                storage_key=output_storage_key,
                filename=personalized_filename,
                file_size=len(output_bytes),
            )
            self.output_repo.create(output_record)

            # Step 7: Update Job & Document status
            self.job_repo.complete_job(job, repl_result)
            self.doc_repo.update_status(doc, DocumentStatus.COMPLETED.value)

            return self.get_job_detail(user_id, job.id)

        except Exception as exc:
            job.status = "failed"
            job.warnings_json = json.dumps([str(exc)])
            self.db.commit()
            self.doc_repo.update_status(
                doc, DocumentStatus.FAILED.value, error_message=str(exc)
            )
            raise

    def get_job_detail(self, user_id: str, job_id: str) -> JobDetailResponse:
        """Retrieves job detail and formatted verification report."""
        job = self.job_repo.get_by_id_and_user(job_id, user_id)
        if not job:
            raise PDFNotFoundError(f"Job not found or access denied: {job_id}")

        warnings = json.loads(job.warnings_json or "[]")
        raw_occurrences = json.loads(job.occurrence_results_json or "[]")
        raw_verification = json.loads(job.verification_report_json or "{}")

        occurrence_dtos = [
            JobOccurrenceResultDTO(
                page_number=occ.get("page_number", 1),
                field_id=occ.get("field_id", ""),
                status=occ.get("status", "failed"),
                message=occ.get("message", ""),
                warning=occ.get("warning"),
                inserted_value=occ.get("inserted_value", ""),
            )
            for occ in raw_occurrences
        ]

        verification_dto = None
        if raw_verification:
            verification_dto = VerificationReportDTO(
                is_valid=raw_verification.get("is_valid", False),
                page_count_matches=raw_verification.get("page_count_matches", False),
                expected_pages=raw_verification.get("expected_pages", 0),
                actual_pages=raw_verification.get("actual_pages", 0),
                replacements_verified=raw_verification.get("replacements_verified", 0),
                total_replacements=raw_verification.get("total_replacements", 0),
                purged_values_absent=raw_verification.get("purged_values_absent", False),
                labels_intact=raw_verification.get("labels_intact", False),
                unrelated_content_intact=raw_verification.get(
                    "unrelated_content_intact", False
                ),
                details=raw_verification.get("details", []),
            )

        has_output = self.output_repo.get_by_job_id(job_id) is not None

        return JobDetailResponse(
            job_id=job.id,
            document_id=job.document_id,
            status=job.status,
            total_replacements=job.total_replacements,
            successful_replacements=job.successful_replacements,
            failed_replacements=job.failed_replacements,
            verification_status=job.verification_status,
            warnings=warnings,
            occurrence_results=occurrence_dtos,
            verification_report=verification_dto,
            download_available=has_output and job.status == "completed",
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    def get_personalized_pdf_bytes(
        self, user_id: str, document_id: str
    ) -> tuple[bytes, str]:
        """Retrieves personalized output PDF bytes with strict ownership verification."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")

        output = self.output_repo.get_by_document_id(document_id)
        if not output:
            raise PDFNotFoundError(
                f"Personalized output not found for document: {document_id}"
            )

        data = self.storage.get_file(output.storage_key, subdirectory="personalized")
        return data, output.filename
