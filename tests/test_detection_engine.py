"""Automated test suite for DocMorph Phase 2 Intelligent Detection Engine.

Covers:
- Footer region detection (A4, landscape, custom dimensions, adaptive boundaries, empty footers)
- Student field label detection (name, enrollment, roll, student_id, casing, negative filters)
- Value extraction (single-word, multi-word, numeric, alphanumeric, multi-line, delimiters)
- Multi-page repeated fields and cross-page conflict detection
- Confidence scoring and explainability
- Human-in-the-loop manual review mutations (confirm, correct, reject, change type)
- CLI execution with --detect flag
"""

from pathlib import Path
import subprocess
import sys
import pytest
import pymupdf

from app.schemas.detection_data import (
    BoundingBox,
    ConfidenceLevel,
    DetectionResult,
    FieldType,
    ReviewStatus,
)
from app.services.confidence_scorer import ConfidenceScorer
from app.services.detection_engine import DetectionEngine
from app.services.field_detector import FieldDetector
from app.services.footer_detector import FooterDetector
from app.services.value_extractor import ValueExtractor


# ==============================================================================
# SECTION 1: FOOTER REGION DETECTION TESTS
# ==============================================================================

class TestFooterDetection:
    """Test suite for geometric footer region detection across various page layouts."""

    def test_standard_a4_portrait(self) -> None:
        """Verifies footer boundary calculation on standard A4 portrait (595 x 842)."""
        detector = FooterDetector()
        boundary_y = detector.get_footer_boundary_y(page_height=842.0, ratio=0.20)
        # Bottom 20% starts at 842 * 0.8 = 673.6
        assert boundary_y == pytest.approx(673.6, rel=1e-2)

        # Region bbox
        region = detector.get_footer_region(page_width=595.0, page_height=842.0)
        assert region.x0 == 0.0
        assert region.y0 == pytest.approx(673.6, rel=1e-2)
        assert region.x1 == 595.0
        assert region.y1 == 842.0

        # Point in footer vs body
        assert detector.is_in_footer(BoundingBox(x0=50, y0=790, x1=200, y1=802), 842.0) is True
        assert detector.is_in_footer(BoundingBox(x0=50, y0=100, x1=200, y1=120), 842.0) is False

    def test_landscape_pdf(self, detection_engine: DetectionEngine, landscape_pdf: Path) -> None:
        """Verifies footer detection on landscape PDF where width > height (842 x 595)."""
        res = detection_engine.detect_file(landscape_pdf)
        assert res.total_pages == 1
        assert len(res.detected_fields) >= 3

        # Verify fields were found in the landscape footer region
        field_types = {f.field_type for f in res.detected_fields}
        assert FieldType.STUDENT_NAME in field_types
        assert FieldType.ENROLLMENT_NUMBER in field_types
        assert FieldType.ROLL_NUMBER in field_types

    def test_custom_page_dimensions(self) -> None:
        """Verifies footer detection on non-standard page dimensions (US Letter: 612 x 792)."""
        detector = FooterDetector()
        region = detector.get_footer_region(page_width=612.0, page_height=792.0, ratio=0.25)
        # Bottom 25% of 792 starts at 792 * 0.75 = 594.0
        assert region.y0 == pytest.approx(594.0, rel=1e-2)
        assert region.width == 612.0

    def test_document_without_footer(
        self, detection_engine: DetectionEngine, no_footer_pdf: Path
    ) -> None:
        """Verifies that a document containing only body text yields 0 student fields."""
        res = detection_engine.detect_file(no_footer_pdf)
        assert res.detection_summary.total_fields_detected == 0
        assert len(res.detected_fields) == 0

    def test_bottom_content_that_is_not_personal_information(
        self, detection_engine: DetectionEngine, no_footer_pdf: Path
    ) -> None:
        """Verifies that generic text like 'Page 1 of 1' at bottom is not classified as student data."""
        res = detection_engine.detect_file(no_footer_pdf)
        assert len(res.detected_fields) == 0
        assert res.detection_summary.total_fields_detected == 0


# ==============================================================================
# SECTION 2: FIELD LABEL DETECTION TESTS
# ==============================================================================

class TestFieldLabelDetection:
    """Test suite for recognizing student field labels across variations."""

    def test_student_name_label_variations(self) -> None:
        """Verifies that variations of student name labels are recognized."""
        samples = [
            "Student Name: Rahul",
            "Name of Student: Rahul",
            "Student's Name: Rahul",
            "Student: Rahul",
            "Name: Rahul",
            "Candidate Name: Rahul",
            "Learner Name: Rahul",
            "STUDENT FULL NAME: Rahul",
        ]
        for s in samples:
            labels = FieldDetector.find_field_labels(s)
            assert len(labels) >= 1, f"Failed on sample: {s}"
            assert labels[0].field_type == FieldType.STUDENT_NAME

    def test_enrollment_number_label_variations(self) -> None:
        """Verifies recognition of enrollment number variations and spellings."""
        samples = [
            "Enrollment No: 2300012345",
            "Enrollment Number: 2300012345",
            "Enrolment No: 2300012345",
            "Enrolment Number: 2300012345",
            "Enrollment ID: 2300012345",
            "Enroll No: 2300012345",
            "Enrollment# 2300012345",
            "ENROLLMENT NO.: 2300012345",
        ]
        for s in samples:
            labels = FieldDetector.find_field_labels(s)
            assert len(labels) >= 1, f"Failed on sample: {s}"
            assert labels[0].field_type == FieldType.ENROLLMENT_NUMBER

    def test_roll_number_label_variations(self) -> None:
        """Verifies recognition of roll number variations."""
        samples = [
            "Roll No: 25",
            "Roll Number: 25",
            "Roll No.: 25",
            "Roll# 25",
            "Class Roll No: 25",
            "Exam Roll No: 25",
            "ROLL NO: 25",
        ]
        for s in samples:
            labels = FieldDetector.find_field_labels(s)
            assert len(labels) >= 1, f"Failed on sample: {s}"
            assert labels[0].field_type == FieldType.ROLL_NUMBER

    def test_student_id_label_variations(self) -> None:
        """Verifies recognition of student id variations."""
        samples = [
            "Student ID: STU2026",
            "Student Identification Number: STU2026",
            "StudentID: STU2026",
            "Stud ID: STU2026",
            "Student No: STU2026",
            "STUDENT ID: STU2026",
        ]
        for s in samples:
            labels = FieldDetector.find_field_labels(s)
            assert len(labels) >= 1, f"Failed on sample: {s}"
            assert labels[0].field_type == FieldType.STUDENT_ID

    def test_negative_context_filtering(self) -> None:
        """Verifies that non-student phrases with the word 'Name' are rejected."""
        false_positives = [
            "File Name: document.pdf",
            "Algorithm Name: BFS",
            "Faculty Name: Prof. Sharma",
            "Teacher Name: Dr. Patel",
            "Instructor Name: Dr. Dave",
            "Department Name: Computer Science",
            "College Name: Gujarat Tech",
            "Project Name: DocMorph",
            "Experiment Name: Binary Trees",
            "Module Name: Architecture",
        ]
        for fp in false_positives:
            labels = FieldDetector.find_field_labels(fp)
            assert len(labels) == 0, f"False positive detected on: {fp}"

    def test_multiple_fields_on_same_line(self) -> None:
        """Verifies that multiple student labels on a single line are all identified."""
        line = "Student Name: Rahul Patel | Enrollment No: 2300012345 | Roll No: 25"
        labels = FieldDetector.find_field_labels(line)
        assert len(labels) == 3
        assert labels[0].field_type == FieldType.STUDENT_NAME
        assert labels[1].field_type == FieldType.ENROLLMENT_NUMBER
        assert labels[2].field_type == FieldType.ROLL_NUMBER


# ==============================================================================
# SECTION 3: VALUE EXTRACTION TESTS
# ==============================================================================

class TestValueExtraction:
    """Test suite for extracting and validating values."""

    def test_single_and_multi_word_name_formats(self) -> None:
        """Verifies person name format validation."""
        valid, _ = ValueExtractor.validate_format(FieldType.STUDENT_NAME, "Rahul")
        assert valid is True
        valid, _ = ValueExtractor.validate_format(FieldType.STUDENT_NAME, "Rahul Patel")
        assert valid is True
        valid, _ = ValueExtractor.validate_format(FieldType.STUDENT_NAME, "A. B. Sharma")
        assert valid is True

        # Names with numbers or symbols should fail format validation
        invalid, _ = ValueExtractor.validate_format(FieldType.STUDENT_NAME, "Rahul123")
        assert invalid is False

    def test_numeric_enrollment_formats(self) -> None:
        """Verifies enrollment format validation."""
        valid, _ = ValueExtractor.validate_format(FieldType.ENROLLMENT_NUMBER, "2300012345")
        assert valid is True
        valid, _ = ValueExtractor.validate_format(FieldType.ENROLLMENT_NUMBER, "BE-2024-0012")
        assert valid is True

        # Pure letters or too short
        invalid, _ = ValueExtractor.validate_format(FieldType.ENROLLMENT_NUMBER, "abc")
        assert invalid is False

    def test_multiline_field_association(
        self, detection_engine: DetectionEngine, multiline_field_pdf: Path
    ) -> None:
        """Verifies extracting a value located on the line directly below the label."""
        res = detection_engine.detect_file(multiline_field_pdf)
        name_fields = [f for f in res.detected_fields if f.field_type == FieldType.STUDENT_NAME]
        assert len(name_fields) == 1
        assert name_fields[0].suggested_value == "Rahul Patel"

    def test_varied_labels_pdf_extraction(
        self, detection_engine: DetectionEngine, varied_labels_pdf: Path
    ) -> None:
        """Verifies end-to-end extraction across lowercase, uppercase, and hyphenated labels."""
        res = detection_engine.detect_file(varied_labels_pdf)
        field_dict = {f.field_type: f.suggested_value for f in res.detected_fields}

        assert field_dict.get(FieldType.STUDENT_NAME) == "Rahul Patel"
        assert field_dict.get(FieldType.ENROLLMENT_NUMBER) == "2300012345"
        assert field_dict.get(FieldType.ROLL_NUMBER) == "25"
        assert field_dict.get(FieldType.STUDENT_ID) == "STU20260025"

    def test_ambiguous_and_missing_values(
        self, detection_engine: DetectionEngine, ambiguous_field_pdf: Path
    ) -> None:
        """Verifies that missing values or non-standard formats trigger review_required."""
        res = detection_engine.detect_file(ambiguous_field_pdf)
        # Should have fields marked review_required
        assert res.detection_summary.review_required_count >= 1

        name_field = next(
            (f for f in res.detected_fields if f.field_type == FieldType.STUDENT_NAME), None
        )
        if name_field:
            assert name_field.review_required is True


# ==============================================================================
# SECTION 4: MULTI-PAGE REPETITION & CONFLICT DETECTION TESTS
# ==============================================================================

class TestRepetitionAndConflicts:
    """Test suite for grouping repeated occurrences and detecting cross-page conflicts."""

    def test_repeated_values_across_all_pages(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies 5-page PDF groups same student credentials into 1 field each with 5 occurrences."""
        res = detection_engine.detect_file(sample_practical_pdf)

        assert len(res.detected_fields) == 3
        for f in res.detected_fields:
            assert len(f.occurrences) == 5
            page_numbers = [occ.page_number for occ in f.occurrences]
            assert page_numbers == [1, 2, 3, 4, 5]
            # Each occurrence has non-empty bounding boxes
            for occ in f.occurrences:
                assert occ.bbox.area > 0
                assert occ.value_bbox is not None and occ.value_bbox.area > 0

    def test_conflicting_values_across_pages_reported(
        self, detection_engine: DetectionEngine, conflicting_pdf: Path
    ) -> None:
        """Verifies that different student names across pages trigger conflict reporting."""
        res = detection_engine.detect_file(conflicting_pdf)

        # There should be at least one registered conflict
        assert len(res.conflicts) >= 1
        name_conflict = next(
            (c for c in res.conflicts if c.field_type == FieldType.STUDENT_NAME), None
        )
        assert name_conflict is not None
        assert "Rahul Patel" in name_conflict.conflicting_values
        assert "Aarav Shah" in name_conflict.conflicting_values
        assert 1 in name_conflict.pages
        assert 3 in name_conflict.pages

        # Both conflicting fields must be flagged for review
        name_fields = [f for f in res.detected_fields if f.field_type == FieldType.STUDENT_NAME]
        for nf in name_fields:
            assert nf.review_required is True


# ==============================================================================
# SECTION 5: CONFIDENCE SCORING & EXPLAINABILITY TESTS
# ==============================================================================

class TestConfidenceScoring:
    """Test suite for multi-factor confidence calculations and reasons."""

    def test_high_confidence_for_clean_repeated_footer(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies clean, repeated, footer-located fields receive High confidence (0.90 - 1.00)."""
        res = detection_engine.detect_file(sample_practical_pdf)
        for field in res.detected_fields:
            assert field.confidence >= 0.90
            assert field.confidence_level == ConfidenceLevel.HIGH
            assert len(field.confidence_reasons) >= 3

    def test_confidence_reasons_contain_specific_details(self) -> None:
        """Verifies explainable reasons describe label, format, location, and repetition."""
        scorer = ConfidenceScorer()
        res = scorer.score_field(
            field_type=FieldType.STUDENT_NAME,
            matched_label="Student Name",
            is_specific_label=True,
            value="Rahul Patel",
            is_in_footer=True,
            occurrence_count=5,
            total_pages=5,
        )
        assert res.score == 1.00
        assert res.level == ConfidenceLevel.HIGH
        reasons_text = " ".join(res.reasons)
        assert "Explicit student label" in reasons_text
        assert "Valid person name" in reasons_text
        assert "footer region" in reasons_text
        assert "5 pages" in reasons_text


# ==============================================================================
# SECTION 6: HUMAN-IN-THE-LOOP MANUAL REVIEW TESTS
# ==============================================================================

class TestManualReviewMutations:
    """Test suite for confirming, correcting, rejecting, and updating field detections."""

    def test_confirm_field(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies confirming a field sets status to CONFIRMED."""
        res = detection_engine.detect_file(sample_practical_pdf)
        target_field = res.detected_fields[0]
        field_id = target_field.field_id

        res.confirm_field(field_id)
        updated = res.get_field(field_id)
        assert updated.status == ReviewStatus.CONFIRMED
        assert updated.review_required is False

    def test_correct_field_preserves_original_value(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies correcting value updates suggested_value while strictly preserving original_value."""
        res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(
            f for f in res.detected_fields if f.field_type == FieldType.STUDENT_NAME
        )
        field_id = name_field.field_id
        original = name_field.original_value

        res.correct_field(field_id, new_value="Smit Patel")
        updated = res.get_field(field_id)

        assert updated.status == ReviewStatus.CORRECTED
        assert updated.suggested_value == "Smit Patel"
        assert updated.original_value == original  # Original MUST remain unchanged!

    def test_reject_field(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies rejecting a field sets status to REJECTED."""
        res = detection_engine.detect_file(sample_practical_pdf)
        target_field = res.detected_fields[0]
        field_id = target_field.field_id

        res.reject_field(field_id)
        updated = res.get_field(field_id)
        assert updated.status == ReviewStatus.REJECTED

    def test_change_field_type(
        self, detection_engine: DetectionEngine, sample_practical_pdf: Path
    ) -> None:
        """Verifies changing field type updates field_type and marks as corrected."""
        res = detection_engine.detect_file(sample_practical_pdf)
        field = res.detected_fields[0]
        field_id = field.field_id

        res.change_field_type(field_id, FieldType.STUDENT_ID)
        updated = res.get_field(field_id)
        assert updated.field_type == FieldType.STUDENT_ID
        assert updated.status == ReviewStatus.CORRECTED


# ==============================================================================
# SECTION 7: CLI EXECUTION WITH --DETECT
# ==============================================================================

class TestCLIDetectionExecution:
    """Test suite for CLI execution in Phase 2 detection mode."""

    def test_cli_detect_flag(self, sample_practical_pdf: Path) -> None:
        """Verifies python -m app.main <file> --detect outputs formatted detection report."""
        cmd = [sys.executable, "-m", "app.main", str(sample_practical_pdf), "--detect"]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        output = proc.stdout
        assert "DOCMORPH" in output
        assert "INTELLIGENT DETECTION ENGINE" in output
        assert "Rahul Patel" in output
        assert "2300012345" in output
        assert "Roll No" in output or "roll_number" in output
        assert "Intelligent detection completed successfully." in output

    def test_cli_detect_json(self, sample_practical_pdf: Path) -> None:
        """Verifies python -m app.main <file> --detect --json outputs valid DetectionResult JSON."""
        cmd = [sys.executable, "-m", "app.main", str(sample_practical_pdf), "--detect", "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        import json
        data = json.loads(proc.stdout)
        assert "document_id" in data
        assert "detected_fields" in data
        assert len(data["detected_fields"]) == 3

