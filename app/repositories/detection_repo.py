"""Detection repository for persisting and querying detected student fields."""

import json
from typing import Optional
from sqlalchemy.orm import Session

from app.models.detection import Detection, DetectionOccurrence
from app.schemas.detection_data import DetectionResult


class DetectionRepository:
    """Encapsulates data access queries for Detections and Occurrences."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_document(self, document_id: str) -> list[Detection]:
        return (
            self.db.query(Detection)
            .filter(Detection.document_id == document_id)
            .order_by(Detection.created_at.asc())
            .all()
        )

    def get_by_field_id(self, document_id: str, field_id: str) -> Optional[Detection]:
        return (
            self.db.query(Detection)
            .filter(Detection.document_id == document_id, Detection.field_id == field_id)
            .first()
        )

    def save_detection_result(
        self, document_id: str, detection_result: DetectionResult
    ) -> list[Detection]:
        """Clears previous detections for document and persists new detection results."""
        # Remove existing detections for fresh analysis
        existing = self.list_by_document(document_id)
        for d in existing:
            self.db.delete(d)
        self.db.flush()

        saved_detections = []
        for field in detection_result.detected_fields:
            det = Detection(
                document_id=document_id,
                field_id=field.field_id,
                field_type=field.field_type.value,
                original_value=field.original_value,
                suggested_value=field.suggested_value,
                corrected_value=(
                    field.suggested_value if field.status.value == "corrected" else None
                ),
                confidence=round(field.confidence, 2),
                review_status=field.status.value,
                is_ambiguous=getattr(field, "is_ambiguous", False) or field.review_required,
                reasons_json=json.dumps(field.confidence_reasons),
            )
            self.db.add(det)
            self.db.flush()

            for occ in field.occurrences:
                val_bbox_dict = occ.value_bbox.model_dump() if occ.value_bbox else {}
                lbl_bbox_dict = occ.label_bbox.model_dump() if occ.label_bbox else {}
                box_dict = occ.bbox.model_dump() if occ.bbox else {}

                occurrence = DetectionOccurrence(
                    detection_id=det.id,
                    page_number=occ.page_number,
                    raw_text=occ.raw_text,
                    bbox_json=json.dumps(box_dict),
                    value_bbox_json=json.dumps(val_bbox_dict),
                    label_bbox_json=json.dumps(lbl_bbox_dict),
                )
                self.db.add(occurrence)

            saved_detections.append(det)

        self.db.commit()
        for d in saved_detections:
            self.db.refresh(d)
        return saved_detections

    def update_field(
        self,
        detection: Detection,
        review_status: str,
        corrected_value: Optional[str] = None,
        field_type: Optional[str] = None,
    ) -> Detection:
        detection.review_status = review_status
        if corrected_value is not None:
            detection.corrected_value = corrected_value
            detection.suggested_value = corrected_value
        if field_type is not None:
            detection.field_type = field_type
        self.db.commit()
        self.db.refresh(detection)
        return detection
