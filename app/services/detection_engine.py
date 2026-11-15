"""Intelligent Footer Detection and Personal Information Recognition Engine.

Orchestrates the Phase 2 detection pipeline:
1. Validates input PDF files or byte streams.
2. Analyzes page dimensions and identifies geometric footer zones.
3. Segments pages into structured lines, spans, and bounding boxes.
4. Identifies student labels (Student Name, Enrollment No, Roll No, Student ID).
5. Isolates and validates associated field values.
6. Groups repeated occurrences across pages and preserves exact bounding boxes.
7. Detects cross-page conflicting values and generates explainable confidence scores.
8. Produces structured DetectionResult models supporting human-in-the-loop review.
"""

import hashlib
from pathlib import Path
from typing import Optional
import pymupdf

from app.core.config import Settings, settings
from app.core.exceptions import (
    DocMorphError,
    InvalidPDFError,
    PDFProcessingError,
    PDFValidationError,
)
from app.schemas.detection_data import (
    ConfidenceLevel,
    DetectionResult,
    DetectionSummary,
    FieldType,
    ReviewStatus,
)
from app.services.confidence_scorer import ConfidenceScorer
from app.services.cross_page_analyzer import CrossPageAnalyzer
from app.services.field_detector import FieldDetector
from app.services.field_grouper import FieldGrouper
from app.services.footer_detector import FooterDetector
from app.services.footer_verifier import FooterVerifier
from app.schemas.footer_verification import DocumentFooterVerification, FooterStatus
from app.services.hybrid_pdf_pipeline import HybridPDFPipeline
from app.services.text_segmenter import TextSegmenter
from app.services.unlabelled_identity_detector import UnlabelledIdentityDetector
from app.services.value_extractor import ExtractedFieldValue, ValueExtractor
from app.utils.file_validator import FileValidator
from ai_training.inference import UniversalLayoutInferenceService


class DetectionEngine:
    """Production-grade Intelligent Detection Engine for student credentials in PDFs."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize detection engine with configuration and modular services.

        Args:
            config: Application settings instance.
        """
        self.config = config
        self.footer_detector = FooterDetector(config=config)
        self.footer_verifier = FooterVerifier(footer_detector=self.footer_detector)
        self.confidence_scorer = ConfidenceScorer(config=config)
        self.field_grouper = FieldGrouper(confidence_scorer=self.confidence_scorer)
        self.unlabelled_detector = UnlabelledIdentityDetector()
        self.hybrid_pipeline = HybridPDFPipeline()
        self.ai_inference = UniversalLayoutInferenceService()
        self.cross_page_analyzer = CrossPageAnalyzer()

    def detect_file(
        self,
        file_path: Path | str,
        base_dir: Optional[Path] = None,
    ) -> DetectionResult:
        """Runs the detection pipeline on an on-disk PDF file.

        Args:
            file_path: Target PDF file path.
            base_dir: Optional boundary path to prevent traversal.

        Returns:
            DetectionResult structured model.

        Raises:
            PDFValidationError: If file validation or encryption checks fail.
            PDFProcessingError: If internal parsing errors occur.
        """
        resolved_path = FileValidator.validate_file_path(
            file_path=file_path,
            base_dir=base_dir,
            config=self.config,
        )
        sanitized_filename = FileValidator.sanitize_filename(resolved_path.name)

        try:
            with pymupdf.open(str(resolved_path)) as doc:
                FileValidator.validate_pdf_document(doc)
                return self.detect_document(doc=doc, filename=sanitized_filename)
        except (PDFValidationError, DocMorphError):
            raise
        except pymupdf.FileDataError as e:
            raise InvalidPDFError("The PDF document is corrupted, damaged, or unreadable.") from e
        except Exception as e:
            raise PDFProcessingError(
                f"An unexpected error occurred during detection: {type(e).__name__}"
            ) from e

    def detect_bytes(
        self,
        data: bytes,
        filename: str = "document.pdf",
    ) -> DetectionResult:
        """Runs the detection pipeline on an in-memory PDF byte stream.

        Args:
            data: Binary PDF data.
            filename: Target file name.

        Returns:
            DetectionResult structured model.

        Raises:
            PDFValidationError: If validation fails.
            PDFProcessingError: If processing fails.
        """
        FileValidator.validate_bytes(data=data, filename=filename, config=self.config)
        sanitized_filename = FileValidator.sanitize_filename(filename)

        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                FileValidator.validate_pdf_document(doc)
                return self.detect_document(doc=doc, filename=sanitized_filename)
        except (PDFValidationError, DocMorphError):
            raise
        except pymupdf.FileDataError as e:
            raise InvalidPDFError("The PDF document is corrupted, damaged, or unreadable.") from e
        except Exception as e:
            raise PDFProcessingError(
                f"An unexpected error occurred during detection: {type(e).__name__}"
            ) from e

    def detect_document(
        self,
        doc: pymupdf.Document,
        filename: str = "document.pdf",
    ) -> DetectionResult:
        """Executes the multi-layer detection pipeline on an open PyMuPDF document.

        Args:
            doc: Open PyMuPDF Document instance.
            filename: Name of the file being processed.

        Returns:
            DetectionResult structured model.
        """
        total_pages = doc.page_count
        document_id = self._generate_document_id(filename, total_pages)

        # 1. Segment structured lines for all pages
        structured_pages = {
            page_idx: TextSegmenter.segment_page(
                page=page,
                page_number=page_idx,
            )
            for page_idx, page in enumerate(doc, start=1)
        }

        # 2. Run dedicated Footer Verification Layer (Multi-signal layout, negative, multi-page)
        footer_verification = self.footer_verifier.verify_document(
            doc=doc,
            structured_pages=structured_pages,
        )

        all_extracted_values: list[ExtractedFieldValue] = []

        for page_idx, page in enumerate(doc, start=1):
            page_height = page.rect.height
            structured_lines = structured_pages.get(page_idx, [])
            page_verif = (
                footer_verification.page_results[page_idx - 1]
                if page_idx - 1 < len(footer_verification.page_results)
                else None
            )

            # Determine footer boundary strictly from verification layer
            if page_verif and page_verif.status == FooterStatus.FOOTER_CONFIRMED:
                footer_boundary_y = page_verif.boundary_y
                has_page_footer = True
            elif page_verif and page_verif.status == FooterStatus.FOOTER_UNCERTAIN:
                footer_boundary_y = page_verif.boundary_y
                has_page_footer = True
            else:
                footer_boundary_y = page_height * 0.96  # Negative/unconfirmed footer: reject bottom body text
                has_page_footer = False

            separator_y = page_verif.separator_y if page_verif else self.footer_detector.find_footer_separator_line(page)

            # Tag footer region membership strictly based on verified boundary
            for line in structured_lines:
                mid_y = (line.bbox.y0 + line.bbox.y1) / 2.0
                line.is_in_footer = has_page_footer and (mid_y >= footer_boundary_y or line.bbox.y0 >= footer_boundary_y)

            # Track lines that produced explicit label detections to prevent redundant scanning
            matched_line_indices: set[int] = set()

            # Pass 1: Explicit Label-Based Student Field Detection
            for line_idx, line in enumerate(structured_lines):
                # Layer 3: Student Field Label Recognition
                matched_labels = FieldDetector.find_field_labels(line.text)
                if not matched_labels:
                    continue

                # Filter generic labels (like generic 'Name:') if not in header/footer zones
                mid_y = (line.bbox.y0 + line.bbox.y1) / 2.0
                is_header_or_footer = line.is_in_footer or mid_y <= page_height * 0.35
                has_specific_label = any(m.is_specific for m in matched_labels)

                if not is_header_or_footer and not has_specific_label:
                    continue

                matched_line_indices.add(line_idx)

                # Check if there is a next line for multi-line association
                next_line = (
                    structured_lines[line_idx + 1]
                    if line_idx + 1 < len(structured_lines)
                    else None
                )

                # Layer 4 & 5: Value Extraction & Coordinate Resolution
                values = ValueExtractor.extract_from_line(
                    line=line,
                    matched_labels=matched_labels,
                    page=page,
                    next_line=next_line,
                )
                all_extracted_values.extend(values)

            # Pass 2: Unlabelled Student Identity Recognition
            # STRICTLY skipped if the page footer is NOT confirmed/uncertain (e.g. FOOTER_NOT_FOUND)
            if has_page_footer:
                for line_idx, line in enumerate(structured_lines):
                    if line_idx in matched_line_indices:
                        continue
                    if not line.is_in_footer:
                        continue

                    unlabelled_values = self.unlabelled_detector.detect_in_line(
                        line=line,
                        page=page,
                        separator_y=separator_y,
                    )
                    if unlabelled_values:
                        if page_verif and page_verif.status == FooterStatus.FOOTER_UNCERTAIN:
                            for uv in unlabelled_values:
                                uv.confidence = min(0.70, uv.confidence)
                        all_extracted_values.extend(unlabelled_values)

        # Fallback: Scan bottom-left ONLY if document has verified/uncertain footer!
        if footer_verification.status in (FooterStatus.FOOTER_CONFIRMED, FooterStatus.FOOTER_UNCERTAIN):
            has_enrollment = any(
                ev.field_type == FieldType.ENROLLMENT_NUMBER for ev in all_extracted_values
            )
            if not has_enrollment:
                fallback_enrollments = self.unlabelled_detector.scan_bottom_left_for_enrollment(doc)
                if fallback_enrollments:
                    all_extracted_values.extend(fallback_enrollments)

        # Pass 3: Layout-Aware Universal AI Document Understanding & Cross-Page Analysis
        try:
            # Check what fields are already reliably detected across pages
            counts_by_type: dict[FieldType, int] = defaultdict(int)
            for ev in all_extracted_values:
                counts_by_type[ev.field_type] += 1

            established_types = {
                ev.field_type for ev in all_extracted_values if not ev.is_unlabelled
            }
            for ft, count in counts_by_type.items():
                if count >= min(2, total_pages):
                    established_types.add(ft)

            doc_rep = self.hybrid_pipeline.process_document(doc)
            page_entities: dict[int, list] = {}
            for page_rep in doc_rep.pages:
                entities = self.ai_inference.predict_page(page_rep)
                if entities:
                    page_entities[page_rep.page_number] = entities

            if page_entities:
                ai_extracted_values = self.cross_page_analyzer.analyze_document(
                    doc_rep=doc_rep,
                    page_entities=page_entities,
                )
                for ai_val in ai_extracted_values:
                    # If this field type was already cleanly established, avoid injecting unverified candidates
                    if ai_val.field_type in established_types:
                        continue

                    exists = any(
                        ex.field_type == ai_val.field_type
                        and ex.occurrence.page_number == ai_val.occurrence.page_number
                        and (
                            ex.value.strip().lower() == ai_val.value.strip().lower()
                            or (ex.occurrence.value_bbox and ex.occurrence.value_bbox.intersects(ai_val.occurrence.bbox))
                        )
                        for ex in all_extracted_values
                    )
                    if not exists:
                        all_extracted_values.append(ai_val)
        except Exception:
            # Fall back gracefully to rule-based extractions if AI pipeline encounters an unexpected format
            pass

        # Layer 6 & 7: Grouping, Multi-page Occurrences, and Conflict Detection
        detected_fields, conflicts = self.field_grouper.group_and_resolve(
            extracted_values=all_extracted_values,
            total_pages=total_pages,
            document_id=document_id,
        )

        # Compute summary metrics
        high_cnt = sum(1 for f in detected_fields if f.confidence_level == ConfidenceLevel.HIGH)
        med_cnt = sum(1 for f in detected_fields if f.confidence_level == ConfidenceLevel.MEDIUM)
        low_cnt = sum(1 for f in detected_fields if f.confidence_level == ConfidenceLevel.LOW)
        rev_cnt = sum(1 for f in detected_fields if f.review_required)

        fields_by_type: dict[str, int] = {}
        for f in detected_fields:
            fields_by_type[f.field_type.value] = fields_by_type.get(f.field_type.value, 0) + 1

        summary = DetectionSummary(
            total_fields_detected=len(detected_fields),
            high_confidence_count=high_cnt,
            medium_confidence_count=med_cnt,
            low_confidence_count=low_cnt,
            review_required_count=rev_cnt,
            conflicts_count=len(conflicts),
            fields_by_type=fields_by_type,
        )

        return DetectionResult(
            document_id=document_id,
            filename=filename,
            total_pages=total_pages,
            detected_fields=detected_fields,
            conflicts=conflicts,
            detection_summary=summary,
            footer_verification=footer_verification,
        )

    @staticmethod
    def _generate_document_id(filename: str, page_count: int) -> str:
        """Generates a stable, unique document identifier."""
        raw = f"{filename}_{page_count}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"doc_{digest}"
