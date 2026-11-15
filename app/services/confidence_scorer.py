"""Confidence Scoring Service for DocMorph.

Calculates multi-factor confidence scores (0.0 to 1.0) with explainable reasons
evaluating label specificity, value validity, page geometry, and repetition.
"""

from dataclasses import dataclass
import re
from typing import Optional

from app.core.config import Settings, settings
from app.schemas.detection_data import ConfidenceLevel, FieldType
from app.services.value_extractor import ValueExtractor


@dataclass
class ConfidenceScoreResult:
    """Contains calculated numeric score, categorical level, reasons, and review flag."""

    score: float
    level: ConfidenceLevel
    reasons: list[str]
    review_required: bool


class ConfidenceScorer:
    """Computes explainable confidence ratings for detected student fields."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize with configurable threshold boundaries.

        Args:
            config: Settings instance holding high and medium thresholds.
        """
        self.config = config
        self.high_threshold = config.CONFIDENCE_HIGH_THRESHOLD
        self.medium_threshold = config.CONFIDENCE_MEDIUM_THRESHOLD

    def score_field(
        self,
        field_type: FieldType,
        matched_label: str,
        is_specific_label: bool,
        value: str,
        is_in_footer: bool,
        is_ambiguous: bool = False,
        ambiguity_reason: Optional[str] = None,
        occurrence_count: int = 1,
        total_pages: int = 1,
        has_conflict: bool = False,
    ) -> ConfidenceScoreResult:
        """Calculates a normalized confidence score and explanation for a detection.

        Args:
            field_type: FieldType enum.
            matched_label: The exact label text that triggered detection.
            is_specific_label: True if label is explicitly student-specific.
            value: The extracted field value string.
            is_in_footer: True if occurrence resides within the footer zone.
            is_ambiguous: True if extraction flagged ambiguity.
            ambiguity_reason: Optional description of why value is ambiguous.
            occurrence_count: Number of pages where this value appears.
            total_pages: Total pages in the document.
            has_conflict: True if contradictory values exist on other pages.

        Returns:
            ConfidenceScoreResult with score, level, reasons, and review_required.
        """
        score = 0.0
        reasons: list[str] = []
        review_required = False

        # --- 1. Label Specificity Component (up to 0.35) ---
        if is_specific_label:
            score += 0.35
            reasons.append(f"Explicit student label match '{matched_label}' (+0.35)")
        else:
            score += 0.20
            reasons.append(f"Generic label match '{matched_label}' (+0.20)")

        # --- 2. Value Validity Component (up to 0.35) ---
        if not value or not value.strip():
            review_required = True
            reasons.append("Missing or empty field value (+0.00)")
        else:
            is_valid_fmt, fmt_reason = ValueExtractor.validate_format(field_type, value)
            if is_valid_fmt:
                score += 0.35
                reasons.append(f"{fmt_reason} (+0.35)")
            else:
                score += 0.05
                review_required = True
                reasons.append(f"Non-standard format: {fmt_reason} (+0.05)")

        # --- 3. Spatial Geometry Component (up to 0.15) ---
        if is_in_footer:
            score += 0.15
            reasons.append("Located within geometric page footer region (+0.15)")
        else:
            score += 0.05
            reasons.append("Located outside primary footer region (+0.05)")

        # --- 4. Document-wide Repetition & Consistency (up to 0.15) ---
        if has_conflict:
            score -= 0.20
            review_required = True
            reasons.append("Inconsistent conflicting value observed across pages (-0.20)")
        elif occurrence_count >= 2:
            score += 0.15
            reasons.append(f"Value consistently repeated across {occurrence_count} pages (+0.15)")
        elif total_pages == 1:
            score += 0.10
            reasons.append("Single-page document consistency (+0.10)")
        else:
            score += 0.05
            reasons.append("Single occurrence in multi-page document (+0.05)")

        # --- 5. Ambiguity Handling ---
        if is_ambiguous:
            review_required = True
            if ambiguity_reason:
                reasons.append(f"Ambiguity flag: {ambiguity_reason}")

        # Clamp score between 0.0 and 1.0
        final_score = round(max(0.0, min(1.0, score)), 2)

        # Categorize tier
        if final_score >= self.high_threshold:
            level = ConfidenceLevel.HIGH
        elif final_score >= self.medium_threshold:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
            review_required = True

        return ConfidenceScoreResult(
            score=final_score,
            level=level,
            reasons=reasons,
            review_required=review_required,
        )

    def score_unlabelled_field(
        self,
        field_type: FieldType,
        value: str,
        is_bottom_left: bool,
        is_in_footer: bool,
        is_near_separator_line: bool,
        occurrence_count: int = 1,
        total_pages: int = 1,
        has_conflict: bool = False,
    ) -> ConfidenceScoreResult:
        """Calculates a normalized confidence score and explanation for an unlabelled detection.

        Args:
            field_type: Detected FieldType enum.
            value: Extracted string value.
            is_bottom_left: True if position is aligned to bottom-left margin.
            is_in_footer: True if position is within footer zone.
            is_near_separator_line: True if occurrence is near/below a separator line.
            occurrence_count: Number of pages where this value appears.
            total_pages: Total pages in the document.
            has_conflict: True if contradictory values exist on other pages.

        Returns:
            ConfidenceScoreResult with score, level, reasons, and review_required.
        """
        score = 0.0
        reasons: list[str] = []
        review_required = False

        # --- 1. Position-Aware Geometry (up to 0.30) ---
        if is_in_footer:
            score += 0.10
            reasons.append("Located within geometric page footer region (+0.10)")
        if is_bottom_left:
            score += 0.10
            reasons.append("Aligned with bottom-left margin (+0.10)")
        if is_near_separator_line:
            score += 0.10
            reasons.append("Associated with footer separator line (+0.10)")

        # --- 2. Combined Identity Pattern Match (up to 0.25) ---
        score += 0.25
        reasons.append("Recognized structured unlabelled identity pattern (+0.25)")

        # --- 3. Credential Plausibility & Non-Page-Number (up to 0.30) ---
        if field_type == FieldType.STUDENT_NAME:
            tokens = value.split()
            # Also handle PascalCase / CamelCase concatenated names like 'VivekDhedhi'
            if len(tokens) < 2 and any(c.isupper() for c in value[1:]):
                tokens = re.findall(r"[A-Z][a-z]+|[a-z]+", value)

            if len(tokens) >= 2 and all(t.isalpha() or len(t) == 1 for t in tokens):
                score += 0.20
                reasons.append("Valid multi-token personal name syntax (+0.20)")
            else:
                score += 0.10
                reasons.append("Plausible personal name syntax (+0.10)")
            score += 0.10
            reasons.append("Verified absence of academic stop words (+0.10)")

        elif field_type in (
            FieldType.ENROLLMENT_NUMBER,
            FieldType.ROLL_NUMBER,
            FieldType.UNKNOWN_IDENTIFIER,
            FieldType.STUDENT_ID,
        ):
            if field_type == FieldType.ENROLLMENT_NUMBER:
                score += 0.20
                reasons.append("Valid student enrollment number syntax (+0.20)")
            elif field_type == FieldType.ROLL_NUMBER:
                score += 0.20
                reasons.append("Valid student roll number syntax (+0.20)")
            else:
                score += 0.15
                reasons.append("Valid student identifier syntax (+0.15)")
            score += 0.10
            reasons.append("Confirmed non-page-number credential (+0.10)")

        # --- 4. Cross-Page Consistency & Repetition (up to 0.15) ---
        if has_conflict:
            score -= 0.20
            review_required = True
            reasons.append("Inconsistent conflicting value observed across pages (-0.20)")
        elif occurrence_count >= 2:
            score += 0.15
            reasons.append(f"Value consistently repeated across {occurrence_count} pages (+0.15)")
        elif total_pages == 1:
            score += 0.10
            reasons.append("Single-page document consistency (+0.10)")
        else:
            score += 0.05
            reasons.append("Single occurrence in multi-page document (+0.05)")

        final_score = round(max(0.0, min(1.0, score)), 2)

        if final_score >= self.high_threshold:
            level = ConfidenceLevel.HIGH
        elif final_score >= self.medium_threshold:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
            review_required = True

        return ConfidenceScoreResult(
            score=final_score,
            level=level,
            reasons=reasons,
            review_required=review_required,
        )


