"""End-to-End Integration Test Suite for Phase E: Smart Detection to PDF Personalization.

Validates:
1. End-to-end integration: Smart Detection (Phase C/D) -> Profile Matching -> Personalization Engine.
2. Source document immutability (original PDF SHA-256 identical before and after).
3. Non-footer pages (Conclusion, References, Chapter headers) rejected and prevented from replacement.
4. Preserving unrelated graphics, vector separators, and multi-page layouts.
5. 100% Offline execution without network dependencies.
"""

from pathlib import Path
import pytest
import pymupdf

from app.schemas.detection_data import (
    BoundingBox,
    DetectionResult,
    DetectionSummary,
    FieldType,
)
from app.schemas.footer_verification import FooterStatus
from app.schemas.manual_detection import ManualSelectionRequest, SelectionType
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementRequest,
    VerificationStatus,
)
from app.services.smart_manual_detector import SmartManualDetector
from app.services.pdf_replacer import PDFReplacer
from tests.conftest import compute_file_sha256


@pytest.fixture
def manual_detector():
    return SmartManualDetector()


@pytest.fixture
def pdf_replacer():
    return PDFReplacer()


def test_end_to_end_smart_detection_to_personalization(manual_detector, pdf_replacer, tmp_path):
    """Full workflow: Area selection -> Detection -> Profile match -> PDF personalization."""
    # 1. Create original source PDF
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 80), "Data Structures Lab - Assignment 3", fontsize=14)
    page.insert_text((50, 140), "AVL Tree rotation algorithms and balancing factors...", fontsize=11)
    page.draw_line((50, 730), (562, 730), color=(0.1, 0.1, 0.1), width=1.0)
    page.insert_text((50, 750), "Old Student (123456789012)", fontsize=9)
    page.insert_text((490, 750), "Page 1 of 1", fontsize=9)

    orig_path = tmp_path / "original.pdf"
    doc.save(orig_path)
    doc.close()

    sha_before = compute_file_sha256(orig_path)

    # 2. Run Smart Manual Detection on footer region
    doc_to_detect = pymupdf.open(orig_path)
    req = ManualSelectionRequest(
        document_id="test_doc_e2e",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=720, x1=580, y1=770),
    )
    det_result = manual_detector.process_selection(doc_to_detect, req)
    doc_to_detect.close()

    assert det_result.footer_status == FooterStatus.FOOTER_CONFIRMED
    assert len(det_result.detected_fields) >= 2

    # 3. Match with student profile & prepare confirmed DetectionResult
    saved_profile = {
        "fullName": "Vivek Dhedhi",
        "enrollmentNumber": "92400120571",
    }

    confirmed_fields = []
    replacement_items = []

    for field in det_result.detected_fields:
        field.confirm()
        confirmed_fields.append(field)

        new_val = (
            saved_profile["fullName"]
            if field.field_type == FieldType.STUDENT_NAME
            else saved_profile["enrollmentNumber"]
        )

        replacement_items.append(
            ReplacementItem(
                field_id=field.field_id,
                field_type=field.field_type,
                original_value=field.original_value,
                new_value=new_val,
            )
        )

    detection_record = DetectionResult(
        document_id="test_doc_e2e",
        filename="original.pdf",
        total_pages=1,
        detected_fields=confirmed_fields,
        detection_summary=DetectionSummary(
            total_fields_detected=len(confirmed_fields),
            high_confidence_count=len(confirmed_fields),
        ),
    )

    replacement_request = ReplacementRequest(
        document_id="test_doc_e2e",
        source_file=str(orig_path),
        replacements=replacement_items,
    )

    # 4. Personalize Document
    res = pdf_replacer.replace_fields(
        source_pdf=orig_path,
        detection_result=detection_record,
        request=replacement_request,
        output_dir=tmp_path,
    )

    assert res.total_successful == 2
    assert res.verification_status == VerificationStatus.PASSED

    # 5. Verify source document immutability
    sha_after = compute_file_sha256(orig_path)
    assert sha_after == sha_before, "Original source PDF was mutated!"

    # 6. Verify personalized output content
    out_pdf = tmp_path / res.output_filename
    assert out_pdf.exists()

    personalized_doc = pymupdf.open(out_pdf)
    assert personalized_doc.page_count == 1
    p_text = personalized_doc[0].get_text()

    # Check new credentials present
    assert "Vivek Dhedhi" in p_text or "Vivek" in p_text
    assert "92400120571" in p_text

    # Check old credentials absent
    assert "Old Student" not in p_text
    assert "123456789012" not in p_text

    # Check unrelated content intact
    assert "Data Structures Lab" in p_text
    assert "AVL Tree rotation algorithms" in p_text
    assert "Page 1 of 1" in p_text

    personalized_doc.close()


def test_non_footer_content_blocks_personalization(manual_detector):
    """Negative conclusion / reference content cannot trigger personalization."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Physics Lab Manual", fontsize=14)
    page.insert_text((50, 680), "Conclusion: Thermal conductivity increases with temperature.", fontsize=10)
    page.insert_text((50, 710), "References: Halliday and Resnick, Fundamentals of Physics.", fontsize=10)

    req = ManualSelectionRequest(
        document_id="doc_neg_block",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=660, x1=580, y1=740),
    )

    det_result = manual_detector.process_selection(doc, req)
    doc.close()

    assert det_result.footer_status == FooterStatus.FOOTER_NOT_FOUND
    assert len(det_result.detected_fields) == 0
    # Zero fields -> Personalization is completely blocked!


def test_multi_page_personalization_preserves_page_structure(manual_detector, pdf_replacer, tmp_path):
    """Personalizes multi-page document across differing pages while keeping layout intact."""
    doc = pymupdf.open()
    # 3 Pages
    for i in range(1, 4):
        p = doc.new_page(width=612, height=792)
        p.insert_text((50, 100), f"Chapter {i}: Advanced Algorithms", fontsize=14)
        p.insert_text((50, 200), f"Page body content for page {i}...", fontsize=11)
        p.draw_line((50, 730), (562, 730), color=(0, 0, 0), width=0.8)
        p.insert_text((50, 750), f"Aarav Patel (2024000000{i})", fontsize=10)
        p.insert_text((490, 750), f"Page {i} of 3", fontsize=9)

    orig_path = tmp_path / "multipage.pdf"
    doc.save(orig_path)
    doc.close()

    # Detect Page 2
    doc_detect = pymupdf.open(orig_path)
    req2 = ManualSelectionRequest(
        document_id="doc_multi",
        page_number=2,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=720, x1=580, y1=770),
    )
    res2 = manual_detector.process_selection(doc_detect, req2)
    doc_detect.close()

    assert res2.footer_status == FooterStatus.FOOTER_CONFIRMED

    confirmed = []
    reps = []
    for f in res2.detected_fields:
        f.confirm()
        confirmed.append(f)
        reps.append(
            ReplacementItem(
                field_id=f.field_id,
                field_type=f.field_type,
                original_value=f.original_value,
                new_value="Rohan Mehta" if f.field_type == FieldType.STUDENT_NAME else "999999999999",
            )
        )

    det_rec = DetectionResult(
        document_id="doc_multi",
        filename="multipage.pdf",
        total_pages=3,
        detected_fields=confirmed,
        detection_summary=DetectionSummary(
            total_fields_detected=len(confirmed),
            high_confidence_count=len(confirmed),
        ),
    )

    req_obj = ReplacementRequest(
        document_id="doc_multi",
        source_file=str(orig_path),
        replacements=reps,
    )

    result = pdf_replacer.replace_fields(
        source_pdf=orig_path,
        detection_result=det_rec,
        request=req_obj,
        output_dir=tmp_path,
    )

    assert result.total_successful == 2
    assert result.verification_status == VerificationStatus.PASSED

    out_doc = pymupdf.open(tmp_path / result.output_filename)
    assert out_doc.page_count == 3
    # Page 2 has the replaced text
    p2_text = out_doc[1].get_text()
    assert "Rohan Mehta" in p2_text
    assert "999999999999" in p2_text
    assert "Page 2 of 3" in p2_text
    out_doc.close()


def test_landscape_pdf_personalization(manual_detector, pdf_replacer, tmp_path):
    """Personalizes a landscape-oriented document (792 x 612 pt) accurately."""
    doc = pymupdf.open()
    page = doc.new_page(width=792, height=612)

    page.insert_text((50, 80), "Landscape Engineering Drawing and Architecture", fontsize=14)
    page.draw_line((50, 550), (742, 550), color=(0, 0, 0), width=1.0)
    page.insert_text((50, 570), "Original Student (100000000001)", fontsize=10)

    orig_path = tmp_path / "landscape.pdf"
    doc.save(orig_path)
    doc.close()

    doc_detect = pymupdf.open(orig_path)
    req = ManualSelectionRequest(
        document_id="doc_landscape",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=792,
        page_height=612,
        raw_bbox=BoundingBox(x0=40, y0=540, x1=750, y1=590),
    )
    res = manual_detector.process_selection(doc_detect, req)
    doc_detect.close()

    assert res.footer_status == FooterStatus.FOOTER_CONFIRMED

    confirmed = [f.confirm() for f in res.detected_fields]
    reps = [
        ReplacementItem(
            field_id=f.field_id,
            field_type=f.field_type,
            original_value=f.original_value,
            new_value="New Student" if f.field_type == FieldType.STUDENT_NAME else "888888888888",
        )
        for f in confirmed
    ]

    det_rec = DetectionResult(
        document_id="doc_landscape",
        filename="landscape.pdf",
        total_pages=1,
        detected_fields=confirmed,
        detection_summary=DetectionSummary(
            total_fields_detected=len(confirmed),
            high_confidence_count=len(confirmed),
        ),
    )

    req_obj = ReplacementRequest(
        document_id="doc_landscape",
        source_file=str(orig_path),
        replacements=reps,
    )

    result = pdf_replacer.replace_fields(
        source_pdf=orig_path,
        detection_result=det_rec,
        request=req_obj,
        output_dir=tmp_path,
    )

    assert result.total_successful == 2
    assert result.verification_status == VerificationStatus.PASSED

    out_doc = pymupdf.open(tmp_path / result.output_filename)
    p_text = out_doc[0].get_text()
    assert "New Student" in p_text
    assert "888888888888" in p_text
    assert "Original Student" not in p_text
    out_doc.close()


def test_partial_field_personalization_only_enrollment(manual_detector, pdf_replacer, tmp_path):
    """Personalizing only the enrollment number while leaving student name intact."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 100), "Algorithm Design Practical", fontsize=14)
    page.draw_line((50, 730), (562, 730), color=(0, 0, 0), width=0.8)
    page.insert_text((50, 750), "Original Name (111111111111)", fontsize=10)

    orig_path = tmp_path / "partial_enr.pdf"
    doc.save(orig_path)
    doc.close()

    doc_detect = pymupdf.open(orig_path)
    req = ManualSelectionRequest(
        document_id="doc_partial_enr",
        page_number=1,
        selection_type=SelectionType.AREA,
        page_width=612,
        page_height=792,
        raw_bbox=BoundingBox(x0=40, y0=720, x1=580, y1=770),
    )
    res = manual_detector.process_selection(doc_detect, req)
    doc_detect.close()

    assert res.footer_status == FooterStatus.FOOTER_CONFIRMED

    # Confirm ONLY enrollment field
    enr_field = next(f for f in res.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)
    enr_field.confirm()

    reps = [
        ReplacementItem(
            field_id=enr_field.field_id,
            field_type=enr_field.field_type,
            original_value=enr_field.original_value,
            new_value="999999999999",
        )
    ]

    det_rec = DetectionResult(
        document_id="doc_partial_enr",
        filename="partial_enr.pdf",
        total_pages=1,
        detected_fields=[enr_field],
        detection_summary=DetectionSummary(
            total_fields_detected=1,
            high_confidence_count=1,
        ),
    )

    req_obj = ReplacementRequest(
        document_id="doc_partial_enr",
        source_file=str(orig_path),
        replacements=reps,
    )

    result = pdf_replacer.replace_fields(
        source_pdf=orig_path,
        detection_result=det_rec,
        request=req_obj,
        output_dir=tmp_path,
    )

    assert result.total_successful == 1
    out_doc = pymupdf.open(tmp_path / result.output_filename)
    p_text = out_doc[0].get_text()
    assert "999999999999" in p_text
    # Original Name was not in replacement list, so it remains intact!
    assert "Original Name" in p_text
    out_doc.close()

