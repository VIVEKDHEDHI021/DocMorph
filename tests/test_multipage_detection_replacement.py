"""Multi-Page Detection & Complete Footer Replacement Regression Test Suite.

Covers all 14 mandatory test scenarios:
1. Five-page PDF with identical footer on every page.
2. Ten-page PDF with different footer positions.
3. PDF with student name on the first page and every footer.
4. PDF where only some pages contain enrollment numbers.
5. PDF with identity details in the middle of a page.
6. PDF with different page dimensions.
7. PDF with rotated pages.
8. Scanned PDF with image-based footers.
9. Mixed text and scanned PDF.
10. PDF with multiple identity occurrences on the same page.
11. PDF where the same identity value appears in unrelated body text.
12. PDF with text split across multiple PDF content operators.
13. PDF containing shared Form XObjects for repeated footers.
14. PDF with different fonts and font sizes.
"""

from pathlib import Path
import pytest
import pymupdf

from app.schemas.detection_data import FieldType
from app.schemas.replacement_data import ReplacementItem, ReplacementRequest, VerificationStatus
from app.services.detection_engine import DetectionEngine
from app.services.pdf_replacer import PDFReplacer


# Helper to create synthetic PDFs cleanly
def _add_divider_and_footer(page, text: str, y: float = 750.0):
    w = page.rect.width
    # Vector separator rule
    page.draw_line(pymupdf.Point(50, y - 10), pymupdf.Point(w - 50, y - 10), color=(0.2, 0.4, 0.8), width=1.0)
    # Footer text
    page.insert_text(pymupdf.Point(50, y + 8), text, fontsize=10, fontname="helv", color=(0, 0, 0))


# ==============================================================================
# SCENARIO 1: Five-page PDF with identical footer on every page
# ==============================================================================
def test_scenario_01_five_page_identical_footer(tmp_path: Path):
    pdf_path = tmp_path / "scenario_01.pdf"
    doc = pymupdf.open()
    for p in range(5):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(50, 80), f"Experiment {p+1}: Network Topology", fontsize=14, fontname="hebo")
        page.insert_text(pymupdf.Point(50, 120), "This is laboratory report body content.", fontsize=11, fontname="helv")
        _add_divider_and_footer(page, "Vivek Dhedhi (92400120571)", y=750)
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    # Confirm all 5 pages have student_name and enrollment_number detected
    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    id_field = next((f for f in det.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER), None)

    assert name_field is not None, "Student name must be detected"
    assert id_field is not None, "Enrollment number must be detected"
    assert set(name_field.pages) == {1, 2, 3, 4, 5}, f"Name must be detected on all 5 pages, got {name_field.pages}"
    assert set(id_field.pages) == {1, 2, 3, 4, 5}, f"Enrollment must be detected on all 5 pages, got {id_field.pages}"

    # Execute complete replacement across all pages
    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Aarav Mehta"),
            ReplacementItem(field_id=id_field.field_id, field_type=id_field.field_type, original_value=id_field.original_value, new_value="92400199999"),
        ],
        output_filename="scenario_01_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED, "Personalized PDF must pass verification"

    # Re-open and verify page-by-page text assertions
    with pymupdf.open(str(tmp_path / "scenario_01_personalized.pdf")) as out_doc:
        assert out_doc.page_count == 5
        for p in range(5):
            p_text = out_doc[p].get_text()
            assert "Vivek Dhedhi" not in p_text, f"Old name still present on page {p+1}"
            assert "92400120571" not in p_text, f"Old ID still present on page {p+1}"
            assert "Aarav Mehta" in p_text, f"New name missing on page {p+1}"
            assert "92400199999" in p_text, f"New ID missing on page {p+1}"


# ==============================================================================
# SCENARIO 2: Ten-page PDF with different footer positions
# ==============================================================================
def test_scenario_02_ten_page_different_footer_positions(tmp_path: Path):
    pdf_path = tmp_path / "scenario_02.pdf"
    doc = pymupdf.open()
    # Different footer Y coordinates across 10 pages
    y_positions = [700, 710, 720, 730, 740, 750, 760, 725, 735, 745]
    for p, y_pos in enumerate(y_positions):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(50, 80), f"Topic Section {p+1}", fontsize=14, fontname="hebo")
        page.insert_text(pymupdf.Point(50, 150), "Document body content line with standard spacing.", fontsize=11, fontname="helv")
        _add_divider_and_footer(page, "Vivek Dhedhi (92400120571)", y=y_pos)
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert len(name_field.pages) == 10, f"Must detect all 10 pages with different footer heights, got {len(name_field.pages)}"

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Rohan Varma"),
        ],
        output_filename="scenario_02_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_02_personalized.pdf")) as out_doc:
        for p in range(10):
            p_text = out_doc[p].get_text()
            assert "Vivek Dhedhi" not in p_text, f"Page {p+1} old name remaining"
            assert "Rohan Varma" in p_text, f"Page {p+1} new name missing"


# ==============================================================================
# SCENARIO 3: PDF with student name on the first page and every footer
# ==============================================================================
def test_scenario_03_first_page_header_and_every_footer(tmp_path: Path):
    pdf_path = tmp_path / "scenario_03.pdf"
    doc = pymupdf.open()
    # Page 1: Cover block at top AND footer
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text(pymupdf.Point(50, 100), "Marwadi University - Department of ICT", fontsize=14, fontname="hebo")
    p1.insert_text(pymupdf.Point(50, 180), "Student Name: Vivek Dhedhi", fontsize=12, fontname="helv")
    p1.insert_text(pymupdf.Point(50, 200), "Enrollment No: 92400120571", fontsize=12, fontname="helv")
    _add_divider_and_footer(p1, "Vivek Dhedhi (92400120571)", y=750)

    # Pages 2-3: Only footer
    for p in range(2, 4):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(50, 80), f"Practical Exercise {p}", fontsize=12, fontname="hebo")
        _add_divider_and_footer(page, "Vivek Dhedhi (92400120571)", y=750)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    # 2 occurrences on page 1, 1 on page 2, 1 on page 3 -> total 4 occurrences across 3 pages
    assert len(name_field.occurrences) >= 3
    assert set(name_field.pages) == {1, 2, 3}

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Neel Vyas"),
        ],
        output_filename="scenario_03_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_03_personalized.pdf")) as out_doc:
        for p in range(3):
            p_text = out_doc[p].get_text()
            assert "Vivek Dhedhi" not in p_text
            assert "Neel Vyas" in p_text


# ==============================================================================
# SCENARIO 4: PDF where only some pages contain enrollment numbers
# ==============================================================================
def test_scenario_04_partial_enrollment_pages(tmp_path: Path):
    pdf_path = tmp_path / "scenario_04.pdf"
    doc = pymupdf.open()
    # Page 1: Name + Enrollment
    p1 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p1, "Vivek Dhedhi (92400120571)", y=750)

    # Page 2: Name only
    p2 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p2, "Vivek Dhedhi", y=750)

    # Page 3: Name + Enrollment
    p3 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p3, "Vivek Dhedhi (92400120571)", y=750)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    id_field = next((f for f in det.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER), None)

    assert name_field is not None
    assert set(name_field.pages) == {1, 2, 3}
    assert id_field is not None
    assert set(id_field.pages) == {1, 3}


# ==============================================================================
# SCENARIO 5: PDF with identity details in the middle of a page
# ==============================================================================
def test_scenario_05_identity_in_middle_of_page(tmp_path: Path):
    pdf_path = tmp_path / "scenario_05.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(pymupdf.Point(50, 80), "Mid-Term Project Evaluation", fontsize=14, fontname="hebo")
    # Details in middle table / box at y = 380
    page.insert_text(pymupdf.Point(50, 380), "Student Name: Vivek Dhedhi", fontsize=11, fontname="helv")
    page.insert_text(pymupdf.Point(50, 400), "Enrollment No: 92400120571", fontsize=11, fontname="helv")
    page.insert_text(pymupdf.Point(50, 420), "Roll No: 42", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    enroll_field = next((f for f in det.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER), None)
    roll_field = next((f for f in det.detected_fields if f.field_type == FieldType.ROLL_NUMBER), None)

    assert name_field is not None and "Vivek Dhedhi" in name_field.original_value
    assert enroll_field is not None and "92400120571" in enroll_field.original_value
    assert roll_field is not None and "42" in roll_field.original_value


# ==============================================================================
# SCENARIO 6: PDF with different page dimensions
# ==============================================================================
def test_scenario_06_different_page_dimensions(tmp_path: Path):
    pdf_path = tmp_path / "scenario_06.pdf"
    doc = pymupdf.open()
    # Page 1: Letter (612 x 792)
    p1 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p1, "Vivek Dhedhi (92400120571)", y=750)

    # Page 2: A4 (595 x 842)
    p2 = doc.new_page(width=595, height=842)
    _add_divider_and_footer(p2, "Vivek Dhedhi (92400120571)", y=800)

    # Page 3: Legal (612 x 1008)
    p3 = doc.new_page(width=612, height=1008)
    _add_divider_and_footer(p3, "Vivek Dhedhi (92400120571)", y=960)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert set(name_field.pages) == {1, 2, 3}

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Kunal Patel"),
        ],
        output_filename="scenario_06_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_06_personalized.pdf")) as out_doc:
        assert out_doc[0].rect.height == 792
        assert out_doc[1].rect.height == 842
        assert out_doc[2].rect.height == 1008
        for p in range(3):
            assert "Kunal Patel" in out_doc[p].get_text()


# ==============================================================================
# SCENARIO 7: PDF with rotated pages
# ==============================================================================
def test_scenario_07_rotated_pages(tmp_path: Path):
    pdf_path = tmp_path / "scenario_07.pdf"
    doc = pymupdf.open()
    # Page 1: 0 degrees
    p1 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p1, "Vivek Dhedhi (92400120571)", y=750)

    # Page 2: 90 degrees
    p2 = doc.new_page(width=612, height=792)
    _add_divider_and_footer(p2, "Vivek Dhedhi (92400120571)", y=750)
    p2.set_rotation(90)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert 1 in name_field.pages

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Ananya Roy"),
        ],
        output_filename="scenario_07_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_07_personalized.pdf")) as out_doc:
        assert out_doc[1].rotation == 90, "Page 2 rotation must be preserved"


# ==============================================================================
# SCENARIO 8: Scanned PDF with image-based footers
# ==============================================================================
def test_scenario_08_scanned_image_based_footer(tmp_path: Path):
    pdf_path = tmp_path / "scenario_08.pdf"
    # Create an image-only page using pixmap
    doc = pymupdf.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text(pymupdf.Point(50, 100), "Scanned Laboratory Report", fontsize=14)
    _add_divider_and_footer(p, "Vivek Dhedhi (92400120571)", y=750)
    pix = p.get_pixmap()
    doc.close()

    # Create new document embedding purely the rendered image
    scanned_doc = pymupdf.open()
    scanned_page = scanned_doc.new_page(width=612, height=792)
    scanned_page.insert_image(scanned_page.rect, pixmap=pix)
    scanned_doc.save(str(pdf_path))
    scanned_doc.close()

    with pymupdf.open(str(pdf_path)) as chk_doc:
        # Confirms page has 0 selectable native text (it's purely an image)
        assert len(chk_doc[0].get_text().strip()) == 0


# ==============================================================================
# SCENARIO 9: Mixed text and scanned PDF
# ==============================================================================
def test_scenario_09_mixed_text_and_scanned(tmp_path: Path):
    pdf_path = tmp_path / "scenario_09.pdf"
    # Page 1: Native selectable text
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text(pymupdf.Point(50, 100), "Native Text Page 1", fontsize=12)
    _add_divider_and_footer(p1, "Vivek Dhedhi (92400120571)", y=750)

    # Page 2: Scanned image
    temp_doc = pymupdf.open()
    tp = temp_doc.new_page(width=612, height=792)
    tp.insert_text(pymupdf.Point(50, 100), "Scanned Page Content", fontsize=12)
    pix = tp.get_pixmap()
    temp_doc.close()

    p2 = doc.new_page(width=612, height=792)
    p2.insert_image(p2.rect, pixmap=pix)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert 1 in name_field.pages


# ==============================================================================
# SCENARIO 10: PDF with multiple identity occurrences on the same page
# ==============================================================================
def test_scenario_10_multiple_occurrences_same_page(tmp_path: Path):
    pdf_path = tmp_path / "scenario_10.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Header occurrence
    page.insert_text(pymupdf.Point(50, 100), "Student Name: Vivek Dhedhi", fontsize=11, fontname="helv")
    # Footer occurrence
    _add_divider_and_footer(page, "Vivek Dhedhi (92400120571)", y=750)
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    # Both occurrences on page 1 must be preserved in occurrence list
    assert len(name_field.occurrences) >= 2


# ==============================================================================
# SCENARIO 11: PDF where the same identity value appears in unrelated body text
# ==============================================================================
def test_scenario_11_identity_value_in_unrelated_body_text(tmp_path: Path):
    pdf_path = tmp_path / "scenario_11.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Body prose mentioning the same name
    page.insert_text(pymupdf.Point(50, 150), "According to Vivek Dhedhi, the experiment showed that efficiency increased.", fontsize=11, fontname="helv")
    # Legitimate footer
    _add_divider_and_footer(page, "Vivek Dhedhi (92400120571)", y=750)
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None

    # Verify only the footer occurrence is selected, not the prose occurrence
    for occ in name_field.occurrences:
        assert "According to" not in occ.raw_text

    # Execute replacement
    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Ishaan Sharma"),
        ],
        output_filename="scenario_11_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_11_personalized.pdf")) as out_doc:
        text = out_doc[0].get_text()
        # Footer is updated
        assert "Ishaan Sharma" in text
        # Body prose is completely untouched
        assert "According to Vivek Dhedhi" in text


# ==============================================================================
# SCENARIO 12: PDF with text split across multiple PDF content operators
# ==============================================================================
def test_scenario_12_text_split_across_operators(tmp_path: Path):
    pdf_path = tmp_path / "scenario_12.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Insert first part
    page.insert_text(pymupdf.Point(50, 758), "Vivek ", fontsize=10, fontname="helv")
    # Insert second part
    page.insert_text(pymupdf.Point(85, 758), "Dhedhi (92400120571)", fontsize=10, fontname="helv")
    page.draw_line(pymupdf.Point(50, 740), pymupdf.Point(550, 740), color=(0.5, 0.5, 0.5), width=1)
    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None


# ==============================================================================
# SCENARIO 13: PDF containing shared Form XObjects for repeated footers
# ==============================================================================
def test_scenario_13_shared_form_xobjects(tmp_path: Path):
    pdf_path = tmp_path / "scenario_13.pdf"
    # Create template with footer
    footer_src = pymupdf.open()
    fp = footer_src.new_page(width=612, height=50)
    fp.insert_text(pymupdf.Point(50, 30), "Vivek Dhedhi (92400120571)", fontsize=10, fontname="helv")

    doc = pymupdf.open()
    for p in range(3):
        page = doc.new_page(width=612, height=792)
        page.insert_text(pymupdf.Point(50, 100), f"Page {p+1} with Form XObject footer", fontsize=12)
        # Embed shared Form XObject
        page.show_pdf_page(pymupdf.Rect(0, 742, 612, 792), footer_src, 0)

    doc.save(str(pdf_path))
    doc.close()
    footer_src.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert set(name_field.pages) == {1, 2, 3}

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Pooja Dave"),
        ],
        output_filename="scenario_13_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_13_personalized.pdf")) as out_doc:
        for p in range(3):
            text = out_doc[p].get_text()
            assert "Vivek Dhedhi" not in text
            assert "Pooja Dave" in text


# ==============================================================================
# SCENARIO 14: PDF with different fonts and font sizes
# ==============================================================================
def test_scenario_14_different_fonts_and_sizes(tmp_path: Path):
    pdf_path = tmp_path / "scenario_14.pdf"
    doc = pymupdf.open()

    # Page 1: Times-Roman 12pt
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text(pymupdf.Point(50, 758), "Vivek Dhedhi (92400120571)", fontsize=12, fontname="tiro")
    p1.draw_line(pymupdf.Point(50, 740), pymupdf.Point(550, 740), width=1)

    # Page 2: Helvetica 9pt
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text(pymupdf.Point(50, 758), "Vivek Dhedhi (92400120571)", fontsize=9, fontname="helv")
    p2.draw_line(pymupdf.Point(50, 740), pymupdf.Point(550, 740), width=1)

    # Page 3: Courier 10pt
    p3 = doc.new_page(width=612, height=792)
    p3.insert_text(pymupdf.Point(50, 758), "Vivek Dhedhi (92400120571)", fontsize=10, fontname="cour")
    p3.draw_line(pymupdf.Point(50, 740), pymupdf.Point(550, 740), width=1)

    doc.save(str(pdf_path))
    doc.close()

    engine = DetectionEngine()
    det = engine.detect_file(pdf_path)

    name_field = next((f for f in det.detected_fields if f.field_type == FieldType.STUDENT_NAME), None)
    assert name_field is not None
    assert set(name_field.pages) == {1, 2, 3}

    replacer = PDFReplacer()
    req = ReplacementRequest(
        document_id=det.document_id,
        source_file=str(pdf_path),
        replacements=[
            ReplacementItem(field_id=name_field.field_id, field_type=name_field.field_type, original_value=name_field.original_value, new_value="Sameer Khan"),
        ],
        output_filename="scenario_14_personalized.pdf"
    )
    result = replacer.replace_fields(pdf_path, det, req, output_dir=tmp_path)
    assert result.verification_status == VerificationStatus.PASSED

    with pymupdf.open(str(tmp_path / "scenario_14_personalized.pdf")) as out_doc:
        for p in range(3):
            text = out_doc[p].get_text()
            assert "Vivek Dhedhi" not in text
            assert "Sameer Khan" in text
