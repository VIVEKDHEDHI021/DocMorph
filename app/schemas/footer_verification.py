"""Pydantic v2 schemas for the DocMorph Footer Verification Layer.

Defines the four definitive detection states, page-level verification evidence,
and document-level aggregated results.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.detection_data import BoundingBox


class FooterStatus(str, Enum):
    """The four canonical verification outcomes defined by DocMorph specification."""

    FOOTER_CONFIRMED = "FOOTER_CONFIRMED"
    FOOTER_NOT_FOUND = "FOOTER_NOT_FOUND"
    FOOTER_UNCERTAIN = "FOOTER_UNCERTAIN"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"


class FooterEvidenceScores(BaseModel):
    """Component evidence breakdown for explainable verification decisions."""

    model_config = ConfigDict(frozen=True)

    layout_score: float = Field(default=0.0, description="Score based on geometry, gap, separator lines, and position")
    multi_page_score: float = Field(default=0.0, description="Score based on cross-page position and styling consistency")
    semantic_score: float = Field(default=0.0, description="Supporting score from student identity or institution patterns")
    negative_score: float = Field(default=0.0, description="Penalty score from body text, prose, experiment/chapter terms")
    total_score: float = Field(default=0.0, description="Net aggregated evidence score")


class PageFooterVerification(BaseModel):
    """Verification assessment for an individual PDF page."""

    page_number: int = Field(description="1-based page number")
    status: FooterStatus = Field(description="Canonical footer status for this page")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the verification outcome")
    boundary_y: float = Field(description="Y coordinate threshold marking the top of the verified footer zone")
    has_separator_line: bool = Field(default=False, description="Whether a horizontal vector rule divides body from footer")
    separator_y: Optional[float] = Field(default=None, description="Y coordinate of the separator line if present")
    footer_bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box enclosing the verified footer content")
    evidence: FooterEvidenceScores = Field(default_factory=FooterEvidenceScores, description="Evidence score breakdown")
    negative_reasons: list[str] = Field(default_factory=list, description="Specific negative triggers identified")
    candidate_texts: list[str] = Field(default_factory=list, description="Raw text of blocks evaluated in footer zone")


class DocumentFooterVerification(BaseModel):
    """Document-wide aggregated footer verification result."""

    status: FooterStatus = Field(description="Overall document footer status")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall verification confidence")
    total_pages: int = Field(description="Total pages analyzed")
    confirmed_pages_count: int = Field(default=0, description="Number of pages with FOOTER_CONFIRMED")
    uncertain_pages_count: int = Field(default=0, description="Number of pages with FOOTER_UNCERTAIN")
    not_found_pages_count: int = Field(default=0, description="Number of pages with FOOTER_NOT_FOUND")
    page_results: list[PageFooterVerification] = Field(default_factory=list, description="Per-page verification results")
    summary_message: str = Field(default="", description="Human-readable decision explanation")
