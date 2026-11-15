"""Personalization, job monitoring, and download routes for Phase 3 integration."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import (
    get_current_user,
    get_det_service,
    get_personalization_service,
)
from app.models.user import User
from app.schemas.api_schemas import (
    JobDetailResponse,
    PersonalizeRequest,
    ResultSummaryResponse,
)
from app.schemas.detection_data import (
    ConfidenceLevel,
    DetectedField,
    DetectionResult,
    FieldType,
    ReviewStatus,
)
from app.schemas.profile_data import ProfileMatchResult, StudentProfile
from app.services.detection_service import DetectionAppService
from app.services.personalization_service import PersonalizationAppService
from app.services.profile_matcher import ProfileMatcher

router = APIRouter(tags=["Personalization"])


@router.post(
    "/documents/{document_id}/personalize",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
)
def personalize_document(
    document_id: str,
    payload: PersonalizeRequest,
    current_user: User = Depends(get_current_user),
    service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Executes the Phase 3 PDF Personalization Engine on confirmed fields.

    Performs vector redaction, typography matching, clearance-based adaptive scaling,
    and post-generation independent verification.
    """
    return service.personalize_document(
        user_id=current_user.id,
        document_id=document_id,
        replacements=payload.replacements,
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Retrieves job processing status, occurrence replacement items, and verification report."""
    return service.get_job_detail(
        user_id=current_user.id,
        job_id=job_id,
    )


@router.get("/documents/{document_id}/result", response_model=JobDetailResponse)
def get_document_latest_result(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Retrieves the latest personalization job and output details for a document."""
    job = service.job_repo.get_latest_by_document(document_id)
    if not job:
        from app.core.exceptions import PDFNotFoundError

        raise PDFNotFoundError(f"No personalization job found for document: {document_id}")
    return service.get_job_detail(user_id=current_user.id, job_id=job.id)


@router.get("/documents/{document_id}/download")
def download_personalized_pdf(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Streams the personalized output PDF as a downloadable attachment.

    Strictly verifies user ownership and authorization.
    """
    pdf_bytes, filename = service.get_personalized_pdf_bytes(
        user_id=current_user.id,
        document_id=document_id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@router.get("/documents/{document_id}/personalized-preview")
def preview_personalized_pdf(
    document_id: str,
    current_user: User = Depends(get_current_user),
    service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Streams the personalized output PDF for in-browser PDF.js preview with authorization."""
    pdf_bytes, filename = service.get_personalized_pdf_bytes(
        user_id=current_user.id,
        document_id=document_id,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
        },
    )


@router.post(
    "/documents/{document_id}/match-profile",
    response_model=ProfileMatchResult,
    status_code=status.HTTP_200_OK,
)
def match_document_profile(
    document_id: str,
    profile: StudentProfile,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
):
    """Compares document detections against a student profile and generates an auto-personalization plan."""
    det_resp = det_service.get_detections(user_id=current_user.id, document_id=document_id)
    return ProfileMatcher.match_profile(det_resp, profile)


@router.post(
    "/documents/{document_id}/auto-personalize",
    response_model=JobDetailResponse,
    status_code=status.HTTP_200_OK,
)
def auto_personalize_document(
    document_id: str,
    profile: StudentProfile,
    current_user: User = Depends(get_current_user),
    det_service: DetectionAppService = Depends(get_det_service),
    pers_service: PersonalizationAppService = Depends(get_personalization_service),
):
    """Automatically confirms eligible fields matching the profile and executes personalization."""
    match_result = match_document_profile(
        document_id=document_id,
        profile=profile,
        current_user=current_user,
        det_service=det_service,
    )
    if not match_result.auto_replacement_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=match_result.summary_message or "No fields eligible for auto-personalization.",
        )
    for item in match_result.auto_replacement_plan:
        det_service.review_field(
            user_id=current_user.id,
            document_id=document_id,
            field_id=item.field_id,
            review_status="confirmed",
        )
    return pers_service.personalize_document(
        user_id=current_user.id,
        document_id=document_id,
        replacements=match_result.auto_replacement_plan,
    )

