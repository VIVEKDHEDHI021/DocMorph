"""Field Detection Service for DocMorph.

Recognizes student-related field labels across common variations in casing,
punctuation, spacing, and abbreviations while rejecting non-student context.
"""

from dataclasses import dataclass
import re
from typing import Optional

from app.schemas.detection_data import FieldType


@dataclass
class MatchedLabel:
    """Represents a matched field label occurrence in a text string."""

    field_type: FieldType
    label_text: str
    start_char: int
    end_char: int
    is_specific: bool = True  # True if label is explicitly student-specific vs generic "Name"


class FieldDetector:
    """Detects student-related field labels in extracted document text."""

    # Prioritized label patterns (more specific regexes tested before generic ones)
    PATTERNS: list[tuple[FieldType, re.Pattern, bool]] = [
        # Student ID patterns
        (
            FieldType.STUDENT_ID,
            re.compile(
                r"(?i)\b(?:student\s+(?:id|identification\s+number|code|no\.?)|student_?id|stud\s+id)\b"
            ),
            True,
        ),
        # Enrollment Number patterns
        (
            FieldType.ENROLLMENT_NUMBER,
            re.compile(
                r"(?i)\b(?:enrollment|enrolment|enroll|enrol)\s*(?:no\.?|number|id|#)?\b"
            ),
            True,
        ),
        # Roll Number patterns
        (
            FieldType.ROLL_NUMBER,
            re.compile(
                r"(?i)\b(?:class\s+|exam\s+)?roll\s*(?:no\.?|number|#)?\b"
            ),
            True,
        ),
        # Explicit Student Name patterns
        (
            FieldType.STUDENT_NAME,
            re.compile(
                r"(?i)\b(?:name\s+of\s+student|student(?:\'s)?\s+(?:full\s+)?name|candidate\s+name|learner\s+name)\b"
            ),
            True,
        ),
        # Student: or Student - (with delimiter or at end of line)
        (
            FieldType.STUDENT_NAME,
            re.compile(
                r"(?i)\bstudent\s*(?:[:\-=\–\—]|$)"
            ),
            False,
        ),
        # Generic Name: or Name - (with delimiter or at end of line, avoiding non-student words)
        (
            FieldType.STUDENT_NAME,
            re.compile(
                r"(?i)(?<!file\s)(?<!algorithm\s)(?<!faculty\s)(?<!teacher\s)(?<!instructor\s)"
                r"(?<!college\s)(?<!department\s)(?<!project\s)(?<!topic\s)(?<!experiment\s)"
                r"(?<!module\s)(?<!book\s)(?<!author\s)\bname\s*(?:[:\-=\–\—]|$)"
            ),
            False,
        ),
    ]

    @classmethod
    def find_field_labels(cls, text: str) -> list[MatchedLabel]:
        """Scans a text string and returns all non-overlapping student label matches.

        Matches are sorted by their starting position in the string.

        Args:
            text: Text line or segment to search.

        Returns:
            List of non-overlapping MatchedLabel instances in left-to-right order.
        """
        if not text:
            return []

        raw_matches: list[MatchedLabel] = []

        for field_type, pattern, is_specific in cls.PATTERNS:
            for match in pattern.finditer(text):
                raw_text = match.group(0)
                cleaned_text = re.sub(r"[\s:\-=\–\—.]+$", "", raw_text)
                clean_end = match.start() + len(cleaned_text)
                raw_matches.append(
                    MatchedLabel(
                        field_type=field_type,
                        label_text=cleaned_text,
                        start_char=match.start(),
                        end_char=clean_end,
                        is_specific=is_specific,
                    )
                )

        if not raw_matches:
            return []

        # Sort matches by start position, resolving ties by longer length and specificity
        raw_matches.sort(
            key=lambda m: (m.start_char, -(m.end_char - m.start_char), not m.is_specific)
        )

        # Filter out overlapping matches (keep earlier/longer/more specific match)
        non_overlapping: list[MatchedLabel] = []
        last_end = -1

        for candidate in raw_matches:
            if candidate.start_char >= last_end:
                non_overlapping.append(candidate)
                last_end = candidate.end_char

        return non_overlapping
