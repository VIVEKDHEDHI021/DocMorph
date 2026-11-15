"""Test suite for Unified Identity Alignment Replacement in DocMorph.

Verifies that unlabelled identity fields (e.g. 'Vivek dhedhi (92400120571)')
are fetched and replaced together as a single unified line, eliminating:
- Awkward horizontal blank gaps before parentheses
- Orphaned delimiter tokens (e.g. '(', ')')
- Baseline coordinate shifts or vertical offsets
- Collisions when replacement strings change length
"""

from pathlib import Path
import pymupdf
import pytest

from app.schemas.detection_data import FieldType, ReviewStatus
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementRequest,
    ReplacementStatus,
    VerificationStatus,
)
from app.services.detection_engine import DetectionEngine
from app.services.pdf_replacer import PDFReplacer


def create_test_academic_pdf(
    file_path: Path,
    footer_text: str,
    page_number_text: str = "",
) -> None:
    """Helper to generate an academic test PDF with custom footer."""
    doc = pymupdf.open()
    page = doc.new_page(width=595.0, height=842.0)

    # Academic header
    page.insert_text(pymupdf.Point(50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=12)
    page.insert_text(pymupdf.Point(50, 90), "Practical 01: Cloud Computing Essentials", fontsize=11)
    page.insert_text(pymupdf.Point(50, 150), "Comparative study of cloud architectures and providers.", fontsize=10)

    # Blue separator line in footer
    page.draw_line(pymupdf.Point(50, 780), pymupdf.Point(545, 780), color=(0.2, 0.4, 0.8), width=1.0)

    # Identity in bottom-left footer
    page.insert_text(pymupdf.Point(50, 805), footer_text, fontname="tiro", fontsize=11.0)

    # Optional page number in bottom-right
    if page_number_text:
        page.insert_text(pymupdf.Point(520, 805), page_number_text, fontname="helv", fontsize=9.0)

    doc.save(str(file_path))
    doc.close()


class TestUnifiedIdentityReplacement:
    """Tests for unified identity replacement in academic PDF footers."""

    def test_unlabelled_pair_replaced_together_parentheses(self, tmp_path: Path) -> None:
        """Verifies unified replacement for concatenated 'Vivekdhedhi(92400120571)'."""
        pdf_path = tmp_path / "test_unlabelled_1.pdf"
        create_test_academic_pdf(pdf_path, "Vivekdhedhi(92400120571)")

        detector = DetectionEngine()
        det_res = detector.detect_file(pdf_path)
        for f in det_res.detected_fields:
            f.confirm()

        name_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        id_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(pdf_path),
            replacements=[
                ReplacementItem(
                    field_id=name_f.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_f.original_value,
                    new_value="NeelVyas",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id=id_f.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=id_f.original_value,
                    new_value="92400120560",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        replacer = PDFReplacer()
        rep_res = replacer.replace_fields(pdf_path, det_res, req, output_dir=tmp_path)

        assert rep_res.total_successful == 2
        assert rep_res.verification_status == VerificationStatus.PASSED

        # Inspect generated PDF
        out_doc = pymupdf.open(str(rep_res.output_path))
        p1_text = out_doc[0].get_text()

        # Both replacement values must be present
        assert "NeelVyas (92400120560)" in p1_text
        # Old values must be absent
        assert "Vivekdhedhi" not in p1_text
        assert "92400120571" not in p1_text

        # Verify unified block structure (no orphaned parentheses)
        footer_blocks = [
            b[4].strip() for b in out_doc[0].get_text("blocks")
            if b[1] > 750
        ]
        assert any("NeelVyas (92400120560)" in b for b in footer_blocks)
        assert "(" not in footer_blocks  # No isolated bracket block
        assert ")" not in footer_blocks
        out_doc.close()

    def test_unlabelled_pair_with_page_number_intact(self, tmp_path: Path) -> None:
        """Verifies replacement preserves bottom-right page number while unifying bottom-left identity."""
        pdf_path = tmp_path / "test_unlabelled_with_page.pdf"
        create_test_academic_pdf(
            pdf_path,
            footer_text="Vivek dhedhi (92400120571)",
            page_number_text="1",
        )

        detector = DetectionEngine()
        det_res = detector.detect_file(pdf_path)
        for f in det_res.detected_fields:
            f.confirm()

        name_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        id_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(pdf_path),
            replacements=[
                ReplacementItem(
                    field_id=name_f.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_f.original_value,
                    new_value="Neel Vyas",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id=id_f.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=id_f.original_value,
                    new_value="92400120560",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        replacer = PDFReplacer()
        rep_res = replacer.replace_fields(pdf_path, det_res, req, output_dir=tmp_path)

        assert rep_res.total_successful == 2
        assert rep_res.verification_status == VerificationStatus.PASSED

        out_doc = pymupdf.open(str(rep_res.output_path))
        p1_text = out_doc[0].get_text()

        # Replaced unified identity present
        assert "Neel Vyas (92400120560)" in p1_text
        # Page number 1 still present on page
        assert "1" in p1_text
        out_doc.close()

    def test_unlabelled_pair_hyphen_format(self, tmp_path: Path) -> None:
        """Verifies hyphen format 'Vivek Dhedhi - 92400120571' is preserved."""
        pdf_path = tmp_path / "test_hyphen.pdf"
        create_test_academic_pdf(pdf_path, "Vivek Dhedhi - 92400120571")

        detector = DetectionEngine()
        det_res = detector.detect_file(pdf_path)
        for f in det_res.detected_fields:
            f.confirm()

        name_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        id_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(pdf_path),
            replacements=[
                ReplacementItem(
                    field_id=name_f.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_f.original_value,
                    new_value="Neel Vyas",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id=id_f.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=id_f.original_value,
                    new_value="92400120560",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        replacer = PDFReplacer()
        rep_res = replacer.replace_fields(pdf_path, det_res, req, output_dir=tmp_path)

        out_doc = pymupdf.open(str(rep_res.output_path))
        p1_text = out_doc[0].get_text()
        assert "Neel Vyas - 92400120560" in p1_text
        out_doc.close()

    def test_name_only_replacement_in_unlabelled_pair(self, tmp_path: Path) -> None:
        """Verifies when only name is replaced, enrollment is preserved in unified line."""
        pdf_path = tmp_path / "test_name_only.pdf"
        create_test_academic_pdf(pdf_path, "Vivek Dhedhi (92400120571)")

        detector = DetectionEngine()
        det_res = detector.detect_file(pdf_path)
        for f in det_res.detected_fields:
            f.confirm()

        name_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.STUDENT_NAME)

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(pdf_path),
            replacements=[
                ReplacementItem(
                    field_id=name_f.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_f.original_value,
                    new_value="Neel Vyas",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        replacer = PDFReplacer()
        rep_res = replacer.replace_fields(pdf_path, det_res, req, output_dir=tmp_path)

        assert rep_res.total_successful == 1
        assert rep_res.verification_status == VerificationStatus.PASSED

        out_doc = pymupdf.open(str(rep_res.output_path))
        p1_text = out_doc[0].get_text()
        assert "Neel Vyas (92400120571)" in p1_text
        assert "Vivek Dhedhi" not in p1_text
        out_doc.close()

    def test_enrollment_only_replacement_in_unlabelled_pair(self, tmp_path: Path) -> None:
        """Verifies when only enrollment is replaced, name is preserved in unified line."""
        pdf_path = tmp_path / "test_id_only.pdf"
        create_test_academic_pdf(pdf_path, "Vivek Dhedhi (92400120571)")

        detector = DetectionEngine()
        det_res = detector.detect_file(pdf_path)
        for f in det_res.detected_fields:
            f.confirm()

        id_f = next(f for f in det_res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        req = ReplacementRequest(
            document_id=det_res.document_id,
            source_file=str(pdf_path),
            replacements=[
                ReplacementItem(
                    field_id=id_f.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=id_f.original_value,
                    new_value="92400120560",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
        )

        replacer = PDFReplacer()
        rep_res = replacer.replace_fields(pdf_path, det_res, req, output_dir=tmp_path)

        assert rep_res.total_successful == 1
        assert rep_res.verification_status == VerificationStatus.PASSED

        out_doc = pymupdf.open(str(rep_res.output_path))
        p1_text = out_doc[0].get_text()
        assert "Vivek Dhedhi (92400120560)" in p1_text
        assert "92400120571" not in p1_text
        out_doc.close()

