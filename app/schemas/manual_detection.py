"""Pydantic v2 schemas for Phase C: Smart Manual Detection Engine.

Defines input boundary models for area selection and text selection, coordinate geometry,
and structured manual detection responses.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.detection_data import BoundingBox, DetectedField
from app.schemas.footer_verification import FooterStatus


class SelectionType(str, Enum):
    """Supported selection guidance methods."""

    AREA = "area"
    TEXT = "text"


class ManualSelectionRequest(BaseModel):
    """Input boundary for guided engine search."""

    model_config = ConfigDict(frozen=True)

    document_id: str = Field(description="Unique document identifier")
    page_number: int = Field(ge=1, description="1-based page number")
    selection_type: SelectionType = Field(description="Area selection or text selection")
    page_width: float = Field(gt=0, description="Page width in PDF points")
    page_height: float = Field(gt=0, description="Page height in PDF points")

    # Geometry for area selection
    raw_bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box in PDF points")
    normalized_bbox: Optional[tuple[int, int, int, int]] = Field(
        default=None, description="Normalized coordinates [x0, y0, x1, y1] in [0, 1000]"
    )

    # Context for text selection
    selected_text: Optional[str] = Field(default=None, description="Highlighted text string")
    text_bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box of highlighted text in PDF points")

    @field_validator("raw_bbox", mode="before")
    @classmethod
    def parse_raw_bbox(cls, v):
        if isinstance(v, (list, tuple)) and len(v) == 4:
            return BoundingBox(x0=float(v[0]), y0=float(v[1]), x1=float(v[2]), y1=float(v[3]))
        return v


class ManualDetectionResponse(BaseModel):
    """Structured detection outcome from Smart Manual Detection analysis."""

    document_id: str = Field(description="Unique document identifier")
    page_number: int = Field(description="1-based page number")
    selection_type: SelectionType = Field(description="Method used for manual guidance")
    resolved_pdf_bbox: BoundingBox = Field(description="Clamped bounding box in PDF points")
    extracted_text: str = Field(description="All text content found inside the selection boundary")
    footer_status: FooterStatus = Field(description="Verification outcome for the selected content")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the verification outcome")
    detected_fields: list[DetectedField] = Field(
        default_factory=list, description="Verified student fields found inside selection"
    )
    negative_reasons: list[str] = Field(
        default_factory=list, description="Explanation for any rejection or penalty"
    )
    summary_message: str = Field(description="User-facing explanation of the detection outcome")
