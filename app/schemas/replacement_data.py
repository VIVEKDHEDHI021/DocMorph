"""Pydantic v2 data models for DocMorph Phase 3 PDF Personalization Engine.

Defines schemas for replacement requests, occurrence results, job execution results,
typography analysis, and output verification reports.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.detection_data import BoundingBox, FieldType, ReviewStatus


class ReplacementStatus(str, Enum):
    """Execution status for a single field or occurrence replacement."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


class VerificationStatus(str, Enum):
    """Outcome of independent post-replacement document verification."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReplacementItem(BaseModel):
    """Specification of an individual field replacement."""

    model_config = ConfigDict(frozen=True)

    field_id: str = Field(description="Unique field ID originating from document detection")
    field_type: FieldType = Field(description="Target field type (student_name, etc.)")
    original_value: str = Field(description="Original detected value to be replaced")
    new_value: str = Field(min_length=1, description="New replacement value")
    review_status: ReviewStatus = Field(
        default=ReviewStatus.CONFIRMED,
        description="Must be confirmed or corrected before replacement",
    )


class ReplacementRequest(BaseModel):
    """Client request bundle targeting one or more fields in a document."""

    model_config = ConfigDict(frozen=True)

    document_id: str = Field(description="Unique document ID matching the analysis")
    source_file: str = Field(description="Name or path of the original PDF")
    replacements: list[ReplacementItem] = Field(
        min_length=1, description="List of fields to personalize"
    )
    output_filename: Optional[str] = Field(
        default=None, description="Optional custom name for the output PDF"
    )


class FormattingDetails(BaseModel):
    """Typography and layout properties analyzed from the original text span."""

    model_config = ConfigDict(frozen=True)

    font_name: str = Field(default="helv", description="Mapped base PDF font name")
    original_font: str = Field(default="unknown", description="Original font name from PDF")
    font_size: float = Field(default=9.0, description="Font size in points")
    font_flags: int = Field(default=0, description="Typography flags (bold, italic, etc.)")
    color_rgb: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0), description="Text color as RGB float values (0.0 to 1.0)"
    )
    origin: tuple[float, float] = Field(
        description="Starting coordinate (x, baseline_y) for text insertion"
    )
    bbox: BoundingBox = Field(description="Bounding box of the text to be replaced")
    available_width: float = Field(
        description="Available horizontal width before hitting neighboring elements"
    )


class ReplacementOccurrenceResult(BaseModel):
    """Outcome of replacing a specific physical occurrence on a single page."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1, description="Page number of the occurrence")
    field_id: str = Field(description="Field ID being personalized")
    status: ReplacementStatus = Field(description="Success, failure, or warning state")
    message: str = Field(description="Detailed outcome message")
    warning: Optional[str] = Field(default=None, description="Warning if scaled or constrained")
    original_bbox: Optional[BoundingBox] = Field(
        default=None, description="Coordinates of original text"
    )
    new_bbox: Optional[BoundingBox] = Field(
        default=None, description="Coordinates of newly inserted replacement"
    )
    original_value: str = Field(default="", description="Original text that was removed")
    inserted_value: str = Field(default="", description="New text that was written")


class VerificationReport(BaseModel):
    """Results from independent post-replacement PDF verification."""

    model_config = ConfigDict(frozen=True)

    status: VerificationStatus = Field(description="Passed or failed indicator")
    passed: bool = Field(description="True if all verification checks passed")
    errors: list[str] = Field(default_factory=list, description="Verification failure details")
    warnings: list[str] = Field(default_factory=list, description="Verification warnings")
    checks_performed: int = Field(default=0, description="Total assertions evaluated")


class ReplacementResult(BaseModel):
    """Complete response summarizing document personalization execution."""

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(description="Unique identifier for this personalization job")
    original_filename: str = Field(description="Original PDF filename")
    output_filename: str = Field(description="Name of the newly generated personalized PDF")
    output_path: str = Field(description="Safe storage path of the personalized PDF")
    total_requested: int = Field(ge=0, description="Number of distinct fields requested")
    total_successful: int = Field(ge=0, description="Number of fields successfully updated")
    total_failed: int = Field(ge=0, description="Number of fields that failed replacement")
    total_occurrences: int = Field(
        ge=0, description="Total physical occurrences across all pages"
    )
    successful_occurrences: int = Field(
        ge=0, description="Occurrences successfully replaced"
    )
    failed_occurrences: int = Field(ge=0, description="Occurrences that failed to replace")
    warnings: list[str] = Field(default_factory=list, description="Warnings encountered during run")
    processing_duration_seconds: float = Field(
        ge=0.0, description="Total execution duration in seconds"
    )
    processing_duration_formatted: str = Field(
        description="Formatted execution duration string"
    )
    verification_status: VerificationStatus = Field(
        description="Post-generation verification result"
    )
    occurrence_results: list[ReplacementOccurrenceResult] = Field(
        default_factory=list, description="Granular per-occurrence execution outcomes"
    )

