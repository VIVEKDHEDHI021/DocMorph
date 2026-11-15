"""Pydantic v2 data models for DocMorph Phase 2 Intelligent Detection Engine.

Provides schemas for bounding boxes, text spans, occurrences, student fields,
conflicts, manual review workflows, and complete detection responses.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldType(str, Enum):
    """Supported student field types for footer recognition."""

    STUDENT_NAME = "student_name"
    ENROLLMENT_NUMBER = "enrollment_number"
    ROLL_NUMBER = "roll_number"
    STUDENT_ID = "student_id"
    UNKNOWN_IDENTIFIER = "unknown_identifier"


class ConfidenceLevel(str, Enum):
    """Categorized confidence tiers for field detections."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewStatus(str, Enum):
    """Lifecycle status for human-in-the-loop manual review."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class BoundingBox(BaseModel):
    """Geometric rectangle in PDF user space coordinates (points)."""

    model_config = ConfigDict(frozen=True)

    x0: float = Field(description="Left coordinate")
    y0: float = Field(description="Top coordinate")
    x1: float = Field(description="Right coordinate")
    y1: float = Field(description="Bottom coordinate")

    @property
    def width(self) -> float:
        """Width of the bounding box."""
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        """Height of the bounding box."""
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        """Surface area of the bounding box."""
        return self.width * self.height

    @property
    def is_empty(self) -> bool:
        """True if width or height is zero or negative."""
        return self.x1 <= self.x0 or self.y1 <= self.y0

    def contains_point(self, x: float, y: float) -> bool:
        """Checks if a point (x, y) falls inside this rectangle."""
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def intersects(self, other: "BoundingBox") -> bool:
        """Checks if this rectangle overlaps with another rectangle."""
        return not (
            self.x1 < other.x0
            or self.x0 > other.x1
            or self.y1 < other.y0
            or self.y0 > other.y1
        )

    def union(self, other: "BoundingBox") -> "BoundingBox":
        """Returns the minimal bounding box containing both rectangles."""
        return BoundingBox(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )

    def to_tuple(self) -> tuple[float, float, float, float]:
        """Returns coordinates as an (x0, y0, x1, y1) tuple."""
        return (self.x0, self.y0, self.x1, self.y1)

    @classmethod
    def from_tuple(cls, coords: tuple[float, float, float, float]) -> "BoundingBox":
        """Creates a BoundingBox from an (x0, y0, x1, y1) tuple."""
        return cls(
            x0=round(coords[0], 2),
            y0=round(coords[1], 2),
            x1=round(coords[2], 2),
            y1=round(coords[3], 2),
        )


class SpanInformation(BaseModel):
    """Detailed typography and coordinate data for an individual text span."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(description="Span text content")
    bbox: BoundingBox = Field(description="Bounding box of the text span")
    font: str = Field(default="unknown", description="Font name/family")
    size: float = Field(default=0.0, description="Font size in points")
    color: int = Field(default=0, description="RGB integer color encoding")
    flags: int = Field(default=0, description="Font styling flags (bold, italic, etc.)")


class FieldOccurrence(BaseModel):
    """A single spatial occurrence of a student field on a specific page."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1, description="1-indexed page number")
    bbox: BoundingBox = Field(description="Overall bounding box of the occurrence")
    value_bbox: Optional[BoundingBox] = Field(
        default=None, description="Exact bounding box isolating the field value"
    )
    label_bbox: Optional[BoundingBox] = Field(
        default=None, description="Exact bounding box isolating the field label"
    )
    block_number: int = Field(default=0, description="PyMuPDF block index on the page")
    line_number: int = Field(default=0, description="Line index within the block")
    span_information: list[SpanInformation] = Field(
        default_factory=list, description="Constituent text spans"
    )
    raw_text: str = Field(default="", description="Complete line or text segment")
    matched_label: str = Field(default="", description="Recognized label substring")
    is_in_footer_region: bool = Field(
        default=True, description="Whether occurrence is within the geometric footer zone"
    )
    line_bbox: Optional[BoundingBox] = Field(
        default=None, description="Full line bounding box for paired/unlabelled footers"
    )
    pair_id: Optional[str] = Field(
        default=None, description="Identifier linking paired name & enrollment fields"
    )


class DetectedField(BaseModel):
    """A detected student field, grouping all occurrences across pages."""

    model_config = ConfigDict(frozen=False)

    field_id: str = Field(description="Unique, stable identifier for this detected field")
    field_type: FieldType = Field(description="Target student field type")
    original_value: str = Field(description="Original unedited detected value from document")
    suggested_value: str = Field(description="Normalized or manually corrected field value")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    confidence_level: ConfidenceLevel = Field(description="High / Medium / Low confidence tier")
    detection_method: str = Field(
        default="hybrid_rules_regex", description="Strategy used to identify this field"
    )
    review_required: bool = Field(
        default=False, description="True if manual human verification is recommended"
    )
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING, description="Manual review workflow state"
    )
    confidence_reasons: list[str] = Field(
        default_factory=list, description="Explainable reasons supporting the confidence score"
    )
    occurrences: list[FieldOccurrence] = Field(
        default_factory=list, description="All spatial occurrences of this field across pages"
    )

    def confirm(self) -> "DetectedField":
        """Marks the detection as confirmed by user."""
        self.status = ReviewStatus.CONFIRMED
        self.review_required = False
        return self

    def correct(self, new_value: str, new_field_type: Optional[FieldType] = None) -> "DetectedField":
        """Applies manual correction while strictly preserving original_value."""
        self.suggested_value = new_value.strip()
        if new_field_type is not None:
            self.field_type = new_field_type
        self.status = ReviewStatus.CORRECTED
        self.review_required = False
        return self

    def reject(self) -> "DetectedField":
        """Rejects the detection as a false positive."""
        self.status = ReviewStatus.REJECTED
        self.review_required = False
        return self

    def change_type(self, new_field_type: FieldType) -> "DetectedField":
        """Changes the field type under manual review."""
        self.field_type = new_field_type
        self.status = ReviewStatus.CORRECTED
        self.review_required = False
        return self

    def mark_review(self, required: bool = True) -> "DetectedField":
        """Explicitly toggles review requirement flag."""
        self.review_required = required
        return self


class FieldConflict(BaseModel):
    """Represents conflicting or contradictory values detected for the same field type."""

    model_config = ConfigDict(frozen=True)

    conflict_id: str = Field(description="Unique conflict identifier")
    field_type: FieldType = Field(description="Field type exhibiting conflicting values")
    field_ids: list[str] = Field(description="List of conflicting field IDs")
    conflicting_values: list[str] = Field(description="Distinct values observed across pages")
    pages: list[int] = Field(description="Pages involved in the conflict")
    description: str = Field(description="Human-readable description of the discrepancy")


class DetectionSummary(BaseModel):
    """Aggregate statistics on detected fields, confidence tiers, and conflicts."""

    model_config = ConfigDict(frozen=True)

    total_fields_detected: int = Field(default=0, description="Total unique detected fields")
    high_confidence_count: int = Field(default=0, description="Count of high confidence detections")
    medium_confidence_count: int = Field(default=0, description="Count of medium confidence detections")
    low_confidence_count: int = Field(default=0, description="Count of low confidence detections")
    review_required_count: int = Field(default=0, description="Count of fields requiring review")
    conflicts_count: int = Field(default=0, description="Number of detected conflicts")
    fields_by_type: dict[str, int] = Field(
        default_factory=dict, description="Count of detections per field type"
    )


class DetectionResult(BaseModel):
    """Complete structured response from the Intelligent Detection Engine."""

    model_config = ConfigDict(frozen=False)

    document_id: str = Field(description="Unique identifier for the analyzed document")
    filename: str = Field(description="Sanitized name of the PDF file")
    total_pages: int = Field(ge=0, description="Total number of pages inspected")
    detected_fields: list[DetectedField] = Field(
        default_factory=list, description="List of recognized student fields"
    )
    conflicts: list[FieldConflict] = Field(
        default_factory=list, description="Contradictions or value discrepancies across pages"
    )
    detection_summary: DetectionSummary = Field(
        description="Summary statistics of the detection results"
    )

    def get_field(self, field_id: str) -> Optional[DetectedField]:
        """Retrieves a detected field by its field_id."""
        for field in self.detected_fields:
            if field.field_id == field_id:
                return field
        return None

    def confirm_field(self, field_id: str) -> "DetectionResult":
        """Confirms a detected field by its field_id."""
        field = self.get_field(field_id)
        if field:
            field.confirm()
            self._recalculate_summary()
        return self

    def correct_field(
        self,
        field_id: str,
        new_value: str,
        new_field_type: Optional[FieldType] = None,
    ) -> "DetectionResult":
        """Corrects a detected field while preserving original_value."""
        field = self.get_field(field_id)
        if field:
            field.correct(new_value=new_value, new_field_type=new_field_type)
            self._recalculate_summary()
        return self

    def reject_field(self, field_id: str) -> "DetectionResult":
        """Rejects a detected field by its field_id."""
        field = self.get_field(field_id)
        if field:
            field.reject()
            self._recalculate_summary()
        return self

    def change_field_type(self, field_id: str, new_field_type: FieldType) -> "DetectionResult":
        """Changes the field type of a detected field."""
        field = self.get_field(field_id)
        if field:
            field.change_type(new_field_type)
            self._recalculate_summary()
        return self

    def mark_review_required(self, field_id: str, required: bool = True) -> "DetectionResult":
        """Toggles the review_required flag on a detected field."""
        field = self.get_field(field_id)
        if field:
            field.mark_review(required)
            self._recalculate_summary()
        return self

    def _recalculate_summary(self) -> None:
        """Internal helper to refresh summary counts after manual review updates."""
        # Active fields: exclude rejected fields from active statistics
        active_fields = [f for f in self.detected_fields if f.status != ReviewStatus.REJECTED]
        high = sum(1 for f in active_fields if f.confidence_level == ConfidenceLevel.HIGH)
        med = sum(1 for f in active_fields if f.confidence_level == ConfidenceLevel.MEDIUM)
        low = sum(1 for f in active_fields if f.confidence_level == ConfidenceLevel.LOW)
        rev = sum(1 for f in active_fields if f.review_required)

        by_type: dict[str, int] = {}
        for f in active_fields:
            by_type[f.field_type.value] = by_type.get(f.field_type.value, 0) + 1

        self.detection_summary = DetectionSummary(
            total_fields_detected=len(active_fields),
            high_confidence_count=high,
            medium_confidence_count=med,
            low_confidence_count=low,
            review_required_count=rev,
            conflicts_count=len(self.conflicts),
            fields_by_type=by_type,
        )

