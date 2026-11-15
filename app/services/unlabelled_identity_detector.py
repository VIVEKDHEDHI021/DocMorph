"""Unlabelled Student Identity Recognition Engine for DocMorph.

Intelligently recognizes unlabelled student credentials (e.g. 'Vivek dhedhi (92400120571)')
in academic PDF footers using geometry, typography, and pattern disambiguation without
requiring explicit labels like 'Name:' or 'Enrollment No:'.
"""

from dataclasses import dataclass
import re
from typing import Optional
import pymupdf

from app.schemas.detection_data import (
    BoundingBox,
    FieldOccurrence,
    FieldType,
)
from app.services.footer_detector import FooterDetector
from app.services.text_segmenter import StructuredLine, TextSegmenter
from app.services.value_extractor import ExtractedFieldValue


@dataclass
class UnlabelledMatch:
    """Represents a candidate identity pair detected on a page."""

    name: str
    identifier: str
    id_field_type: FieldType
    name_start: int
    name_end: int
    id_start: int
    id_end: int
    is_inverted: bool = False


class UnlabelledIdentityDetector:
    """Position-aware, layout-driven detector for unlabelled student identity pairs."""

    # Academic stop words and institutional entities that cannot be personal student names
    ACADEMIC_STOP_WORDS: set[str] = {
        # Academic disciplines and faculties
        "computer engineering",
        "information technology",
        "mechanical engineering",
        "civil engineering",
        "electrical engineering",
        "electronics engineering",
        "electronics and communication",
        "chemical engineering",
        "biotechnology",
        "aerospace engineering",
        "data science",
        "artificial intelligence",
        "machine learning",
        "cyber security",
        # Institutional organizational terms
        "department of",
        "department",
        "dept of",
        "dept",
        "faculty of",
        "faculty",
        "school of",
        "university",
        "college",
        "institute",
        "polytechnic",
        "academy",
        "campus",
        # Universities
        "marwadi university",
        "gujarat technological university",
        "gtu",
        "mru",
        # Document and assignment terminology
        "lab manual",
        "laboratory manual",
        "laboratory",
        "practical",
        "experiment",
        "assignment",
        "exercise",
        "course",
        "subject",
        "syllabus",
        "curriculum",
        "index",
        "aim",
        "objective",
        "apparatus",
        "theory",
        "procedure",
        "observation",
        "calculation",
        "result",
        "conclusion",
        "discussion",
        "program",
        "source code",
        "output",
        "code",
        # Academic calendar & evaluation labels
        "submission date",
        "submission",
        "date",
        "page",
        "academic year",
        "semester",
        "sem",
        "term",
        "class",
        "division",
        "batch",
        "signature",
        "sign",
        "remark",
        "grade",
        "marks",
        "evaluation",
        "assessment",
        # Instructional roles
        "teacher",
        "instructor",
        "professor",
        "guide",
        "mentor",
        "hod",
        "head of department",
        "principal",
        "dean",
        # General metadata
        "topic",
        "title",
        "author",
        "authors",
        "edition",
        "editions",
        "published",
        "publisher",
        "isbn",
        "issn",
        "docmorph",
        "study material",
        "lecture notes",
        "reference",
        "references",
        "bibliography",
        "citations",
        "citation",
        "precautions",
        "precaution",
        "conclusions",
        "results",
        "observations",
        "experiments",
        "practicals",
        "assignments",
        "exercises",
        "chapters",
        "chapter",
        "sections",
        "section",
        "units",
        "unit",
        "table of contents",
    }

    # Combined identity patterns in order of priority
    IDENTITY_PATTERNS: list[tuple[re.Pattern, bool]] = [
        # 1. Name followed by ID in parentheses or brackets: 'Vivek dhedhi (92400120571)', 'Vivek Dhedhi [92400120571]'
        (
            re.compile(
                r"^(?P<name>[A-Za-z\s.\'\-]+?)\s*[\(\[]\s*(?P<id>[A-Za-z0-9\-_/]+)\s*[\)\]]"
            ),
            False,
        ),
        # 2. Name followed by delimiter (- | , / – —) and ID: 'Vivek Dhedhi - 92400120571', 'Vivek Dhedhi | 92400120571', 'Vivek Dhedhi, 92400120571'
        (
            re.compile(
                r"^(?P<name>[A-Za-z\s.\'\-]+?)\s*[\-–—|,/]\s*(?P<id>[A-Za-z0-9\-_/]+)"
            ),
            False,
        ),
        # 3. ID followed by delimiter and Name (inverted order): '92400120571 - Vivek Dhedhi', '92400120571 | Vivek Dhedhi'
        (
            re.compile(
                r"^(?P<id>[A-Za-z0-9\-_/]+)\s*[\-–—|,/]\s*(?P<name>[A-Za-z\s.\'\-]+)"
            ),
            True,
        ),
        # 4. ID in parentheses/brackets followed by Name: '(92400120571) Vivek Dhedhi'
        (
            re.compile(
                r"^[\(\[]\s*(?P<id>[A-Za-z0-9\-_/]+)\s*[\)\]]\s*(?P<name>[A-Za-z\s.\'\-]+)"
            ),
            True,
        ),
        # 5. Name followed by pure digits with whitespace: 'Vivek Dhedhi 92400120571'
        (
            re.compile(
                r"^(?P<name>[A-Za-z\s.\'\-]+?)\s{1,4}(?P<id>\d{6,16})(?:\s+|$)"
            ),
            False,
        ),
    ]

    @classmethod
    def is_academic_term(cls, text: str) -> bool:
        """Determines if a candidate string matches or contains academic stop words."""
        norm = text.lower().strip()
        # Direct exact match
        if norm in cls.ACADEMIC_STOP_WORDS:
            return True
        # Substring / phrase match
        for stop_term in cls.ACADEMIC_STOP_WORDS:
            # Check whole-word or boundary match for short stop terms, substring for phrases
            if len(stop_term.split()) > 1:
                if stop_term in norm:
                    return True
            else:
                if re.search(rf"\b{re.escape(stop_term)}\b", norm):
                    return True
        return False

    @classmethod
    def is_valid_student_name(
        cls,
        name_candidate: str,
        allow_single_token: bool = False,
    ) -> tuple[bool, str]:
        """Validates that a string is a plausible student name."""
        val = name_candidate.strip()
        if not val:
            return False, "Candidate is empty"

        # Character length constraints
        if len(val) < 2 or len(val) > 45:
            return False, f"Name length ({len(val)}) outside expected bounds"

        # Must not contain digits
        if any(c.isdigit() for c in val):
            return False, "Name contains digits"

        # Must only contain letters, spaces, dots, hyphens, apostrophes
        if not re.match(r"^[A-Za-z\s.\'\-]+$", val):
            return False, "Name contains invalid characters"

        # Token count: Student names require at least 2 tokens, or 1 token if concatenated/single in footer
        raw_tokens = re.split(r"[\s.\-]+", val)
        tokens = [t for t in raw_tokens if t]
        if not allow_single_token and len(tokens) < 2:
            return False, f"Name requires at least two tokens (found {len(tokens)})"
        if len(tokens) > 5:
            return False, f"Name contains suspiciously many tokens ({len(tokens)})"

        # Check against academic stop words
        if cls.is_academic_term(val):
            return False, f"Name contains academic non-name term: '{val}'"

        return True, "Valid student name candidate"

    @classmethod
    def is_page_number_text(
        cls,
        text: str,
        bbox: Optional[BoundingBox] = None,
        page_width: Optional[float] = None,
    ) -> bool:
        """Determines if a text string represents a document page number."""
        clean = text.strip()
        if not clean:
            return False

        # Explicit page patterns (e.g., 'Page 1', 'Page 1 of 5', '1 / 5', '- 1 -')
        if re.search(r"(?i)\b(?:page|pg\.?)\s*\d+", clean):
            return True
        if re.search(r"(?i)\b\d+\s*(?:of|/)\s*\d+\b", clean):
            return True
        if re.match(r"^[\-–—]\s*\d+\s*[\-–—]$", clean):
            return True

        # Short isolated numbers (1-4 digits)
        if clean.isdigit() and len(clean) <= 4:
            # If positioned in center or right half of the page: definitely page number
            if bbox is not None and page_width is not None:
                if bbox.x0 >= page_width * 0.40:
                    return True
            # Isolated short numbers without name pairing
            return True

        return False

    @classmethod
    def classify_identifier(
        cls,
        id_raw: str,
        bbox: Optional[BoundingBox] = None,
        page_width: Optional[float] = None,
    ) -> tuple[Optional[FieldType], str]:
        """Classifies a candidate identifier token into enrollment, roll number, or unknown."""
        cleaned = id_raw.strip()
        if not cleaned:
            return None, "Empty identifier"

        # Never classify page numbers as student identifiers
        if cls.is_page_number_text(cleaned, bbox=bbox, page_width=page_width):
            return None, "Classified as page number"

        # Enrollment Number: Pure digits with standard length (6 to 18 digits)
        if cleaned.isdigit():
            if len(cleaned) >= 6:
                return FieldType.ENROLLMENT_NUMBER, "Numeric enrollment number"
            elif 1 <= len(cleaned) <= 4:
                return FieldType.ROLL_NUMBER, "Numeric roll number"

        # Alphanumeric Roll Number patterns (e.g., '21CS045', 'IT-2023-089', 'CS-25')
        if re.match(
            r"^(?:[A-Za-z]{1,5}-?[0-9]{1,5}|[0-9]{2}[A-Za-z]{2,6}-?[0-9]{1,6}|[A-Za-z]{2,5}[0-9]{2,6})$",
            cleaned,
        ):
            return FieldType.ROLL_NUMBER, "Alphanumeric roll number"

        # Standard alphanumeric enrollment number (e.g. 'BE-2024-0012', 'ENR-92400120571')
        if re.match(r"^[A-Za-z0-9\-_/]{6,25}$", cleaned) and any(c.isdigit() for c in cleaned):
            digits_count = sum(1 for c in cleaned if c.isdigit())
            if digits_count >= 8:
                return FieldType.ENROLLMENT_NUMBER, "Alphanumeric enrollment number"
            elif any(
                prefix in cleaned.upper()
                for prefix in ["CS", "IT", "EC", "ME", "CE", "EE", "ROLL", "STUD"]
            ):
                return FieldType.ROLL_NUMBER, "Roll number format"
            else:
                return FieldType.UNKNOWN_IDENTIFIER, "Ambiguous student identifier"

        return None, "Unrecognized identifier format"

    @classmethod
    def detect_in_line(
        cls,
        line: StructuredLine,
        page: pymupdf.Page,
        separator_y: Optional[float] = None,
    ) -> list[ExtractedFieldValue]:
        """Detects unlabelled student identity pairs in a text line.

        Emits separate ExtractedFieldValue instances for the name and the identifier,
        each with precise, strictly non-overlapping bounding boxes.

        Args:
            line: The candidate StructuredLine to inspect.
            page: Open PyMuPDF Page object for coordinate resolution.
            separator_y: Optional Y coordinate of horizontal separator line.

        Returns:
            List of ExtractedFieldValue instances (usually [name_field, id_field] or []).
        """
        line_text = line.text.strip()
        if not line_text:
            return []

        page_width = page.rect.width
        page_height = page.rect.height

        # Discard lines that are pure page numbers
        if cls.is_page_number_text(line_text, bbox=line.bbox, page_width=page_width):
            return []

        # Assess position attributes
        is_bottom_left = FooterDetector.is_bottom_left(
            bbox=line.bbox,
            page_width=page_width,
            page_height=page_height,
        )
        is_near_sep = FooterDetector.is_near_separator_line(
            bbox=line.bbox,
            separator_y=separator_y,
        )

        # Test each identity pattern
        matched_pair: Optional[UnlabelledMatch] = None

        for pattern, is_inverted in cls.IDENTITY_PATTERNS:
            match = pattern.search(line_text)
            if not match:
                continue

            name_raw = match.group("name").strip()
            id_raw = match.group("id").strip()

            # Classify identifier
            id_type, _ = cls.classify_identifier(
                id_raw, bbox=line.bbox, page_width=page_width
            )
            if id_type is None:
                continue

            # Validate name candidate (allow single-token / concatenated names in bottom-left footer)
            is_valid_name, _ = cls.is_valid_student_name(
                name_raw,
                allow_single_token=is_bottom_left or True,
            )

            # Locate character offsets within line.text
            n_start = line.text.find(name_raw) if is_valid_name else -1
            n_end = n_start + len(name_raw) if is_valid_name else -1
            i_start = line.text.find(id_raw)
            i_end = i_start + len(id_raw)

            matched_pair = UnlabelledMatch(
                name=name_raw if is_valid_name else "",
                identifier=id_raw,
                id_field_type=id_type,
                name_start=n_start,
                name_end=n_end,
                id_start=i_start,
                id_end=i_end,
                is_inverted=is_inverted,
            )
            break

        # Standalone enrollment number detection in bottom-left corner
        if not matched_pair and is_bottom_left:
            standalone_match = re.search(
                r"(?:^|[\s\(\[\{\-–—|,/])(?P<id>\d{6,18}|[0-9]{2}[A-Za-z]{2,5}[0-9]{3,8})(?:[\)\]\}\s\-–—|,/]|$)",
                line_text,
            )
            if standalone_match:
                id_raw = standalone_match.group("id").strip()
                id_type, _ = cls.classify_identifier(
                    id_raw, bbox=line.bbox, page_width=page_width
                )
                if id_type is not None:
                    i_start = line.text.find(id_raw)
                    i_end = i_start + len(id_raw)
                    matched_pair = UnlabelledMatch(
                        name="",
                        identifier=id_raw,
                        id_field_type=id_type,
                        name_start=-1,
                        name_end=-1,
                        id_start=i_start,
                        id_end=i_end,
                        is_inverted=False,
                    )

        if not matched_pair:
            return []

        # Resolve ID bounding box
        id_bbox = TextSegmenter.resolve_substring_bbox(
            page=page,
            substring=matched_pair.identifier,
            line=line,
            start_char=matched_pair.id_start,
            end_char=matched_pair.id_end,
        )

        # Build Occurrence for Identifier
        pair_key = (
            f"pair_p{line.page_number}_b{line.block_number}_l{line.line_number}"
            if matched_pair.name
            else None
        )
        id_occurrence = FieldOccurrence(
            page_number=line.page_number,
            bbox=id_bbox,
            value_bbox=id_bbox,
            label_bbox=None,
            block_number=line.block_number,
            line_number=line.line_number,
            span_information=line.spans,
            raw_text=line.text,
            matched_label="",
            is_in_footer_region=line.is_in_footer,
            line_bbox=line.bbox,
            pair_id=pair_key,
        )

        id_extracted = ExtractedFieldValue(
            field_type=matched_pair.id_field_type,
            matched_label="",
            value=matched_pair.identifier,
            is_ambiguous=False,
            ambiguity_reason=None,
            occurrence=id_occurrence,
            is_unlabelled=True,
            is_near_separator_line=is_near_sep,
            is_bottom_left=is_bottom_left,
        )

        results: list[ExtractedFieldValue] = [id_extracted]

        # Resolve Name bounding box if present and valid
        if matched_pair.name:
            name_bbox = TextSegmenter.resolve_substring_bbox(
                page=page,
                substring=matched_pair.name,
                line=line,
                start_char=matched_pair.name_start,
                end_char=matched_pair.name_end,
            )

            # Enforce strict non-overlapping bounding boxes
            name_bbox, id_bbox = cls._ensure_non_overlapping_boxes(
                name_bbox=name_bbox,
                id_bbox=id_bbox,
                is_inverted=matched_pair.is_inverted,
            )
            # Update id occurrence with clamped bbox
            id_occurrence = FieldOccurrence(
                page_number=line.page_number,
                bbox=id_bbox,
                value_bbox=id_bbox,
                label_bbox=None,
                block_number=line.block_number,
                line_number=line.line_number,
                span_information=line.spans,
                raw_text=line.text,
                matched_label="",
                is_in_footer_region=line.is_in_footer,
                line_bbox=line.bbox,
                pair_id=pair_key,
            )
            id_extracted.occurrence = id_occurrence

            name_occurrence = FieldOccurrence(
                page_number=line.page_number,
                bbox=name_bbox,
                value_bbox=name_bbox,
                label_bbox=None,
                block_number=line.block_number,
                line_number=line.line_number,
                span_information=line.spans,
                raw_text=line.text,
                matched_label="",
                is_in_footer_region=line.is_in_footer,
                line_bbox=line.bbox,
                pair_id=pair_key,
            )

            name_extracted = ExtractedFieldValue(
                field_type=FieldType.STUDENT_NAME,
                matched_label="",
                value=matched_pair.name,
                is_ambiguous=False,
                ambiguity_reason=None,
                occurrence=name_occurrence,
                is_unlabelled=True,
                is_near_separator_line=is_near_sep,
                is_bottom_left=is_bottom_left,
            )

            results.insert(0, name_extracted)

        return results

    @classmethod
    def scan_bottom_left_for_enrollment(
        cls,
        doc: pymupdf.Document,
    ) -> list[ExtractedFieldValue]:
        """Dedicated recovery scan targeting the left-bottom corner of each page.

        If no enrollment number was detected during standard passes, this method
        scans the left-bottom quadrant (x <= 48% of page width, y >= 60% of page height)
        for any isolated or bracketed enrollment number token (6 to 18 digits).

        Args:
            doc: Open PyMuPDF Document instance.

        Returns:
            List of ExtractedFieldValue instances for the recovered enrollment number.
        """
        recovered_values: list[ExtractedFieldValue] = []

        for page_idx, page in enumerate(doc, start=1):
            page_width = page.rect.width
            page_height = page.rect.height
            min_y = page_height * 0.60
            max_x = page_width * 0.48

            separator_y = FooterDetector.find_footer_separator_line(page)
            structured_lines = TextSegmenter.segment_page(page, page_number=page_idx)

            for line in structured_lines:
                if line.bbox.y0 < min_y or line.bbox.x0 > max_x:
                    continue

                line_text = line.text.strip()
                if not line_text:
                    continue

                if cls.is_page_number_text(line_text, bbox=line.bbox, page_width=page_width):
                    continue

                # Search for 6-18 digit enrollment number token
                match = re.search(
                    r"(?:^|[\s\(\[\{\-–—|,/])(?P<id>\d{6,18})(?:[\)\]\}\s\-–—|,/]|$)",
                    line_text,
                )
                if not match:
                    continue

                id_raw = match.group("id").strip()
                id_type, _ = cls.classify_identifier(
                    id_raw, bbox=line.bbox, page_width=page_width
                )
                if id_type != FieldType.ENROLLMENT_NUMBER:
                    continue

                i_start = line.text.find(id_raw)
                i_end = i_start + len(id_raw)
                id_bbox = TextSegmenter.resolve_substring_bbox(
                    page=page,
                    substring=id_raw,
                    line=line,
                    start_char=i_start,
                    end_char=i_end,
                )

                is_near_sep = FooterDetector.is_near_separator_line(
                    bbox=line.bbox,
                    separator_y=separator_y,
                )

                id_occurrence = FieldOccurrence(
                    page_number=line.page_number,
                    bbox=id_bbox,
                    value_bbox=id_bbox,
                    label_bbox=None,
                    block_number=line.block_number,
                    line_number=line.line_number,
                    span_information=line.spans,
                    raw_text=line.text,
                    matched_label="",
                    is_in_footer_region=line.is_in_footer,
                    line_bbox=line.bbox,
                )

                id_extracted = ExtractedFieldValue(
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    matched_label="",
                    value=id_raw,
                    is_ambiguous=False,
                    ambiguity_reason=None,
                    occurrence=id_occurrence,
                    is_unlabelled=True,
                    is_near_separator_line=is_near_sep,
                    is_bottom_left=True,
                )

                recovered_values.append(id_extracted)

        return recovered_values

    @classmethod
    def _ensure_non_overlapping_boxes(
        cls,
        name_bbox: BoundingBox,
        id_bbox: BoundingBox,
        is_inverted: bool,
    ) -> tuple[BoundingBox, BoundingBox]:
        """Guarantees that the name and identifier bounding boxes do not overlap."""
        rect_name = pymupdf.Rect(name_bbox.to_tuple())
        rect_id = pymupdf.Rect(id_bbox.to_tuple())

        # If they don't intersect, retain original tight bounds
        if not rect_name.intersects(rect_id):
            return name_bbox, id_bbox

        # If overlapping due to glyph interpolation, partition along boundary
        if not is_inverted:
            # Name comes before ID horizontally
            mid_x = (name_bbox.x1 + id_bbox.x0) / 2.0
            new_name_box = BoundingBox(
                x0=name_bbox.x0,
                y0=name_bbox.y0,
                x1=min(name_bbox.x1, mid_x - 1.0),
                y1=name_bbox.y1,
            )
            new_id_box = BoundingBox(
                x0=max(id_bbox.x0, mid_x + 1.0),
                y0=id_bbox.y0,
                x1=id_bbox.x1,
                y1=id_bbox.y1,
            )
        else:
            # ID comes before Name horizontally
            mid_x = (id_bbox.x1 + name_bbox.x0) / 2.0
            new_id_box = BoundingBox(
                x0=id_bbox.x0,
                y0=id_bbox.y0,
                x1=min(id_bbox.x1, mid_x - 1.0),
                y1=id_bbox.y1,
            )
            new_name_box = BoundingBox(
                x0=max(name_bbox.x0, mid_x + 1.0),
                y0=name_bbox.y0,
                x1=name_bbox.x1,
                y1=name_bbox.y1,
            )

        return new_name_box, new_id_box

