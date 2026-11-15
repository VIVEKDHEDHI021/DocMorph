"""Value Extraction Service for DocMorph.

Extracts, cleans, and isolates field values associated with detected labels
across inline, multi-field, and adjacent line layouts.
"""

from dataclasses import dataclass
import re
from typing import Optional
import pymupdf

from app.schemas.detection_data import BoundingBox, FieldOccurrence, FieldType
from app.services.field_detector import MatchedLabel
from app.services.text_segmenter import StructuredLine, TextSegmenter


@dataclass
class ExtractedFieldValue:
    """Contains raw and cleaned field value data alongside precise coordinates."""

    field_type: FieldType
    matched_label: str
    value: str
    is_ambiguous: bool
    ambiguity_reason: Optional[str]
    occurrence: FieldOccurrence
    is_unlabelled: bool = False
    is_near_separator_line: bool = False
    is_bottom_left: bool = False


class ValueExtractor:
    """Isolates and validates values corresponding to detected student field labels."""

    # Patterns indicating non-value trailing footer content
    STOP_PATTERNS = re.compile(
        r"(?i)\b(?:page\s*\d+(?:\s*(?:of|/)\s*\d+)?|dated?:|date:|sign(?:ature)?:)\b"
    )

    @classmethod
    def extract_from_line(
        cls,
        line: StructuredLine,
        matched_labels: list[MatchedLabel],
        page: pymupdf.Page,
        next_line: Optional[StructuredLine] = None,
    ) -> list[ExtractedFieldValue]:
        """Extracts field values for all detected labels on a given line.

        Handles:
        - Label and value on same line separated by colon or hyphen.
        - Multiple labels on the same line (partitioned between labels).
        - Labels followed by value on the next line when same line has no value.

        Args:
            line: The StructuredLine containing the matched labels.
            matched_labels: Non-overlapping label matches on the line.
            page: PyMuPDF Page object for coordinate resolution.
            next_line: Optional succeeding line for multi-line associations.

        Returns:
            List of ExtractedFieldValue instances.
        """
        extracted_values: list[ExtractedFieldValue] = []

        for i, match in enumerate(matched_labels):
            # Determine the slice of text belonging to this field
            if i + 1 < len(matched_labels):
                raw_segment = line.text[match.end_char : matched_labels[i + 1].start_char]
                segment_end_char = matched_labels[i + 1].start_char
            else:
                raw_segment = line.text[match.end_char :]
                segment_end_char = len(line.text)

            # Extract and clean inline value
            clean_value = cls._clean_raw_value(raw_segment)
            is_multiline = False
            used_line = line

            # If inline value is empty, check next line association
            if not clean_value and next_line is not None:
                # Next line must not be another field label or stop pattern
                if cls._is_viable_next_line_value(next_line):
                    clean_value = cls._clean_raw_value(next_line.text)
                    if clean_value:
                        is_multiline = True
                        used_line = next_line

            # Format validation and ambiguity detection
            is_ambiguous = False
            ambiguity_reason = None

            if not clean_value:
                is_ambiguous = True
                ambiguity_reason = f"Missing value for label '{match.label_text}'"
            else:
                valid_format, reason = cls.validate_format(match.field_type, clean_value)
                if not valid_format:
                    is_ambiguous = True
                    ambiguity_reason = reason

            # Resolve exact bounding boxes
            label_bbox = TextSegmenter.resolve_substring_bbox(
                page=page,
                substring=match.label_text,
                line=line,
                start_char=match.start_char,
                end_char=match.end_char,
            )

            value_bbox = None
            if clean_value:
                # Find value start offset within used_line
                val_start = used_line.text.find(clean_value)
                if val_start != -1:
                    val_end = val_start + len(clean_value)
                else:
                    val_start = match.end_char
                    val_end = segment_end_char

                value_bbox = TextSegmenter.resolve_substring_bbox(
                    page=page,
                    substring=clean_value,
                    line=used_line,
                    start_char=val_start,
                    end_char=val_end,
                )

            # Overall bbox encompasses label and value
            overall_bbox = label_bbox if value_bbox is None else label_bbox.union(value_bbox)

            occurrence = FieldOccurrence(
                page_number=line.page_number,
                bbox=overall_bbox,
                value_bbox=value_bbox,
                label_bbox=label_bbox,
                block_number=line.block_number,
                line_number=line.line_number,
                span_information=line.spans,
                raw_text=line.text if not is_multiline else f"{line.text} {next_line.text}",
                matched_label=match.label_text,
                is_in_footer_region=line.is_in_footer,
            )

            extracted_values.append(
                ExtractedFieldValue(
                    field_type=match.field_type,
                    matched_label=match.label_text,
                    value=clean_value,
                    is_ambiguous=is_ambiguous,
                    ambiguity_reason=ambiguity_reason,
                    occurrence=occurrence,
                )
            )

        return extracted_values

    @classmethod
    def _clean_raw_value(cls, segment: str) -> str:
        """Strips delimiters, stop words, and punctuation from a raw value segment."""
        if not segment:
            return ""

        # Strip leading punctuation and whitespace (: - = . etc.)
        val = re.sub(r"^[\s:\-=\–\—.]+", "", segment)

        # Truncate before stop patterns (e.g. Page 1 of 5, Date:, Sign:)
        stop_match = cls.STOP_PATTERNS.search(val)
        if stop_match:
            val = val[: stop_match.start()]

        # Delimiters indicating separation of fields (pipe, bullet, tab, semicolon)
        for delim in ["|", ";", "•", "\t"]:
            if delim in val:
                val = val.split(delim)[0]

        # Strip trailing punctuation and whitespace
        val = re.sub(r"[\s,;:|/\-]+$", "", val)

        return val.strip()

    @classmethod
    def _is_viable_next_line_value(cls, line: StructuredLine) -> bool:
        """Determines if a succeeding line is a plausible continuation value."""
        if not line.text or len(line.text) > 80:
            return False

        # Reject if next line starts with another recognized label
        label_check = re.match(
            r"(?i)^(?:student|name|roll|enroll|enrol|id|date|page|sign)",
            line.text.strip(),
        )
        if label_check:
            return False

        # Reject if next line is a long sentence (e.g. 8+ words)
        if len(line.text.split()) > 7:
            return False

        return True

    @classmethod
    def validate_format(cls, field_type: FieldType, value: str) -> tuple[bool, str]:
        """Validates format plausibility for a specific student field type.

        Args:
            field_type: Expected FieldType.
            value: Extracted string value.

        Returns:
            Tuple of (is_valid, reason_string).
        """
        val = value.strip()
        if not val:
            return False, "Value is empty"

        if field_type == FieldType.STUDENT_NAME:
            # Person names: 1 to 5 words, letters, dots, hyphens, apostrophes
            if any(char.isdigit() for char in val):
                return False, f"Name contains unexpected digits: '{val}'"
            if len(val) < 2:
                return False, f"Name value too short: '{val}'"
            words = val.split()
            if len(words) > 5:
                return False, f"Name value contains suspiciously many words ({len(words)}): '{val}'"
            if not re.match(r"^[A-Za-z\s.\'\-]+$", val):
                return False, f"Name contains unexpected characters: '{val}'"
            return True, "Valid person name format"

        elif field_type == FieldType.ENROLLMENT_NUMBER:
            # Enrollment numbers: 6 to 24 characters, mostly digits or alphanumeric
            cleaned = re.sub(r"[\s\-]", "", val)
            if len(cleaned) < 4 or len(cleaned) > 25:
                return False, f"Enrollment number length ({len(cleaned)}) outside expected bounds: '{val}'"
            # Require at least some digits
            if not any(c.isdigit() for c in cleaned):
                return False, f"Enrollment number lacks digits: '{val}'"
            if not re.match(r"^[A-Za-z0-9\-]+$", cleaned):
                return False, f"Enrollment number contains invalid characters: '{val}'"
            return True, "Valid enrollment number format"

        elif field_type == FieldType.ROLL_NUMBER:
            # Roll numbers: 1 to 8 chars, integer (25) or short code (CS-25)
            cleaned = re.sub(r"[\s]", "", val)
            if len(cleaned) < 1 or len(cleaned) > 10:
                return False, f"Roll number length ({len(cleaned)}) outside expected bounds: '{val}'"
            if not re.match(r"^[A-Za-z0-9\-]+$", cleaned):
                return False, f"Roll number contains invalid characters: '{val}'"
            return True, "Valid roll number format"

        elif field_type == FieldType.STUDENT_ID:
            # Student ID: 3 to 20 alphanumeric characters
            cleaned = re.sub(r"[\s]", "", val)
            if len(cleaned) < 2 or len(cleaned) > 25:
                return False, f"Student ID length ({len(cleaned)}) outside expected bounds: '{val}'"
            if not re.match(r"^[A-Za-z0-9\-]+$", cleaned):
                return False, f"Student ID contains invalid characters: '{val}'"
            return True, "Valid student ID format"

        elif field_type == FieldType.UNKNOWN_IDENTIFIER:
            cleaned = re.sub(r"[\s]", "", val)
            if len(cleaned) < 2 or len(cleaned) > 25:
                return False, f"Identifier length ({len(cleaned)}) outside expected bounds: '{val}'"
            if not re.match(r"^[A-Za-z0-9\-]+$", cleaned):
                return False, f"Identifier contains invalid characters: '{val}'"
            return True, "Valid identifier format"

        return True, "Format accepted"

