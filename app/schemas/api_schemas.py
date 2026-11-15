"""Pydantic schemas for the DocMorph REST API.

Enforces strict typing, input validation, and structured responses across all endpoints.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==============================================================================
# AUTH SCHEMAS
# ==============================================================================


class UserCreate(BaseModel):
    """Payload for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    full_name: Optional[str] = Field(default="", max_length=100)


class UserLogin(BaseModel):
    """Payload for user login."""

    email: str
    password: str


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==============================================================================
# DOCUMENT SCHEMAS
# ==============================================================================


class DocumentUploadResponse(BaseModel):
    """Response returned immediately after file upload and initial validation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    page_count: int
    file_size: int
    status: str
    created_at: datetime


class DocumentListItem(BaseModel):
    """Summary item for document listings in the user dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    page_count: int
    file_size: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document listing response."""

    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentDetailResponse(BaseModel):
    """Detailed document state and associated metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    page_count: int
    file_size: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    detections_count: int = 0
    has_personalized_output: bool = False
    latest_job_id: Optional[str] = None


# ==============================================================================
# DETECTION SCHEMAS
# ==============================================================================


class DetectionOccurrenceDTO(BaseModel):
    """Single physical occurrence on a specific PDF page."""

    page_number: int
    raw_text: str
    bbox: dict[str, Any]
    value_bbox: dict[str, Any]
    label_bbox: dict[str, Any]


class DetectionFieldDTO(BaseModel):
    """Recognized field with review actions and multi-page occurrences."""

    id: str
    field_id: str
    field_type: str
    original_value: str
    suggested_value: str
    corrected_value: Optional[str] = None
    confidence: float
    confidence_level: str
    review_status: str
    is_ambiguous: bool
    reasons: list[str]
    occurrences_count: int
    pages: list[int]
    occurrences: list[DetectionOccurrenceDTO]


class DetectionSummaryDTO(BaseModel):
    """Document-level detection statistics."""

    total_fields: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    review_required: int
    conflicts_count: int


class DocumentDetectionResponse(BaseModel):
    """Full detection response for the review workspace."""

    document_id: str
    status: str
    fields: list[DetectionFieldDTO]
    summary: DetectionSummaryDTO


class DetectionReviewAction(BaseModel):
    """Payload for manual review mutations (confirm, correct, reject, change_type)."""

    review_status: str = Field(..., pattern="^(confirmed|corrected|rejected|pending)$")
    corrected_value: Optional[str] = Field(default=None, max_length=100)
    field_type: Optional[str] = Field(
        default=None,
        pattern="^(student_name|enrollment_number|roll_number|student_id)$",
    )


# ==============================================================================
# PERSONALIZATION SCHEMAS
# ==============================================================================


class PersonalizeFieldItem(BaseModel):
    """Individual replacement specification."""

    field_id: str
    field_type: str = Field(
        ..., pattern="^(student_name|enrollment_number|roll_number|student_id)$"
    )
    new_value: str = Field(..., min_length=1, max_length=100)


class PersonalizeRequest(BaseModel):
    """Payload to trigger personalization on confirmed fields."""

    replacements: list[PersonalizeFieldItem] = Field(..., min_length=1)


class JobOccurrenceResultDTO(BaseModel):
    """Result of an individual occurrence replacement."""

    page_number: int
    field_id: str
    status: str
    message: str
    warning: Optional[str] = None
    inserted_value: str


class VerificationReportDTO(BaseModel):
    """Post-generation independent verification results."""

    is_valid: bool
    page_count_matches: bool
    expected_pages: int
    actual_pages: int
    replacements_verified: int
    total_replacements: int
    purged_values_absent: bool
    labels_intact: bool
    unrelated_content_intact: bool
    details: list[str]


class JobDetailResponse(BaseModel):
    """Personalization job status and verification output."""

    job_id: str
    document_id: str
    status: str
    total_replacements: int
    successful_replacements: int
    failed_replacements: int
    verification_status: str
    warnings: list[str]
    occurrence_results: list[JobOccurrenceResultDTO]
    verification_report: Optional[VerificationReportDTO] = None
    download_available: bool = False
    started_at: datetime
    completed_at: Optional[datetime] = None


class ResultSummaryResponse(BaseModel):
    """Final personalization result summary and download links."""

    document_id: str
    job_id: str
    original_filename: str
    output_filename: str
    total_requested: int
    total_successful: int
    total_failed: int
    verification_status: str
    download_url: str


# ==============================================================================
# ERROR SCHEMAS
# ==============================================================================


class ErrorDetail(BaseModel):
    """Standardized error response payload."""

    detail: str
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

