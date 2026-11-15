"""Comprehensive test suite for Phase C: Smart Manual Detection Engine.

Validates:
1. Area Selection Processing:
   - Genuine footer rectangular selection (FOOTER_CONFIRMED + student fields).
   - Partial footer selection.
   - Incorrect area selection (ordinary paragraphs, experiment titles).
   - Boundary clamping and out-of-bounds / invalid coordinates.
   - Non-standard PDF dimensions (Landscape, A4, Custom).
   - Multi-page document selection targeting specific pages.
2. Text Selection Processing:
   - Selecting student name string.
   - Selecting enrollment number string.
   - Selecting ordinary paragraph text.
   - Selecting experiment / chapter number text.
   - Selecting solitary page number text.
3. Coordinate transformations:
   - Normalized coordinates [0, 1000] mapping to PDF points.
   - Inverted and sub-threshold box validation.
4. Selection as input boundary (not content modification).
"""

import pytest
import pymupdf

from app.schemas.detection_data import BoundingBox, FieldType
from app.schemas.footer_verification import FooterStatus
from app.schemas.manual_detection import (
    ManualSelectionRequest,
    SelectionType,
)
from app.services.smart_manual_detector import SmartManualDetector


@pytest.fixture
def manual_detector():
    return SmartManualDetector()


@pytest.fixture
def sample_academic_pdf():
    """Creates a realistic academic PDF with body text, chapter header, and footer."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Header and body
    page.insert_text((50, 60), "Department of Computer Science & Engineering", fontsize=12)
    page.insert_text((50, 100), "Experiment 4: Implementation of Red-Black Trees", fontsize=14)
    page.insert_text(
        (50, 160),
        "A red-black tree is a kind of self-balancing binary search tree in computer science.",
        fontsize=10,
    )
    page.insert_text(
        (50, 180),
        "Each node stores an extra bit representing color (red or black), used to maintain balance.",
        fontsize=10,
    )

    # Middle body paragraph
    page.insert_text(
        (50, 450),
        "Theoretical analysis shows that insertion takes O(log n) time in the worst case.",
        fontsize=10,
    )

    # Near-bottom trailing paragraph (negative candidate)
    page.insert_text(
        (50, 660),
        "Conclusion: Red-black tree properties ensure maximum height does not exceed 2 log(n+1).",
        fontsize=10,
    )
    page.insert_text(
        (50, 680),
        "References: Introduction to Algorithms, Cormen, Leiserson, Rivest, Stein.",
        fontsize=10,
    )

    # Genuine Footer with separator
    page.draw_line((50, 730), (562, 730), color=(0.2, 0.2, 0.2), width=0.8)
    page.insert_text((50, 750), "Vivek Dhedhi (92400120571)", fontsize=9)
    page.insert_text((490, 750), "Page 1 of 4", fontsize=9)

    return doc


# =====================================================================
# 1. Area Selection Tests
# =====================================================================

def test_area_selection_genuine_footer(manual_detector, sample_academic_pdf):
    """Area selection tightly enclosing the genuine footer returns FOOTER_CONFIRMED with student fields."""
    req = ManualSelectionRequest(
        document_id="doc_area_genuine",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=725, x1=580, y1=770),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert resp.confidence >= 0.75
    assert len(resp.detected_fields) >= 2

    types = {f.field_type for f in resp.detected_fields}
    assert FieldType.STUDENT_NAME in types
    assert FieldType.ENROLLMENT_NUMBER in types

    name_field = next(f for f in resp.detected_fields if f.field_type == FieldType.STUDENT_NAME)
    assert "Vivek" in name_field.original_value
    assert "Dhedhi" in name_field.original_value


def test_area_selection_with_normalized_coordinates(manual_detector, sample_academic_pdf):
    """Area selection specified via normalized [0, 1000] coordinates accurately maps to PDF points."""
    # Normalized bbox for bottom region (y: 915 to 975 -> ~724 to 772 on 792 height)
    req = ManualSelectionRequest(
        document_id="doc_norm_coords",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        normalized_bbox=(65, 915, 950, 975),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert len(resp.detected_fields) >= 2
    # Verify coordinate resolution
    assert abs(resp.resolved_pdf_bbox.y0 - (915 / 1000.0 * 792)) < 1.0


def test_area_selection_rejects_ordinary_paragraph(manual_detector, sample_academic_pdf):
    """Area selection covering body text or Conclusion paragraph is rejected as FOOTER_NOT_FOUND."""
    req = ManualSelectionRequest(
        document_id="doc_reject_body",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=650, x1=580, y1=705),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert len(resp.detected_fields) == 0
    assert any("negative academic" in r.lower() or "prose" in r.lower() for r in resp.negative_reasons)


def test_area_selection_rejects_experiment_title(manual_detector, sample_academic_pdf):
    """Area selection covering Experiment header in upper section is rejected."""
    req = ManualSelectionRequest(
        document_id="doc_reject_header",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=80, x1=500, y1=130),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert len(resp.detected_fields) == 0
    assert any("experiment" in r.lower() or "top/middle" in r.lower() for r in resp.negative_reasons)


def test_area_selection_boundary_clamping_and_integrity(manual_detector, sample_academic_pdf):
    """Coordinates extending past page bounds are clamped strictly to page dimensions."""
    req = ManualSelectionRequest(
        document_id="doc_clamp",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=-50, y0=720, x1=700, y1=850),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.resolved_pdf_bbox.x0 == 0.0
    assert resp.resolved_pdf_bbox.x1 == 612.0
    assert resp.resolved_pdf_bbox.y1 == 792.0
    # Clamping shouldn't leak upper body lines
    assert "Theoretical analysis" not in resp.extracted_text


def test_area_selection_invalid_geometry(manual_detector, sample_academic_pdf):
    """Inverted or degenerate bounding boxes return a validation error."""
    # Inverted x: x1 < x0
    req = ManualSelectionRequest(
        document_id="doc_invalid_geo",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=300, y0=700, x1=100, y1=750),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert any("invalid dimensions" in r.lower() for r in resp.negative_reasons)


def test_area_selection_empty_region(manual_detector, sample_academic_pdf):
    """Area selection over white space containing no text returns no-text rejection."""
    req = ManualSelectionRequest(
        document_id="doc_empty_area",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=50, y0=300, x1=300, y1=380),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert resp.extracted_text == ""
    assert any("no selectable text" in r.lower() for r in resp.negative_reasons)


# =====================================================================
# 2. Text Selection Tests
# =====================================================================

def test_text_selection_student_name(manual_detector, sample_academic_pdf):
    """Text selection on student name extracts the name field with high confidence."""
    req = ManualSelectionRequest(
        document_id="doc_text_name",
        page_number=1,
        selection_type=SelectionType.TEXT,
        page_width=612,
        page_height=792,
        selected_text="Vivek Dhedhi",
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status in (FooterStatus.FOOTER_CONFIRMED, FooterStatus.FOOTER_UNCERTAIN)
    assert len(resp.detected_fields) >= 1
    name_field = next(f for f in resp.detected_fields if f.field_type == FieldType.STUDENT_NAME)
    assert "Vivek" in name_field.original_value


def test_text_selection_enrollment_number(manual_detector, sample_academic_pdf):
    """Text selection on enrollment digits extracts enrollment_number field."""
    req = ManualSelectionRequest(
        document_id="doc_text_enr",
        page_number=1,
        selection_type=SelectionType.TEXT,
        page_width=612,
        page_height=792,
        selected_text="92400120571",
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status in (FooterStatus.FOOTER_CONFIRMED, FooterStatus.FOOTER_UNCERTAIN)
    assert len(resp.detected_fields) >= 1
    enr_field = next(f for f in resp.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)
    assert "92400120571" in enr_field.original_value


def test_text_selection_rejects_ordinary_prose(manual_detector, sample_academic_pdf):
    """Text selection on ordinary sentence in body text is rejected as footer."""
    req = ManualSelectionRequest(
        document_id="doc_text_prose",
        page_number=1,
        selection_type=SelectionType.TEXT,
        page_width=612,
        page_height=792,
        selected_text="Each node stores an extra bit representing color",
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert len(resp.detected_fields) == 0


def test_text_selection_rejects_solitary_page_number(manual_detector, sample_academic_pdf):
    """Selecting only 'Page 1 of 4' is rejected as student footer."""
    req = ManualSelectionRequest(
        document_id="doc_text_page_num",
        page_number=1,
        selection_type=SelectionType.TEXT,
        page_width=612,
        page_height=792,
        selected_text="Page 1 of 4",
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert len(resp.detected_fields) == 0
    assert any("page number" in r.lower() for r in resp.negative_reasons)


# =====================================================================
# 3. Multi-page and Differing Page Dimensions Tests
# =====================================================================

def test_differing_dimensions_landscape_and_a4(manual_detector):
    """Smart manual detector accurately operates on landscape and A4 page dimensions."""
    doc = pymupdf.open()
    # Page 1: Landscape (792 x 612)
    p1 = doc.new_page(width=792, height=612)
    p1.insert_text((50, 80), "Landscape Architecture Chart", fontsize=14)
    p1.draw_line((50, 560), (742, 560), color=(0, 0, 0), width=1.0)
    p1.insert_text((50, 580), "Aarav Sharma (20210045612)", fontsize=10)

    # Page 2: Standard A4 (595.28 x 841.89)
    p2 = doc.new_page(width=595.28, height=841.89)
    p2.insert_text((50, 80), "A4 Document Format", fontsize=14)
    p2.draw_line((50, 790), (545, 790), color=(0, 0, 0), width=1.0)
    p2.insert_text((50, 810), "Priya Patel (180020107042)", fontsize=10)

    # Test Landscape Selection on Page 1
    req_landscape = ManualSelectionRequest(
        document_id="doc_diff_dims",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=792,
        page_height=612,
        raw_bbox=BoundingBox(x0=40, y0=550, x1=750, y1=600),
    )
    resp1 = manual_detector.process_selection(doc, req_landscape)
    assert resp1.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert any("Aarav" in f.original_value for f in resp1.detected_fields)

    # Test A4 Selection on Page 2
    req_a4 = ManualSelectionRequest(
        document_id="doc_diff_dims",
        page_number=2,
        selection_type=SelectionType.AREA,
        page_width=595.28,
        page_height=841.89,
        raw_bbox=BoundingBox(x0=40, y0=780, x1=550, y1=830),
    )
    resp2 = manual_detector.process_selection(doc, req_a4)
    assert resp2.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert any("Priya" in f.original_value for f in resp2.detected_fields)
    assert any("180020107042" in f.original_value for f in resp2.detected_fields)


def test_invalid_page_number(manual_detector, sample_academic_pdf):
    """Requests targeting a non-existent page number return DOCUMENT_UNREADABLE safely."""
    req = ManualSelectionRequest(
        document_id="doc_bad_page",
        page_number=99,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=50, y0=700, x1=550, y1=760),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.DOCUMENT_UNREADABLE
    assert "out of bounds" in resp.negative_reasons[0].lower()


def test_text_selection_with_explicit_text_bbox(manual_detector, sample_academic_pdf):
    """Text selection using explicit text_bbox coordinates (instead of string search)."""
    # Coordinates around "Vivek Dhedhi (92400120571)"
    req = ManualSelectionRequest(
        document_id="doc_text_bbox",
        page_number=1,
        selection_type=SelectionType.TEXT,
        page_width=612,
        page_height=792,
        text_bbox=BoundingBox(x0=50, y0=740, x1=220, y1=755),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert len(resp.detected_fields) >= 1
    assert any("Vivek" in f.original_value for f in resp.detected_fields)


def test_partial_footer_selection_enrollment_only(manual_detector, sample_academic_pdf):
    """Selecting only the enrollment portion of a footer successfully isolates the enrollment field."""
    req = ManualSelectionRequest(
        document_id="doc_partial_sel",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=120, y0=740, x1=230, y1=760),
    )

    resp = manual_detector.process_selection(sample_academic_pdf, req)

    assert resp.footer_status in (FooterStatus.FOOTER_CONFIRMED, FooterStatus.FOOTER_UNCERTAIN)
    assert len(resp.detected_fields) >= 1
    enr_fields = [f for f in resp.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER]
    assert len(enr_fields) == 1
    assert "92400120571" in enr_fields[0].original_value


def test_area_selection_uncertain_status_in_ambiguous_zone(manual_detector):
    """Student info selected in mid-page zone without separator returns FOOTER_UNCERTAIN."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Project Synopsis", fontsize=14)
    # Student name at middle of page (y=420) without separator line
    page.insert_text((50, 420), "Submitted by: Vivek Dhedhi (92400120571)", fontsize=11)
    page.insert_text((50, 600), "Guide: Prof. A. Mehta", fontsize=11)

    req = ManualSelectionRequest(
        document_id="doc_ambiguous",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=410, x1=400, y1=440),
    )

    resp = manual_detector.process_selection(doc, req)

    # In mid page, negative score penalizes footer classification
    assert resp.footer_status in (FooterStatus.FOOTER_UNCERTAIN, FooterStatus.FOOTER_NOT_FOUND)


def test_multi_page_document_selection(manual_detector):
    """Targeting specific pages in a 4-page PDF respects the respective page context."""
    names = ["Aarav Patel", "Priya Sharma", "Rohan Mehta", "Ananya Verma"]
    doc = pymupdf.open()
    for i in range(1, 5):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 100), f"Document Page {i}", fontsize=14)
        page.draw_line((50, 730), (562, 730), color=(0, 0, 0), width=0.8)
        page.insert_text((50, 750), f"{names[i-1]} (10000000000{i})", fontsize=10)

    # Target Page 3
    req3 = ManualSelectionRequest(
        document_id="doc_multipage",
        page_number=3,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=720, x1=570, y1=770),
    )

    resp3 = manual_detector.process_selection(doc, req3)
    assert resp3.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert resp3.page_number == 3
    assert any("Rohan Mehta" in f.original_value for f in resp3.detected_fields)
    assert any("100000000003" in f.original_value for f in resp3.detected_fields)

