"""Pydantic schemas for the DocMorph One-Time Student Profile and Auto-Matching System.

Defines schemas for local student profiles, profile match comparisons,
auto-personalization plans, and execution statuses.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api_schemas import PersonalizeFieldItem


class ProfileMatchStatus(str, Enum):
    """Status indicating how a detected document field compares to the saved profile."""

    ALREADY_MATCHING = "already_matching"
    DIFFERENT = "different"
    NOT_DETECTED = "not_detected"
    UNCERTAIN = "uncertain"
    CONFLICTING = "conflicting"
    OPTIONAL_FIELD_EMPTY = "optional_field_empty"


class StudentProfile(BaseModel):
    """User profile stored on client and passed for automatic matching."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str = Field(..., min_length=1, description="Student's full legal name")
    enrollment_number: str = Field(..., min_length=1, description="Student's university enrollment number")
    roll_number: Optional[str] = Field(None, description="Optional class roll number")
    student_id: Optional[str] = Field(None, description="Optional secondary student ID")
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class FieldMatchComparison(BaseModel):
    """Comparison evaluation between a detected document field and profile value."""

    model_config = ConfigDict(from_attributes=True)

    field_type: str = Field(..., description="Target field type (student_name, enrollment_number, etc.)")
    detected_value: Optional[str] = Field(None, description="Original value detected on PDF")
    profile_value: Optional[str] = Field(None, description="Target value from student profile")
    status: ProfileMatchStatus = Field(..., description="Evaluation outcome")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence of detection")
    field_id: Optional[str] = Field(None, description="Backend detection field identifier if found")
    auto_action_eligible: bool = Field(False, description="True if field can be automatically replaced")
    reason: str = Field("", description="Explainable reason for status and decision")


class ProfileMatchResult(BaseModel):
    """Overall outcome of comparing a document's detected credentials against the student profile."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    comparisons: dict[str, FieldMatchComparison] = Field(
        default_factory=dict,
        description="Keyed by field_type (student_name, enrollment_number, roll_number, student_id)",
    )
    all_eligible_for_auto: bool = Field(
        False,
        description="True if all detected fields can be safely and automatically replaced without manual review",
    )
    has_conflicts: bool = Field(
        False,
        description="True if any cross-page conflict was detected",
    )
    requires_manual_review: bool = Field(
        False,
        description="True if manual review mode is recommended",
    )
    auto_replacement_plan: list[PersonalizeFieldItem] = Field(
        default_factory=list,
        description="List of replacement items ready to be executed",
    )
    summary_message: str = Field(
        "",
        description="Summary of the matching analysis",
    )

