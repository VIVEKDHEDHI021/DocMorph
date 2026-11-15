"""Comprehensive test suite for Unlabelled Student Identity Recognition in academic PDF footers.

Tests all 12 mandatory requirements:
1. "Vivek Dhedhi (92400120571)" in bottom-left footer.
2. "Vivek Dhedhi - 92400120571" in bottom-left footer.
3. "Vivek Dhedhi | 92400120571" in bottom-left footer.
4. "Vivek Dhedhi 92400120571" (space separator) in bottom-left footer.
5. "92400120571 - Vivek Dhedhi" (inverted order).
6. Page numbers on the bottom-right are NOT detected as identifiers.
7. Footer separator line presence boosts confidence.
8. Separate bounding boxes for name and identifier.
9. Name with academic stop words (e.g., "Computer Engineering (92400120571)") is rejected.
10. Cross-page consistency boosts confidence.
11. Single-page document with unlabelled identity.
12. Multi-page document where one page is missing the identity.
"""

import time
import pymupdf
import pytest

from app.schemas.detection_data import FieldType
from app.services.detection_engine import DetectionEngine
from app.services.unlabelled_identity_detector import UnlabelledIdentityDetector


def create_academic_pdf(
    footer_text: str,
    page_count: int = 1,
    include_separator_line: bool = False,
    include_page_number: bool = False,
    footer_y: float = 800.0,
    footer_x: float = 50.0,
    skip_footer_on_pages: set[int] = None,
) -> bytes:
    """Helper to generate in-memory academic PDFs for test scenarios."""
    skip_footer_on_pages = skip_footer_on_pages or set()
    doc = pymupdf.open()

    for p_num in range(1, page_count + 1):
        # A4 Page: 595.3 x 841.9 pt
        page = doc.new_page(width=595.0, height=842.0)

        # Header / Academic body content
        page.insert_text(pymupdf.Point(50, 60), "DEPARTMENT OF COMPUTER ENGINEERING", fontsize=12)
        page.insert_text(pymupdf.Point(50, 90), "EXPERIMENT NO. 5: INSTRUCTION ANALYSIS", fontsize=11)
        page.insert_text(
            pymupdf.Point(50, 150),
            "Objective: To study the execution flags and registers of the 8086 microprocessor.",
            fontsize=10,
        )

        # Optional vector horizontal separator line
        if include_separator_line:
            page.draw_line(pymupdf.Point(50.0, 780.0), pymupdf.Point(545.0, 780.0), width=1.0)

        # Footer identity text (bottom-left)
        if p_num not in skip_footer_on_pages and footer_text:
            page.insert_text(
                pymupdf.Point(footer_x, footer_y),
                footer_text,
                fontsize=10,
            )

        # Bottom-right page number
        if include_page_number:
            page.insert_text(
                pymupdf.Point(500.0, footer_y),
                f"Page {p_num}",
                fontsize=10,
            )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestUnlabelledIdentityDetection:
    """TestSuite for unlabelled student credential recognition in academic footers."""

    @pytest.fixture
    def engine(self) -> DetectionEngine:
        return DetectionEngine()

    def test_case_1_parentheses_pattern(self, engine: DetectionEngine):
        """1. 'Vivek Dhedhi (92400120571)' in bottom-left footer."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi (92400120571)")
        result = engine.detect_bytes(pdf_bytes, filename="case1.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields

        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek Dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"
        assert fields[FieldType.STUDENT_NAME].confidence >= 0.65
        assert fields[FieldType.ENROLLMENT_NUMBER].confidence >= 0.65

    def test_case_2_hyphen_pattern(self, engine: DetectionEngine):
        """2. 'Vivek Dhedhi - 92400120571' in bottom-left footer."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi - 92400120571")
        result = engine.detect_bytes(pdf_bytes, filename="case2.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek Dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_3_pipe_pattern(self, engine: DetectionEngine):
        """3. 'Vivek Dhedhi | 92400120571' in bottom-left footer."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi | 92400120571")
        result = engine.detect_bytes(pdf_bytes, filename="case3.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek Dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_4_space_separator_pattern(self, engine: DetectionEngine):
        """4. 'Vivek Dhedhi 92400120571' (space separator) in bottom-left footer."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi 92400120571")
        result = engine.detect_bytes(pdf_bytes, filename="case4.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek Dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_5_inverted_order_pattern(self, engine: DetectionEngine):
        """5. '92400120571 - Vivek Dhedhi' (inverted order)."""
        pdf_bytes = create_academic_pdf("92400120571 - Vivek Dhedhi")
        result = engine.detect_bytes(pdf_bytes, filename="case5.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek Dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_6_page_numbers_disambiguation(self, engine: DetectionEngine):
        """6. Page numbers on the bottom-right are NOT detected as identifiers."""
        # PDF with student info on left, and 'Page 1' on right
        pdf_bytes = create_academic_pdf(
            footer_text="Vivek Dhedhi (92400120571)",
            include_page_number=True,
        )
        result = engine.detect_bytes(pdf_bytes, filename="case6.pdf")

        # Must detect student name and enrollment number
        values = [f.suggested_value for f in result.detected_fields]
        assert "Vivek Dhedhi" in values
        assert "92400120571" in values

        # Must never detect "Page 1" or "1" as any student field
        for f in result.detected_fields:
            assert "Page" not in f.suggested_value
            assert f.suggested_value != "1"
            assert f.field_type != FieldType.ROLL_NUMBER or f.suggested_value != "1"

    def test_case_7_separator_line_confidence_boost(self, engine: DetectionEngine):
        """7. Footer separator line presence boosts confidence."""
        pdf_without_line = create_academic_pdf(
            "Vivek Dhedhi (92400120571)",
            include_separator_line=False,
        )
        pdf_with_line = create_academic_pdf(
            "Vivek Dhedhi (92400120571)",
            include_separator_line=True,
        )

        res_without = engine.detect_bytes(pdf_without_line, filename="no_line.pdf")
        res_with = engine.detect_bytes(pdf_with_line, filename="with_line.pdf")

        name_without = next(f for f in res_without.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_with = next(f for f in res_with.detected_fields if f.field_type == FieldType.STUDENT_NAME)

        # Presence of separator line must yield a higher confidence score
        assert name_with.confidence > name_without.confidence
        assert any("separator line" in r.lower() for r in name_with.confidence_reasons)

    def test_case_8_separate_bounding_boxes(self, engine: DetectionEngine):
        """8. Separate bounding boxes for name and identifier."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi (92400120571)")
        result = engine.detect_bytes(pdf_bytes, filename="case8.pdf")

        name_field = next(f for f in result.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        id_field = next(f for f in result.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        name_box = name_field.occurrences[0].value_bbox
        id_box = id_field.occurrences[0].value_bbox

        assert name_box is not None
        assert id_box is not None

        # Coordinates must be strictly non-overlapping
        rect_name = pymupdf.Rect(name_box.to_tuple())
        rect_id = pymupdf.Rect(id_box.to_tuple())
        assert not rect_name.intersects(rect_id)

        # Name must be to the left of ID
        assert name_box.x1 < id_box.x0

    def test_case_9_academic_stop_words_rejection(self, engine: DetectionEngine):
        """9. Name with academic stop words (e.g. 'Computer Engineering (92400120571)') is rejected."""
        pdf_bytes = create_academic_pdf("Computer Engineering (92400120571)")
        result = engine.detect_bytes(pdf_bytes, filename="case9.pdf")

        names = [f.suggested_value for f in result.detected_fields if f.field_type == FieldType.STUDENT_NAME]
        assert "Computer Engineering" not in names

    def test_case_10_cross_page_consistency_boost(self, engine: DetectionEngine):
        """10. Cross-page consistency boosts confidence."""
        # 1-page document with single occurrence
        pdf_1page = create_academic_pdf("Vivek Dhedhi (92400120571)", page_count=1)
        # 3-page document with repeating occurrence on all 3 pages
        pdf_3page = create_academic_pdf("Vivek Dhedhi (92400120571)", page_count=3)

        res_1page = engine.detect_bytes(pdf_1page, filename="p1.pdf")
        res_3page = engine.detect_bytes(pdf_3page, filename="p3.pdf")

        name_1 = next(f for f in res_1page.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        name_3 = next(f for f in res_3page.detected_fields if f.field_type == FieldType.STUDENT_NAME)

        assert len(name_3.occurrences) == 3
        # Consistency across multiple pages boosts confidence
        assert name_3.confidence > name_1.confidence
        assert any("repeated across 3 pages" in r for r in name_3.confidence_reasons)

    def test_case_11_single_page_document(self, engine: DetectionEngine):
        """11. Single-page document with unlabelled identity."""
        pdf_bytes = create_academic_pdf("Vivek dhedhi (92400120571)", page_count=1)
        result = engine.detect_bytes(pdf_bytes, filename="single_page.pdf")

        assert result.total_pages == 1
        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivek dhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_12_multi_page_missing_on_one_page(self, engine: DetectionEngine):
        """12. Multi-page document where one page is missing the identity."""
        # 3-page document, but page 2 does not have the footer
        pdf_bytes = create_academic_pdf(
            "Vivek Dhedhi (92400120571)",
            page_count=3,
            skip_footer_on_pages={2},
        )
        result = engine.detect_bytes(pdf_bytes, filename="missing_p2.pdf")

        assert result.total_pages == 3
        name_field = next(f for f in result.detected_fields if f.field_type == FieldType.STUDENT_NAME)

        pages_with_name = [occ.page_number for occ in name_field.occurrences]
        assert pages_with_name == [1, 3]
        assert 2 not in pages_with_name

    def test_performance_10_page_document(self, engine: DetectionEngine):
        """Performance requirement: 10-page document detection completes in < 2.0s."""
        pdf_bytes = create_academic_pdf("Vivek Dhedhi (92400120571)", page_count=10)
        start = time.perf_counter()
        result = engine.detect_bytes(pdf_bytes, filename="perf10.pdf")
        elapsed = time.perf_counter() - start

        assert result.total_pages == 10
        assert elapsed < 2.0

    def test_end_to_end_personalization_preserves_parentheses(self, engine: DetectionEngine, tmp_path):
        """Verify that replacing unlabelled fields replaces only the targeted text and preserves punctuation."""
        from app.schemas.detection_data import ReviewStatus
        from app.schemas.replacement_data import ReplacementItem, ReplacementRequest
        from app.services.pdf_replacer import PDFReplacer

        # Create input PDF on disk
        pdf_bytes = create_academic_pdf("Vivek Dhedhi (92400120571)", page_count=1)
        src_path = tmp_path / "academic_doc.pdf"
        src_path.write_bytes(pdf_bytes)

        # Detect
        det_result = engine.detect_file(src_path)
        name_f = next(f for f in det_result.detected_fields if f.field_type == FieldType.STUDENT_NAME)
        id_f = next(f for f in det_result.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

        # Confirm fields for personalization
        det_result.confirm_field(name_f.field_id)
        det_result.confirm_field(id_f.field_id)

        replacer = PDFReplacer()
        req = ReplacementRequest(
            source_file=str(src_path),
            document_id=det_result.document_id,
            replacements=[
                ReplacementItem(
                    field_id=name_f.field_id,
                    field_type=FieldType.STUDENT_NAME,
                    original_value=name_f.suggested_value,
                    new_value="Aarav Sharma",
                    review_status=ReviewStatus.CONFIRMED,
                ),
                ReplacementItem(
                    field_id=id_f.field_id,
                    field_type=FieldType.ENROLLMENT_NUMBER,
                    original_value=id_f.suggested_value,
                    new_value="99900011122",
                    review_status=ReviewStatus.CONFIRMED,
                ),
            ],
            output_filename="personalized_academic.pdf",
        )

        res = replacer.replace_fields(
            source_pdf=src_path,
            detection_result=det_result,
            request=req,
            output_dir=tmp_path / "output",
        )

        from pathlib import Path
        assert res.total_successful == 2
        assert res.total_failed == 0
        assert Path(res.output_path).exists()

        # Verify output text in personalized PDF
        with pymupdf.open(str(res.output_path)) as out_doc:
            text = out_doc[0].get_text("text")
            assert "Aarav Sharma" in text
            assert "99900011122" in text
            assert "(" in text and ")" in text
            assert "Vivek Dhedhi" not in text
            assert "92400120571" not in text

    def test_case_13_concatenated_name_pattern(self, engine: DetectionEngine):
        """13. 'Vivekdhedhi(92400120571)' (concatenated/single-token name) in bottom-left footer."""
        pdf_bytes = create_academic_pdf("Vivekdhedhi(92400120571)")
        result = engine.detect_bytes(pdf_bytes, filename="concatenated.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.STUDENT_NAME in fields
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.STUDENT_NAME].suggested_value == "Vivekdhedhi"
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"

    def test_case_14_standalone_bottom_left_enrollment(self, engine: DetectionEngine):
        """14. Standalone enrollment number in bottom-left corner without student name."""
        pdf_bytes = create_academic_pdf("(92400120571)", include_page_number=True)
        result = engine.detect_bytes(pdf_bytes, filename="standalone_id.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"
        # Page number on right must NOT be detected
        for f in result.detected_fields:
            assert f.suggested_value != "1"
            assert "Page" not in f.suggested_value

    def test_case_15_pure_digits_left_bottom_fallback(self, engine: DetectionEngine):
        """15. Every time an enrollment number is in the left-bottom corner, it is identified."""
        pdf_bytes = create_academic_pdf("92400120571", include_page_number=True)
        result = engine.detect_bytes(pdf_bytes, filename="pure_digits.pdf")

        fields = {f.field_type: f for f in result.detected_fields}
        assert FieldType.ENROLLMENT_NUMBER in fields
        assert fields[FieldType.ENROLLMENT_NUMBER].suggested_value == "92400120571"


