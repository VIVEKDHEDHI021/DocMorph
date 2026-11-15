"""Field Grouping and Conflict Resolution Service for DocMorph.

Aggregates repeated spatial field occurrences across pages, tracks exact
bounding boxes, detects multi-page value discrepancies, and emits stable field IDs.
"""

from collections import defaultdict
import hashlib
from typing import Optional

from app.schemas.detection_data import (
    DetectedField,
    FieldConflict,
    FieldOccurrence,
    FieldType,
)
from app.services.confidence_scorer import ConfidenceScorer
from app.services.field_detector import MatchedLabel
from app.services.value_extractor import ExtractedFieldValue


class FieldGrouper:
    """Groups occurrences of the same field and detects cross-page conflicts."""

    def __init__(self, confidence_scorer: Optional[ConfidenceScorer] = None) -> None:
        """Initialize with a ConfidenceScorer instance.

        Args:
            confidence_scorer: Optional ConfidenceScorer; defaults to a new instance.
        """
        self.scorer = confidence_scorer or ConfidenceScorer()

    def group_and_resolve(
        self,
        extracted_values: list[ExtractedFieldValue],
        total_pages: int,
        document_id: str = "doc",
    ) -> tuple[list[DetectedField], list[FieldConflict]]:
        """Groups raw field occurrences by type and value, identifies conflicts, and scores fields.

        Args:
            extracted_values: List of ExtractedFieldValue instances from all pages.
            total_pages: Total number of pages in the PDF.
            document_id: Stable identifier of the analyzed document.

        Returns:
            Tuple of (list of DetectedField, list of FieldConflict).
        """
        # Step 1: Bucket extractions by field_type
        by_type: dict[FieldType, list[ExtractedFieldValue]] = defaultdict(list)
        for ev in extracted_values:
            by_type[ev.field_type].append(ev)

        detected_fields: list[DetectedField] = []
        conflicts: list[FieldConflict] = []

        field_counter = 0

        # Step 2: Process each field type independently
        for field_type, values in by_type.items():
            # Sub-group by normalized value
            by_val: dict[str, list[ExtractedFieldValue]] = defaultdict(list)
            for v in values:
                norm_key = v.value.strip().lower()
                by_val[norm_key].append(v)

            # Check if this field type has multiple non-empty conflicting values across pages
            non_empty_values = [k for k in by_val.keys() if k]
            type_has_conflict = len(non_empty_values) > 1

            conflict_field_ids: list[str] = []
            conflicting_val_strings: list[str] = []
            conflict_pages: set[int] = set()

            type_fields: list[DetectedField] = []

            for norm_key, occurrences_group in by_val.items():
                field_counter += 1
                field_id = f"{field_type.value}_{field_counter}"

                rep_value = occurrences_group[0].value
                rep_label = occurrences_group[0].matched_label

                # Accumulate all physical occurrences
                all_occurrences: list[FieldOccurrence] = [
                    g.occurrence for g in occurrences_group
                ]

                # Sort occurrences by page number and vertical position
                all_occurrences.sort(key=lambda o: (o.page_number, o.bbox.y0))

                any_ambiguous = any(g.is_ambiguous for g in occurrences_group)
                ambiguity_reason = next(
                    (g.ambiguity_reason for g in occurrences_group if g.ambiguity_reason),
                    None,
                )

                # Determine if any occurrence was in the footer region
                is_in_footer = any(o.is_in_footer_region for o in all_occurrences)
                is_unlabelled = (
                    any(getattr(g, "is_unlabelled", False) for g in occurrences_group)
                    or rep_label == ""
                )
                is_near_sep = any(
                    getattr(g, "is_near_separator_line", False) for g in occurrences_group
                )
                is_bottom_left = any(
                    getattr(g, "is_bottom_left", False) for g in occurrences_group
                )

                if is_unlabelled:
                    score_res = self.scorer.score_unlabelled_field(
                        field_type=field_type,
                        value=rep_value,
                        is_bottom_left=is_bottom_left,
                        is_in_footer=is_in_footer,
                        is_near_separator_line=is_near_sep,
                        occurrence_count=len(all_occurrences),
                        total_pages=total_pages,
                        has_conflict=type_has_conflict,
                    )
                    method = "unlabelled_identity_recognition"
                    # Requirement 8: Only emit detections that meet minimum confidence threshold (>= 0.65)
                    if score_res.score < 0.65:
                        continue
                else:
                    # Score confidence using scorer for labelled fields
                    score_res = self.scorer.score_field(
                        field_type=field_type,
                        matched_label=rep_label,
                        is_specific_label=len(rep_label.split()) > 1 or field_type != FieldType.STUDENT_NAME,
                        value=rep_value,
                        is_in_footer=is_in_footer,
                        is_ambiguous=any_ambiguous,
                        ambiguity_reason=ambiguity_reason,
                        occurrence_count=len(all_occurrences),
                        total_pages=total_pages,
                        has_conflict=type_has_conflict,
                    )
                    method = "hybrid_rules_regex"

                detected_field = DetectedField(
                    field_id=field_id,
                    field_type=field_type,
                    original_value=rep_value,
                    suggested_value=rep_value,
                    confidence=score_res.score,
                    confidence_level=score_res.level,
                    detection_method=method,
                    review_required=score_res.review_required or type_has_conflict,
                    status=score_res.level == "low" and "pending" or "pending",
                    confidence_reasons=score_res.reasons,
                    occurrences=all_occurrences,
                )

                type_fields.append(detected_field)

                if type_has_conflict and rep_value:
                    conflict_field_ids.append(field_id)
                    conflicting_val_strings.append(rep_value)
                    for occ in all_occurrences:
                        conflict_pages.add(occ.page_number)

            detected_fields.extend(type_fields)

            # Record conflict object if contradictory values exist
            if type_has_conflict and len(conflicting_val_strings) > 1:
                conflict_id = f"conflict_{field_type.value}_{len(conflicts) + 1}"
                conflicts.append(
                    FieldConflict(
                        conflict_id=conflict_id,
                        field_type=field_type,
                        field_ids=conflict_field_ids,
                        conflicting_values=conflicting_val_strings,
                        pages=sorted(list(conflict_pages)),
                        description=(
                            f"Inconsistent values detected for {field_type.value}: "
                            f"{', '.join(repr(v) for v in conflicting_val_strings)} "
                            f"across pages {sorted(list(conflict_pages))}."
                        ),
                    )
                )

        return detected_fields, conflicts

