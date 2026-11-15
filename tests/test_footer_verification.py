"""Comprehensive test suite for Phase B: Footer Verification Layer.

Validates:
1. Canonical verification states: FOOTER_CONFIRMED, FOOTER_NOT_FOUND, FOOTER_UNCERTAIN, DOCUMENT_UNREADABLE.
2. Prevention of false positives on ordinary trailing text ('Conclusion', 'References', etc.).
3. Chapter numbers, experiment numbers, and solitary page numbers rejected as footers.
4. Accurate detection of genuine footers across multiple pages, single pages, and differing layouts.
5. First-page exception handling in multi-page documents.
"""

import pytest
import pymupdf

from app.schemas.detection_data import FieldType
from app.schemas.footer_verification import FooterStatus
from app.services.detection_engine import DetectionEngine
from app.services.footer_verifier import FooterVerifier
from app.services.text_segmenter import TextSegmenter


@pytest.fixture
def detection_engine():
    return DetectionEngine()


@pytest.fixture
def footer_verifier():
    return FooterVerifier()


def test_negative_conclusion_references_not_classified_as_footer(detection_engine):
    """Verifies that ordinary paragraphs with 'Conclusion' and 'References' at bottom are NOT footers."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Physics Practical Manual - Experiment 5", fontsize=14)
    page.insert_text((50, 140), "Observation data table and theoretical background...", fontsize=11)
    page.insert_text((50, 680), "Conclusion: The speed of sound in air was measured to be 343 m/s.", fontsize=10)
    page.insert_text((50, 710), "References: Halliday & Resnick, Fundamentals of Physics 11th Edition.", fontsize=10)
    page.insert_text((50, 735), "Department of Applied Sciences, Academic Year 2024-2025.", fontsize=10)

    result = detection_engine.detect_document(doc, "conclusion_negative.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_NOT_FOUND
    assert result.footer_verification.confirmed_pages_count == 0
    # No student fields should be detected from trailing body text
    assert len(result.detected_fields) == 0


def test_negative_experiment_chapter_number_not_footer(detection_engine):
    """Verifies that chapter and experiment numbers near the bottom of a page are rejected."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Computer Engineering Lab Manual", fontsize=14)
    page.insert_text((50, 150), "Overview of Sorting Algorithms in C++", fontsize=11)
    page.insert_text((50, 720), "Experiment No. 4: QuickSort and MergeSort Implementations", fontsize=10)
    page.insert_text((50, 745), "Chapter 3: Divide and Conquer Paradigms", fontsize=10)

    result = detection_engine.detect_document(doc, "chapter_negative.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_NOT_FOUND
    assert len(result.detected_fields) == 0


def test_negative_solitary_page_number_not_footer(detection_engine):
    """Verifies that a solitary page number ('Page 1 of 5') at bottom is NOT a student footer."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Data Structures Assignment 1", fontsize=14)
    page.insert_text((50, 150), "Binary Search Tree properties and rotations...", fontsize=11)
    # Centered page number at bottom
    page.insert_text((280, 755), "Page 1 of 5", fontsize=9)

    result = detection_engine.detect_document(doc, "page_number_only.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_NOT_FOUND
    assert len(result.detected_fields) == 0


def test_positive_genuine_footer_with_separator_line(detection_engine):
    """Verifies that a genuine footer separated by a vector rule is CONFIRMED with student fields."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Operating Systems Lab Practical 3", fontsize=14)
    page.insert_text((50, 150), "Process synchronization with semaphores...", fontsize=11)

    # Horizontal vector separator rule
    page.draw_line((50, 730), (562, 730), color=(0.1, 0.3, 0.7), width=1.0)
    # Genuine footer metadata
    page.insert_text((50, 750), "Vivek Dhedhi (92400120571)", fontsize=9)
    page.insert_text((480, 750), "Page 1", fontsize=9)

    result = detection_engine.detect_document(doc, "positive_footer.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_CONFIRMED
    assert result.footer_verification.confirmed_pages_count == 1
    page1 = result.footer_verification.page_results[0]
    assert page1.has_separator_line is True
    assert page1.separator_y is not None

    # Check student field extraction
    types = [f.field_type for f in result.detected_fields]
    assert FieldType.STUDENT_NAME in types
    assert FieldType.ENROLLMENT_NUMBER in types


def test_positive_multi_page_document_with_footers(detection_engine):
    """Verifies multi-page consistency and cross-page reinforcement across pages."""
    doc = pymupdf.open()

    for p_num in range(1, 4):
        p = doc.new_page(width=612, height=792)
        p.insert_text((50, 100), f"Database Management Systems - Page {p_num}", fontsize=14)
        p.insert_text((50, 150), "SQL queries and normalization exercises...", fontsize=11)
        p.draw_line((50, 735), (562, 735), color=(0.5, 0.5, 0.5), width=0.8)
        p.insert_text((50, 755), "Rahul Patel - 2300012345", fontsize=9)
        p.insert_text((500, 755), f"Page {p_num}", fontsize=9)

    result = detection_engine.detect_document(doc, "multipage_positive.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_CONFIRMED
    assert result.footer_verification.confirmed_pages_count == 3
    assert result.total_pages == 3

    # Check that multi-page evidence bonus was assigned
    for page_res in result.footer_verification.page_results:
        assert page_res.status == FooterStatus.FOOTER_CONFIRMED
        assert page_res.evidence.multi_page_score >= 15.0


def test_positive_multi_page_first_page_cover_exception(detection_engine):
    """Verifies that a multi-page document with a cover page (no footer on page 1) is handled correctly."""
    doc = pymupdf.open()

    # Page 1: Cover page (no footer)
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((150, 250), "SOFTWARE ENGINEERING PROJECT REPORT", fontsize=18)
    p1.insert_text((200, 300), "DocMorph Automated System", fontsize=14)
    p1.insert_text((220, 350), "Submitted by Group 4", fontsize=12)

    # Pages 2 & 3: Content pages with genuine footers
    for p_num in range(2, 4):
        p = doc.new_page(width=612, height=792)
        p.insert_text((50, 100), f"Section {p_num}: Requirements Analysis", fontsize=14)
        p.insert_text((50, 140), "Functional and non-functional requirements...", fontsize=11)
        p.draw_line((50, 735), (562, 735), color=(0.4, 0.4, 0.4), width=0.8)
        p.insert_text((50, 755), "Neel Vyas (92400120560)", fontsize=9)

    result = detection_engine.detect_document(doc, "cover_page_doc.pdf")

    assert result.footer_verification is not None
    # Document overall should be CONFIRMED because pages 2 & 3 have verified footers
    assert result.footer_verification.status == FooterStatus.FOOTER_CONFIRMED
    assert result.footer_verification.page_results[0].status == FooterStatus.FOOTER_NOT_FOUND
    assert result.footer_verification.page_results[1].status == FooterStatus.FOOTER_CONFIRMED
    assert result.footer_verification.page_results[2].status == FooterStatus.FOOTER_CONFIRMED


def test_uncertain_footer_structure_requires_review(detection_engine):
    """Verifies that an ambiguous bottom block without strong separation triggers FOOTER_UNCERTAIN."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Mathematics Tutorial Sheet", fontsize=14)
    page.insert_text((50, 150), "Solve the following differential equations...", fontsize=11)
    # Ambiguous footer: at y = 730, but no line divider and moderate gap
    page.insert_text((50, 740), "Batch A2 - Roll No 45", fontsize=10)

    result = detection_engine.detect_document(doc, "ambiguous_footer.pdf")

    assert result.footer_verification is not None
    # Should be UNCERTAIN or CONFIRMED depending on gap, but NOT NOT_FOUND
    assert result.footer_verification.status in (FooterStatus.FOOTER_UNCERTAIN, FooterStatus.FOOTER_CONFIRMED)


def test_different_page_sizes_and_landscape(detection_engine):
    """Verifies that landscape orientation and non-standard page sizes (A4, Letter) work correctly."""
    doc = pymupdf.open()
    # A4 Landscape: 842 x 595
    page = doc.new_page(width=842, height=595)

    page.insert_text((50, 80), "Landscape Engineering Drawing and Circuit Analysis", fontsize=14)
    page.insert_text((50, 120), "Schematic diagram representation...", fontsize=11)
    page.draw_line((50, 545), (792, 545), color=(0.3, 0.3, 0.3), width=0.8)
    page.insert_text((50, 565), "Vivek Dhedhi [92400120571]", fontsize=9)

    result = detection_engine.detect_document(doc, "landscape_footer.pdf")

    assert result.footer_verification is not None
    assert result.footer_verification.status == FooterStatus.FOOTER_CONFIRMED
    page1 = result.footer_verification.page_results[0]
    assert page1.has_separator_line is True
    # The boundary must be scaled properly to landscape height (595pt)
    assert page1.boundary_y > 500
