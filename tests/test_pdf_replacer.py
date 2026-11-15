"""Automated test suite for DocMorph Phase 3 PDF Personalization Engine.

Covers:
- Basic replacements (student_name, enrollment_number, roll_number, student_id)
- Multi-page document replacements across all occurrences
- Formatting preservation and adaptive font scaling for long values
- Collision detection when replacement text exceeds available clearance
- Document integrity & immutability (SHA-256 hash check, purging old text)
- Safety rules (unconfirmed / rejected fields, empty values, coordinate checks)
- Output verification assertions
- CLI personalization commands
"""

import hashlib
from pathlib import Path
import subprocess
import sys
import pytest
import pymupdf

from app.core.exceptions import (
    FieldNotFoundError,
    InvalidBoundingBoxError,
    InvalidReplacementRequestError,
    UnconfirmedFieldError,
)
from app.schemas.detection_data import (
    BoundingBox,
    DetectionResult,
    FieldOccurrence,
    FieldType,
    ReviewStatus,
)
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementRequest,
    ReplacementResult,
    ReplacementStatus,
    VerificationStatus,
)
from app.services.detection_engine import DetectionEngine
from app.services.pdf_replacer import PDFReplacer
from tests.conftest import compute_file_sha256


# ==============================================================================
# SECTION 1: BASIC FIELD REPLACEMENTS
# ==============================================================================

class TestBasicReplacement:
    """Test suite for fundamental student credential replacements."""

    def test_replace_student_name(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies replacing student name updates the document and verifies cleanly."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value="Vivek Dhedhi",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(
            source_pdf=sample_practical_pdf,
            detection_result=det_res,
            request=req,
            output_dir=tmp_path,
        )

        assert res.total_requested == 1
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED

        # Check content in generated output
        with pymupdf.open(res.output_path) as out_doc:
            assert out_doc.page_count == 5
            for page in out_doc:
                assert "Vivek Dhedhi" in page.get_text("text")
                assert "Rahul Patel" not in page.get_text("text")

    def test_replace_enrollment_number(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies enrollment number replacement."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        enroll_field = next(
            f for f in det_res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER
        )
        enroll_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=enroll_field.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=enroll_field.original_value,
                    new_value="2400015678",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED

        with pymupdf.open(res.output_path) as out_doc:
            for page in out_doc:
                assert "2400015678" in page.get_text("text")
                assert "2300012345" not in page.get_text("text")

    def test_replace_roll_number(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies roll number replacement."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        roll_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.ROLL_NUMBER)
        roll_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=roll_field.field_id,
                    field_type=FieldType.ROLL_NUMBER,
                    original_value=roll_field.original_value,
                    new_value="42",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED

    def test_replace_student_id(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        varied_labels_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies student_id replacement."""
        det_res = detection_engine.detect_file(varied_labels_pdf)
        id_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_ID)
        id_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(varied_labels_pdf),
            replacements=[
                ReplacementItem(
                    field_id=id_field.field_id,
                    field_type=FieldType.STUDENT_ID,
                    original_value=id_field.original_value,
                    new_value="STU-9999",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(varied_labels_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED

        with pymupdf.open(res.output_path) as out_doc:
            assert "STU-9999" in out_doc[0].get_text("text")

    def test_replace_multiple_fields_simultaneously(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies replacing name, enrollment, and roll number simultaneously across all pages."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        for f in det_res.detected_fields:
            f.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id="student_name_1",
                    field_type=FieldType.STUDENT_NAME,
                    original_value="Rahul Patel",
                    new_value="Vivek Dhedhi",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id="enrollment_number_2",
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value="2300012345",
                    new_value="2400015678",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id="roll_number_3",
                    field_type=FieldType.ROLL_NUMBER,
                    original_value="25",
                    new_value="42",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_requested == 3
        assert res.total_successful == 3
        assert res.successful_occurrences == 15
        assert res.verification_status == VerificationStatus.PASSED


# ==============================================================================
# SECTION 2: MULTI-PAGE REPLACEMENT & LAYOUTS
# ==============================================================================

class TestMultiPageReplacement:
    """Test suite for multi-page occurrence processing and layout variations."""

    def test_same_field_across_five_pages(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies all 5 pages are updated with occurrence results recorded for each page."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value="Aarav Sharma",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert len(res.occurrence_results) == 5

        observed_pages = [occ.page_number for occ in res.occurrence_results]
        assert observed_pages == [1, 2, 3, 4, 5]

    def test_landscape_pdf_replacement(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        landscape_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies replacement in landscape documents (842x595)."""
        det_res = detection_engine.detect_file(landscape_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(landscape_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value="Aarav Patel",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(landscape_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED


# ==============================================================================
# SECTION 3: FORMATTING AND TEXT FITTING
# ==============================================================================

class TestFormattingAndTextFitting:
    """Test suite for typography preservation and text length handling."""

    def test_longer_replacement_adaptive_scaling(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies that longer replacement values scale font size down to fit available width."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        # Longer name that requires scaling (65pt vs 46.5pt original; fits when scaled)
        longer_name = "Vivek K. Dhedhi"
        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value=longer_name,
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED

        # Should have generated scaling warnings
        assert any("scaled" in w.lower() for w in res.warnings)

    def test_text_collision_when_scaling_below_minimum(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies collision detection when text is so long it would scale below MIN_REPLACEMENT_FONT_SIZE."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        # Ultra long name that cannot fit within 47pt even at 6.0pt
        ultra_long = "Dr. Alexander Montgomery Bartholomew III"
        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value=ultra_long,
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        # Should record failure due to collision rather than corrupting layout
        assert res.total_failed == 1
        assert any("exceeding available width" in w.lower() or "scales below min" in w.lower() for w in res.warnings)
        assert all(occ.status == ReplacementStatus.FAILED for occ in res.occurrence_results)

    def test_shorter_replacement(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies shorter replacement values fit naturally without warnings."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_field.original_value,
                    new_value="Ali",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert res.total_successful == 1
        assert res.verification_status == VerificationStatus.PASSED


# ==============================================================================
# SECTION 4: SAFETY, VALIDATION, AND INTEGRITY
# ==============================================================================

class TestSafetyAndIntegrity:
    """Test suite for immutability, coordinates, and unconfirmed field rejection."""

    def test_original_pdf_remains_unchanged(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies SHA-256 hash of original PDF is identical before and after personalization."""
        hash_before = compute_file_sha256(sample_practical_pdf)

        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="Vivek Dhedhi",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)

        hash_after = compute_file_sha256(sample_practical_pdf)
        assert hash_before == hash_after, "Original PDF was modified during personalization!"

    def test_old_value_not_extractable_at_occurrence(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies the old value is purged from the PDF text stream, not merely covered."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="New Student",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)

        with pymupdf.open(res.output_path) as out_doc:
            for page in out_doc:
                # Old value must be 0 occurrences in footers
                assert len(page.search_for("Rahul Patel")) == 0

    def test_label_and_unrelated_content_remain_intact(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies label ('Student Name:') and unrelated body paragraphs remain intact."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="New Student",
                    review_status=ReviewStatus.CONFIRMED,
                )
            ],
        )

        res = pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)

        with pymupdf.open(res.output_path) as out_doc:
            p1_text = out_doc[0].get_text("text")
            assert "Student Name:" in p1_text
            assert "Practical 1: Implementation of Stack using Arrays" in p1_text
            assert "DEPARTMENT OF COMPUTER ENGINEERING" in p1_text

    def test_unconfirmed_field_cannot_be_replaced(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies attempting to replace an unconfirmed (PENDING) field raises UnconfirmedFieldError."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        # Keep status as PENDING (unconfirmed)
        assert name_field.status == ReviewStatus.PENDING

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="New Student",
                    review_status=ReviewStatus.PENDING,  # Unconfirmed!
                )
            ],
        )

        with pytest.raises(UnconfirmedFieldError) as exc_info:
            pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert "unconfirmed" in str(exc_info.value).lower()

    def test_rejected_field_cannot_be_replaced(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies attempting to replace a REJECTED field raises UnconfirmedFieldError."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        name_field.reject()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="New Student",
                    review_status=ReviewStatus.REJECTED,
                )
            ],
        )

        with pytest.raises(UnconfirmedFieldError) as exc_info:
            pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert "rejected" in str(exc_info.value).lower()

    def test_empty_replacement_value_rejected(self) -> None:
        """Verifies empty or blank replacement value fails schema validation."""
        with pytest.raises(Exception):
            ReplacementItem(
                field_id="field_1",
                field_type=FieldType.STUDENT_NAME,
                original_value="Rahul",
                new_value="",  # Empty
            )

    def test_duplicate_replacement_request_rejected(
        self,
        pdf_replacer: PDFReplacer,
        detection_engine: DetectionEngine,
        sample_practical_pdf: Path,
        tmp_path: Path,
    ) -> None:
        """Verifies duplicate replacement items for the same field_id raise an error."""
        det_res = detection_engine.detect_file(sample_practical_pdf)
        name_field = det_res.detected_fields[0]
        name_field.confirm()

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(sample_practical_pdf),
            replacements=[
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="Name A",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id=name_field.field_id,
                    field_type=name_field.field_type,
                    original_value=name_field.original_value,
                    new_value="Name B",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        with pytest.raises(InvalidReplacementRequestError) as exc_info:
            pdf_replacer.replace_fields(sample_practical_pdf, det_res, req, output_dir=tmp_path)
        assert "duplicate" in str(exc_info.value).lower()


# ==============================================================================
# SECTION 5: CLI EXECUTION WITH PERSONALIZATION
# ==============================================================================

class TestCLIPersonalizationExecution:
    """Test suite for CLI execution in Phase 3 personalization mode."""

    def test_cli_personalize_name_and_roll(
        self, sample_practical_pdf: Path, tmp_path: Path
    ) -> None:
        """Verifies running python -m app.main <file> --name '...' --roll '...' personalizes PDF."""
        cmd = [
            sys.executable,
            "-m",
            "app.main",
            str(sample_practical_pdf),
            "--name",
            "Vivek Dhedhi",
            "--roll",
            "42",
            "-o",
            str(tmp_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        output = proc.stdout
        assert "DOCMORPH" in output
        assert "PDF PERSONALIZATION ENGINE" in output
        assert "Fields Replaced: 2 / 2" in output
        assert "PASSED" in output
        assert "PDF personalization completed successfully." in output

    def test_cli_personalize_json(
        self, sample_practical_pdf: Path, tmp_path: Path
    ) -> None:
        """Verifies CLI outputs valid ReplacementResult JSON when --json is provided."""
        cmd = [
            sys.executable,
            "-m",
            "app.main",
            str(sample_practical_pdf),
            "--name",
            "Vivek Dhedhi",
            "--json",
            "-o",
            str(tmp_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode == 0
        import json
        data = json.loads(proc.stdout)
        assert "job_id" in data
        assert data["total_successful"] == 1
        assert data["verification_status"] == "passed"
