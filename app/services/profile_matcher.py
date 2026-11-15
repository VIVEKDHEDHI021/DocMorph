"""Profile Matching Engine for DocMorph.

Phase 4 Enhancement:
Compares detected document fields from Phase 2 against the user's saved personal profile,
evaluates matching statuses (already_matching, different, not_detected, uncertain,
conflicting, optional_field_empty), and prepares an intelligent, non-destructive
auto-personalization replacement plan.
"""

import re
from typing import Optional

from app.schemas.api_schemas import PersonalizeFieldItem
from app.schemas.detection_data import (
    ConfidenceLevel,
    DetectedField,
    DetectionResult,
    FieldConflict,
    FieldType,
)
from app.schemas.profile_data import (
    FieldMatchComparison,
    ProfileMatchResult,
    ProfileMatchStatus,
    StudentProfile,
)


class ProfileMatcher:
    """Matches detected academic document fields against local student profile."""

    @classmethod
    def match_profile(
        cls,
        detection_result: any,
        profile: StudentProfile,
        min_auto_confidence: float = 0.70,
    ) -> ProfileMatchResult:
        """Compares detection results against the student profile and prepares a safe replacement plan."""
        comparisons: dict[str, FieldMatchComparison] = {}
        replacement_plan: list[PersonalizeFieldItem] = []
        raw_conflicts = getattr(detection_result, "conflicts", [])
        has_conflicts = bool(raw_conflicts)
        requires_manual_review = False

        # 1. Group detected fields by field_type string
        detected_by_type: dict[str, list[any]] = {}
        raw_fields = getattr(detection_result, "detected_fields", None)
        if raw_fields is None:
            raw_fields = getattr(detection_result, "fields", [])

        for f in raw_fields:
            ft_str = f.field_type.value if hasattr(f.field_type, "value") else str(f.field_type)
            detected_by_type.setdefault(ft_str, []).append(f)

        # 2. Define field configurations to evaluate
        field_configs = [
            ("student_name", profile.full_name, True),
            ("enrollment_number", profile.enrollment_number, True),
            ("roll_number", profile.roll_number, False),
            ("student_id", profile.student_id, False),
        ]

        # 3. Track fields with cross-page conflicts
        conflicted_types: set[str] = set()
        for conflict in raw_conflicts:
            c_type = conflict.field_type.value if hasattr(conflict.field_type, "value") else str(conflict.field_type)
            conflicted_types.add(c_type)

        for f_type, prof_val, is_required in field_configs:
            fields = detected_by_type.get(f_type, [])

            if not fields:
                if not prof_val:
                    status = ProfileMatchStatus.OPTIONAL_FIELD_EMPTY
                    reason = f"Optional field '{f_type}' is not configured in your profile."
                else:
                    status = ProfileMatchStatus.NOT_DETECTED
                    reason = f"No {f_type.replace('_', ' ')} detected in this document."

                comparisons[f_type] = FieldMatchComparison(
                    field_type=f_type,
                    detected_value=None,
                    profile_value=prof_val,
                    status=status,
                    confidence=0.0,
                    field_id=None,
                    auto_action_eligible=False,
                    reason=reason,
                )
                continue

            primary = fields[0]

            is_ambiguous = getattr(primary, "is_ambiguous", False) or getattr(primary, "review_required", False)
            if f_type in conflicted_types or is_ambiguous:
                status = ProfileMatchStatus.CONFLICTING
                reason = "Cross-page conflicting values detected. Manual review required."
                auto_action_eligible = False
                requires_manual_review = True
            elif primary.confidence < min_auto_confidence:
                status = ProfileMatchStatus.UNCERTAIN
                reason = f"Detection confidence ({primary.confidence:.2f}) below safe threshold ({min_auto_confidence:.2f})."
                auto_action_eligible = False
                requires_manual_review = True
            elif not prof_val:
                status = ProfileMatchStatus.OPTIONAL_FIELD_EMPTY
                reason = "Document contains field but your profile has no value configured."
                auto_action_eligible = False
            elif cls._values_match(f_type, primary.original_value, prof_val):
                status = ProfileMatchStatus.ALREADY_MATCHING
                reason = "Document already matches your student profile."
                auto_action_eligible = False
            else:
                status = ProfileMatchStatus.DIFFERENT
                reason = f"Detected '{primary.original_value}' will be updated to '{prof_val}'."
                auto_action_eligible = True
                replacement_plan.append(
                    PersonalizeFieldItem(
                        field_id=primary.field_id,
                        field_type=f_type,
                        new_value=prof_val,
                    )
                )

            comparisons[f_type] = FieldMatchComparison(
                field_type=f_type,
                detected_value=primary.original_value,
                profile_value=prof_val,
                status=status,
                confidence=primary.confidence,
                field_id=primary.field_id,
                auto_action_eligible=auto_action_eligible,
                reason=reason,
            )

        # 4. Determine overall readiness for safe auto-personalization
        detected_count = len(raw_fields)
        eligible_count = len(replacement_plan)
        already_matching_count = sum(
            1 for c in comparisons.values() if c.status == ProfileMatchStatus.ALREADY_MATCHING
        )

        all_eligible_for_auto = (
            not requires_manual_review
            and not has_conflicts
            and (eligible_count > 0 or already_matching_count > 0)
            and all(
                c.status in (ProfileMatchStatus.ALREADY_MATCHING, ProfileMatchStatus.DIFFERENT, ProfileMatchStatus.OPTIONAL_FIELD_EMPTY, ProfileMatchStatus.NOT_DETECTED)
                for c in comparisons.values()
            )
        )

        if has_conflicts:
            summary_message = "Document has conflicting student identities across pages. Manual review is required."
        elif requires_manual_review:
            summary_message = "Low confidence detections require manual verification before replacement."
        elif already_matching_count > 0 and eligible_count == 0:
            summary_message = "All detected fields already match your student profile. No modifications needed."
        elif eligible_count > 0:
            summary_message = f"Found {eligible_count} field(s) ready for automatic personalization."
        else:
            summary_message = "No matching fields detected for personalization."

        return ProfileMatchResult(
            document_id=detection_result.document_id,
            comparisons=comparisons,
            all_eligible_for_auto=all_eligible_for_auto,
            has_conflicts=has_conflicts,
            requires_manual_review=requires_manual_review,
            auto_replacement_plan=replacement_plan,
            summary_message=summary_message,
        )

    @classmethod
    def _values_match(cls, field_type: str, val1: Optional[str], val2: Optional[str]) -> bool:
        """Determines if two values match semantically considering formatting differences."""
        if not val1 or not val2:
            return False

        if field_type == "student_name":
            n1 = cls._normalize_name(val1)
            n2 = cls._normalize_name(val2)
            return n1 == n2

        return val1.strip().lower() == val2.strip().lower()

    @classmethod
    def _normalize_name(cls, name: str) -> str:
        """Normalizes names by handling PascalCase/CamelCase, spaces, and punctuation."""
        clean = name.strip()
        clean = re.sub(r"([a-z])([A-Z])", r"\1 \2", clean)
        words = [w.lower() for w in re.split(r"[\s.\-_]+", clean) if w]
        return " ".join(words)
