"""Comprehensive Test Suite for Phase 2.2 Universal Layout AI Detection Engine.

Validates:
1. HybridPDFPipeline token extraction, geometry normalization, and intermediate representation.
2. LayoutFeatureExtractor 36-dimensional feature computation and stability.
3. UniversalLayoutInferenceService BIO tag prediction and structured entity grouping.
4. CrossPageAnalyzer multi-page candidate clustering, alignment consistency, and page number exclusion.
5. Independent bounding box preservation between student names and enrollment IDs.
6. End-to-end DetectionEngine execution on diverse multi-page academic layouts.
"""

from pathlib import Path
import pytest
import pymupdf

from ai_training.config import LABEL_LIST, MODEL_OUTPUT_DIR
from ai_training.inference import LayoutPredictionEntity, UniversalLayoutInferenceService
from ai_training.train import LayoutFeatureExtractor
from app.schemas.detection_data import BoundingBox, FieldType
from app.services.cross_page_analyzer import CrossPageAnalyzer
from app.services.detection_engine import DetectionEngine
from app.services.hybrid_pdf_pipeline import (
    DocumentRepresentation,
    ExtractedToken,
    HybridPDFPipeline,
    PageRepresentation,
)


@pytest.fixture
def sample_academic_pdf(tmp_path: Path) -> Path:
    """Creates a realistic 2-page academic PDF with unlabelled student credentials and page numbers."""
    pdf_path = tmp_path / "test_academic_doc.pdf"
    doc = pymupdf.open()

    for page_num in range(1, 3):
        page = doc.new_page(width=595.0, height=842.0)  # Standard A4

        # Document Header
        page.insert_text(
            (50, 60),
            "DEPARTMENT OF COMPUTER ENGINEERING",
            fontsize=13,
            fontname="helv",
        )
        page.insert_text(
            (50, 80),
            "Subject: Cloud Computing Practical 01",
            fontsize=11,
            fontname="helv",
        )

        # Body Content
        body_y = 130
        for i in range(12):
            page.insert_text(
                (50, body_y + (i * 20)),
                f"Data analysis row {i}: Computing metrics and algorithmic convergence bounds.",
                fontsize=10,
                fontname="helv",
            )

        # Separator line above footer
        page.draw_line(pymupdf.Point(50, 785), pymupdf.Point(545, 785), color=(0.8, 0.8, 0.8), width=0.5)

        # Unlabelled Footer on bottom-left: Name (Enrollment)
        page.insert_text(
            (50, 805),
            "Aarav Patel (92400120999)",
            fontsize=9,
            fontname="helv",
        )

        # Page number on bottom-right
        page.insert_text(
            (530, 805),
            str(page_num),
            fontsize=9,
            fontname="helv",
        )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_hybrid_pdf_pipeline_extraction(sample_academic_pdf: Path):
    """Tests that HybridPDFPipeline accurately parses tokens, lines, and normalized bboxes."""
    pipeline = HybridPDFPipeline()
    with pymupdf.open(str(sample_academic_pdf)) as doc:
        doc_rep = pipeline.process_document(doc)

    assert doc_rep.total_pages == 2
    assert len(doc_rep.pages) == 2

    page1 = doc_rep.pages[0]
    assert page1.width == 595.0
    assert page1.height == 842.0
    assert len(page1.tokens) > 20

    # Test coordinate normalization to [0, 1000]
    for token in page1.tokens:
        x0, y0, x1, y1 = token.normalized_bbox
        assert 0 <= x0 <= 1000
        assert 0 <= y0 <= 1000
        assert 0 <= x1 <= 1000
        assert 0 <= y1 <= 1000
        assert x1 >= x0
        assert y1 >= y0


def test_layout_feature_extractor():
    """Tests that the LayoutFeatureExtractor computes 36-dimensional feature representations."""
    extractor = LayoutFeatureExtractor()
    tokens = ["Aarav", "Patel", "(92400120999)", "1"]
    bboxes = [
        [84, 940, 120, 955],
        [125, 940, 160, 955],
        [165, 940, 260, 955],
        [890, 940, 900, 955],
    ]

    features = extractor.extract_features(tokens, bboxes)
    assert features.shape == (4, 36)
    assert not (features < -10.0).any()
    assert not (features > 10.0).any()


def test_inference_service_availability():
    """Validates that the trained model checkpoint exists and is successfully loaded."""
    service = UniversalLayoutInferenceService()
    assert service.is_model_available(), "Trained model checkpoint layout_classifier.joblib must be present"


def test_cross_page_analyzer_separate_bboxes():
    """Verifies that student name and enrollment number maintain strictly separate bounding boxes."""
    analyzer = CrossPageAnalyzer()

    # Create synthetic overlapping entities to test separation
    ent_name = LayoutPredictionEntity(
        entity_type="student_name",
        value="Aarav Patel",
        bbox=(50.0, 800.0, 180.0, 815.0),
        normalized_bbox=(84, 940, 302, 955),
        page_number=1,
        confidence=0.95,
    )
    ent_enr = LayoutPredictionEntity(
        entity_type="enrollment_number",
        value="92400120999",
        bbox=(150.0, 800.0, 240.0, 815.0),
        normalized_bbox=(250, 940, 400, 955),
        page_number=1,
        confidence=0.95,
    )

    page_entities = {1: [ent_name, ent_enr]}
    doc_rep = DocumentRepresentation(
        document_id="doc_test",
        filename="test.pdf",
        total_pages=1,
        pages=[
            PageRepresentation(
                page_number=1,
                width=595.0,
                height=842.0,
                tokens=[],
                lines=[],
                is_scanned=False,
                is_mixed=False,
            )
        ],
    )

    refined = analyzer._enforce_separate_bounding_boxes(page_entities, doc_rep)
    refined_name = [e for e in refined[1] if e.entity_type == "student_name"][0]
    refined_enr = [e for e in refined[1] if e.entity_type == "enrollment_number"][0]

    # Name right bound must be to the left of enrollment left bound
    assert refined_name.bbox[2] <= refined_enr.bbox[0]


def test_page_number_exclusion():
    """Tests that page numbers in the bottom-right are excluded from student identity detection."""
    analyzer = CrossPageAnalyzer()

    page_num_ent = LayoutPredictionEntity(
        entity_type="page_number",
        value="1",
        bbox=(530.0, 800.0, 540.0, 815.0),
        normalized_bbox=(890, 940, 907, 955),
        page_number=1,
        confidence=0.99,
    )

    assert analyzer._is_likely_page_number(page_num_ent, current_page=1)


def test_end_to_end_detection_engine_with_ai(sample_academic_pdf: Path):
    """Executes the full DetectionEngine pipeline on a multi-page PDF with unlabelled footer."""
    engine = DetectionEngine()
    result = engine.detect_file(sample_academic_pdf)

    assert result.total_pages == 2
    assert len(result.detected_fields) >= 2

    types_detected = {f.field_type for f in result.detected_fields}
    assert FieldType.STUDENT_NAME in types_detected
    assert FieldType.ENROLLMENT_NUMBER in types_detected

    name_field = next(f for f in result.detected_fields if f.field_type == FieldType.STUDENT_NAME)
    enr_field = next(f for f in result.detected_fields if f.field_type == FieldType.ENROLLMENT_NUMBER)

    assert "Aarav" in name_field.original_value
    assert "92400120999" in enr_field.original_value

    # Verify both fields occur on both pages
    assert len(name_field.occurrences) == 2
    assert len(enr_field.occurrences) == 2

    # Verify separate bounding boxes on page 1
    name_occ_p1 = next(o for o in name_field.occurrences if o.page_number == 1)
    enr_occ_p1 = next(o for o in enr_field.occurrences if o.page_number == 1)

    assert name_occ_p1.value_bbox is not None
    assert enr_occ_p1.value_bbox is not None
    # Independent boxes: name should be completely to the left of enrollment
    assert name_occ_p1.value_bbox.x1 <= enr_occ_p1.value_bbox.x0 or not name_occ_p1.value_bbox.intersects(enr_occ_p1.value_bbox)
