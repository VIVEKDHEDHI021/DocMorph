"""Detection application service orchestrating Phase 2 detection and manual review."""

import json
from typing import Optional
from sqlalchemy.orm import Session

from app.core.exceptions import FieldNotFoundError, PDFNotFoundError
from app.models.document import DocumentStatus
from app.repositories.detection_repo import DetectionRepository
from app.repositories.document_repo import DocumentRepository
from app.schemas.api_schemas import (
    DetectionFieldDTO,
    DetectionOccurrenceDTO,
    DetectionSummaryDTO,
    DocumentDetectionResponse,
)
from app.services.detection_engine import DetectionEngine
from app.storage.base import StorageProvider


class DetectionAppService:
    """Service handling field recognition, confidence scoring, and review mutations."""

    def __init__(
        self,
        db: Session,
        storage: StorageProvider,
        detection_engine: Optional[DetectionEngine] = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.doc_repo = DocumentRepository(db)
        self.det_repo = DetectionRepository(db)
        self.engine = detection_engine or DetectionEngine()

    def analyze_document(self, user_id: str, document_id: str) -> DocumentDetectionResponse:
        """Loads source PDF, runs Phase 2 DetectionEngine, and persists results."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")

        self.doc_repo.update_status(doc, DocumentStatus.ANALYZING.value)

        try:
            # Load PDF bytes from private storage
            pdf_bytes = self.storage.get_file(doc.source_storage_key, subdirectory="uploads")

            # Run intelligent detection engine
            detection_res = self.engine.detect_bytes(
                data=pdf_bytes,
                filename=doc.original_filename,
            )

            # Persist detected fields & occurrences to database
            self.det_repo.save_detection_result(document_id, detection_res)

            # Update document status to AWAITING_REVIEW
            self.doc_repo.update_status(doc, DocumentStatus.AWAITING_REVIEW.value)

            return self.get_detections(user_id, document_id)

        except Exception as exc:
            self.doc_repo.update_status(
                doc, DocumentStatus.FAILED.value, error_message=str(exc)
            )
            raise

    def get_detections(self, user_id: str, document_id: str) -> DocumentDetectionResponse:
        """Retrieves persisted detections and formats the review response."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")

        detections = self.det_repo.list_by_document(document_id)

        field_dtos: list[DetectionFieldDTO] = []
        high_cnt = 0
        med_cnt = 0
        low_cnt = 0
        review_cnt = 0

        for d in detections:
            conf = d.confidence
            if conf >= 0.90:
                conf_level = "high"
                high_cnt += 1
            elif conf >= 0.70:
                conf_level = "medium"
                med_cnt += 1
            else:
                conf_level = "low"
                low_cnt += 1

            if d.review_status in ("pending", "rejected") or d.is_ambiguous:
                review_cnt += 1

            occ_dtos: list[DetectionOccurrenceDTO] = []
            pages = []
            for occ in d.occurrences:
                pages.append(occ.page_number)
                occ_dtos.append(
                    DetectionOccurrenceDTO(
                        page_number=occ.page_number,
                        raw_text=occ.raw_text,
                        bbox=json.loads(occ.bbox_json or "{}"),
                        value_bbox=json.loads(occ.value_bbox_json or "{}"),
                        label_bbox=json.loads(occ.label_bbox_json or "{}"),
                    )
                )

            reasons = json.loads(d.reasons_json or "[]")

            field_dtos.append(
                DetectionFieldDTO(
                    id=d.id,
                    field_id=d.field_id,
                    field_type=d.field_type,
                    original_value=d.original_value,
                    suggested_value=d.suggested_value,
                    corrected_value=d.corrected_value,
                    confidence=d.confidence,
                    confidence_level=conf_level,
                    review_status=d.review_status,
                    is_ambiguous=d.is_ambiguous,
                    reasons=reasons,
                    occurrences_count=len(occ_dtos),
                    pages=sorted(list(set(pages))),
                    occurrences=occ_dtos,
                )
            )

        summary = DetectionSummaryDTO(
            total_fields=len(field_dtos),
            high_confidence=high_cnt,
            medium_confidence=med_cnt,
            low_confidence=low_cnt,
            review_required=review_cnt,
            conflicts_count=0,
        )

        return DocumentDetectionResponse(
            document_id=document_id,
            status=doc.status,
            fields=field_dtos,
            summary=summary,
        )

    def review_field(
        self,
        user_id: str,
        document_id: str,
        field_id: str,
        review_status: str,
        corrected_value: Optional[str] = None,
        field_type: Optional[str] = None,
    ) -> DetectionFieldDTO:
        """Applies manual review decisions (confirm, correct, reject, change_type)."""
        doc = self.doc_repo.get_by_id_and_user(document_id, user_id)
        if not doc:
            raise PDFNotFoundError(f"Document not found or access denied: {document_id}")

        detection = self.det_repo.get_by_field_id(document_id, field_id)
        if not detection:
            raise FieldNotFoundError(f"Field '{field_id}' not found in document: {document_id}")

        self.det_repo.update_field(
            detection=detection,
            review_status=review_status,
            corrected_value=corrected_value,
            field_type=field_type,
        )

        # Refresh and return single field DTO
        res = self.get_detections(user_id, document_id)
        for f in res.fields:
            if f.field_id == field_id:
                return f
        raise FieldNotFoundError(f"Field '{field_id}' error after update")
