"""Detection and manual review routes for Phase 2 integration."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_det_service
from app.models.user import User
from app.schemas.api_schemas import (
    DetectionFieldDTO,
    DetectionReviewAction,
    DocumentDetectionResponse,
)
from app.services.detection_service import DetectionAppService

router = APIRouter(prefix="/documents", tags=["Detections"])


@router.post("/{document_id}/analyze", response_model=DocumentDetectionResponse)
def trigger_detection(
    document_id: str,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Executes the Phase 2 DetectionEngine on the document and persists field detections."""
    return det_service.analyze_document(
        user_id=current_user.id,
        document_id=document_id,
    )


@router.get("/{document_id}/detection", response_model=DocumentDetectionResponse)
def get_detections(
    document_id: str,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Retrieves detected student fields, multi-page occurrences, and confidence reasons."""
    return det_service.get_detections(
        user_id=current_user.id,
        document_id=document_id,
    )


@router.patch(
    "/{document_id}/detections/{field_id}",
    response_model=DetectionFieldDTO,
)
def review_field(
    document_id: str,
    field_id: str,
    action: DetectionReviewAction,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Updates review decision: confirm, correct value, reject, or change field type."""
    return det_service.review_field(
        user_id=current_user.id,
        document_id=document_id,
        field_id=field_id,
        review_status=action.review_status,
        corrected_value=action.corrected_value,
        field_type=action.field_type,
    )


@router.post(
    "/{document_id}/detections/{field_id}/confirm",
    response_model=DetectionFieldDTO,
)
def confirm_field(
    document_id: str,
    field_id: str,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Convenience endpoint to confirm a detected field."""
    return det_service.review_field(
        user_id=current_user.id,
        document_id=document_id,
        field_id=field_id,
        review_status="confirmed",
    )


@router.post(
    "/{document_id}/detections/{field_id}/reject",
    response_model=DetectionFieldDTO,
)
def reject_field(
    document_id: str,
    field_id: str,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Convenience endpoint to reject a detected field."""
    return det_service.review_field(
        user_id=current_user.id,
        document_id=document_id,
        field_id=field_id,
        review_status="rejected",
    )

