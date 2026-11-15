"""Smart Manual Detection Service for DocMorph (Phase C).

Enables user-guided detection via area selection (rectangle) or text selection.
Selected content acts as an input search boundary for the local engine,
NOT an instruction to manually edit PDF content.
"""

import re
from typing import Optional
import pymupdf

from app.schemas.detection_data import (
    BoundingBox,
    ConfidenceLevel,
    DetectedField,
    FieldOccurrence,
    FieldType,
    ReviewStatus,
)
from app.schemas.footer_verification import FooterStatus
from app.schemas.manual_detection import (
    ManualDetectionResponse,
    ManualSelectionRequest,
    SelectionType,
)
from app.services.field_detector import FieldDetector
from app.services.footer_verifier import FooterVerifier
from app.services.text_segmenter import StructuredLine, TextSegmenter
from app.services.unlabelled_identity_detector import UnlabelledIdentityDetector
from app.services.value_extractor import ValueExtractor


class SmartManualDetector:
    """Production-grade service processing user-guided area and text selections."""

    def __init__(self, footer_verifier: Optional[FooterVerifier] = None) -> None:
        self.footer_verifier = footer_verifier or FooterVerifier()
        self.unlabelled_detector = UnlabelledIdentityDetector()

    def process_selection(
        self,
        doc: pymupdf.Document,
        request: ManualSelectionRequest,
    ) -> ManualDetectionResponse:
        """Processes an area or text selection on a document page.

        Args:
            doc: Open PyMuPDF Document instance.
            request: ManualSelectionRequest containing selection geometry and type.

        Returns:
            ManualDetectionResponse with verification outcome and extracted student fields.
        """
        # 1. Page bounds check
        if request.page_number < 1 or request.page_number > doc.page_count:
            return ManualDetectionResponse(
                document_id=request.document_id,
                page_number=request.page_number,
                selection_type=request.selection_type,
                resolved_pdf_bbox=BoundingBox(x0=0, y0=0, x1=0, y1=0),
                extracted_text="",
                footer_status=FooterStatus.DOCUMENT_UNREADABLE,
                confidence=0.0,
                detected_fields=[],
                negative_reasons=[f"Page number {request.page_number} is out of bounds (1..{doc.page_count})"],
                summary_message="Selected page does not exist in this document.",
            )

        page = doc[request.page_number - 1]
        page_width = page.rect.width
        page_height = page.rect.height

        # 2. Coordinate Resolution & Validation
        resolved_box, coord_error = self._resolve_and_validate_coords(page, request, page_width, page_height)
        if coord_error:
            return ManualDetectionResponse(
                document_id=request.document_id,
                page_number=request.page_number,
                selection_type=request.selection_type,
                resolved_pdf_bbox=resolved_box or BoundingBox(x0=0, y0=0, x1=0, y1=0),
                extracted_text="",
                footer_status=FooterStatus.FOOTER_NOT_FOUND,
                confidence=0.90,
                detected_fields=[],
                negative_reasons=[coord_error],
                summary_message=f"Invalid selection: {coord_error}",
            )

        # 3. Extract structured text lines located strictly within the selection boundary
        all_lines = TextSegmenter.segment_page(page, request.page_number)
        selected_lines = self._filter_lines_in_bbox(all_lines, resolved_box)

        # Build extracted text string
        extracted_text = " ".join(line.text.strip() for line in selected_lines if line.text.strip()).strip()

        if not selected_lines or not extracted_text:
            return ManualDetectionResponse(
                document_id=request.document_id,
                page_number=request.page_number,
                selection_type=request.selection_type,
                resolved_pdf_bbox=resolved_box,
                extracted_text="",
                footer_status=FooterStatus.FOOTER_NOT_FOUND,
                confidence=0.90,
                detected_fields=[],
                negative_reasons=["No selectable text found inside the selected region"],
                summary_message="The selected region contains no text.",
            )

        # 4. Pass selected content to the Footer Verification Layer
        verification_outcome = self._verify_selected_content(
            page=page,
            page_number=request.page_number,
            selected_lines=selected_lines,
            resolved_box=resolved_box,
            page_height=page_height,
            selection_type=request.selection_type,
        )

        status = verification_outcome["status"]
        confidence = verification_outcome["confidence"]
        negative_reasons = verification_outcome["negative_reasons"]

        # 5. Extract Student Information Fields
        detected_fields: list[DetectedField] = []

        if status in (FooterStatus.FOOTER_CONFIRMED, FooterStatus.FOOTER_UNCERTAIN):
            detected_fields = self._extract_student_fields_from_selection(
                page=page,
                page_number=request.page_number,
                selected_lines=selected_lines,
                resolved_box=resolved_box,
                is_uncertain=(status == FooterStatus.FOOTER_UNCERTAIN),
            )

        # If student fields were extracted but status was uncertain/not-found without fields
        if status == FooterStatus.FOOTER_CONFIRMED and not detected_fields:
            summary_msg = "A possible footer was identified, but no supported student information could be found."
        elif status == FooterStatus.FOOTER_CONFIRMED:
            summary_msg = f"Recognizable footer verified. Identified {len(detected_fields)} student field(s)."
        elif status == FooterStatus.FOOTER_UNCERTAIN:
            if detected_fields:
                summary_msg = f"Footer needs review. Identified {len(detected_fields)} field(s) with partial evidence."
            else:
                summary_msg = "Selected area could not be confidently verified as a footer."
        else:
            summary_msg = "The selected region does not appear to contain recognizable footer information."

        return ManualDetectionResponse(
            document_id=request.document_id,
            page_number=request.page_number,
            selection_type=request.selection_type,
            resolved_pdf_bbox=resolved_box,
            extracted_text=extracted_text,
            footer_status=status,
            confidence=confidence,
            detected_fields=detected_fields,
            negative_reasons=negative_reasons,
            summary_message=summary_msg,
        )

    def _resolve_and_validate_coords(
        self,
        page: pymupdf.Page,
        request: ManualSelectionRequest,
        page_width: float,
        page_height: float,
    ) -> tuple[Optional[BoundingBox], Optional[str]]:
        """Resolves input coordinates to PDF user points and validates bounds."""
        resolved: Optional[BoundingBox] = None

        if request.selection_type == SelectionType.TEXT:
            if request.text_bbox is not None:
                # Add slight padding around highlighted text to capture line context
                resolved = BoundingBox(
                    x0=max(0.0, request.text_bbox.x0 - 8.0),
                    y0=max(0.0, request.text_bbox.y0 - 4.0),
                    x1=min(page_width, request.text_bbox.x1 + 8.0),
                    y1=min(page_height, request.text_bbox.y1 + 4.0),
                )
            elif request.selected_text:
                # Search page text for string
                search_results = page.search_for(request.selected_text.strip())
                if search_results:
                    hit = search_results[0]
                    resolved = BoundingBox(
                        x0=max(0.0, hit.x0 - 8.0),
                        y0=max(0.0, hit.y0 - 4.0),
                        x1=min(page_width, hit.x1 + 8.0),
                        y1=min(page_height, hit.y1 + 4.0),
                    )
                else:
                    return None, f"Selected text '{request.selected_text}' could not be located on page"
            else:
                return None, "Text selection requires selected_text or text_bbox"

        elif request.selection_type == SelectionType.AREA:
            if request.raw_bbox is not None:
                resolved = request.raw_bbox
            elif request.normalized_bbox is not None:
                nx0, ny0, nx1, ny1 = request.normalized_bbox
                resolved = BoundingBox(
                    x0=(nx0 / 1000.0) * page_width,
                    y0=(ny0 / 1000.0) * page_height,
                    x1=(nx1 / 1000.0) * page_width,
                    y1=(ny1 / 1000.0) * page_height,
                )
            else:
                return None, "Area selection requires raw_bbox or normalized_bbox"

        if resolved is None:
            return None, "No coordinate geometry provided"

        # Check for inverted or zero-size rectangle
        if resolved.x1 <= resolved.x0 or resolved.y1 <= resolved.y0:
            return None, f"Selected area has invalid dimensions ({resolved.width:.1f} x {resolved.height:.1f})"

        # Check for minimal usable area
        if resolved.area < 15.0:
            return None, "Selected area is too small to contain readable text"

        # Clamp strictly to page dimensions
        clamped = BoundingBox(
            x0=max(0.0, min(page_width, resolved.x0)),
            y0=max(0.0, min(page_height, resolved.y0)),
            x1=max(0.0, min(page_width, resolved.x1)),
            y1=max(0.0, min(page_height, resolved.y1)),
        )

        return clamped, None

    def _filter_lines_in_bbox(
        self,
        lines: list[StructuredLine],
        bbox: BoundingBox,
    ) -> list[StructuredLine]:
        """Filters structured lines whose content falls inside the selection rectangle.

        Strictly prevents leaking unrelated text outside the selection.
        """
        filtered: list[StructuredLine] = []

        for line in lines:
            line_mid_y = (line.bbox.y0 + line.bbox.y1) / 2.0
            line_mid_x = (line.bbox.x0 + line.bbox.x1) / 2.0

            # Condition 1: Center of line is inside selection
            if bbox.contains_point(line_mid_x, line_mid_y):
                filtered.append(line)
                continue

            # Condition 2: Significant horizontal and vertical overlap
            if bbox.intersects(line.bbox):
                overlap_x0 = max(bbox.x0, line.bbox.x0)
                overlap_x1 = min(bbox.x1, line.bbox.x1)
                overlap_y0 = max(bbox.y0, line.bbox.y0)
                overlap_y1 = min(bbox.y1, line.bbox.y1)

                overlap_area = max(0.0, overlap_x1 - overlap_x0) * max(0.0, overlap_y1 - overlap_y0)
                vert_overlap = (overlap_y1 - overlap_y0) / max(1.0, line.bbox.height)
                if vert_overlap >= 0.40 and (overlap_area / max(1.0, line.bbox.area)) >= 0.20:
                    filtered.append(line)
                    continue

        return filtered

    def _verify_selected_content(
        self,
        page: pymupdf.Page,
        page_number: int,
        selected_lines: list[StructuredLine],
        resolved_box: BoundingBox,
        page_height: float,
        selection_type: SelectionType,
    ) -> dict:
        """Applies Phase B Footer Verification logic to the selected region."""
        candidate_texts = [l.text.strip() for l in selected_lines if l.text.strip()]
        combined_text = " ".join(candidate_texts)
        lower_combined = combined_text.lower()

        negative_score = 0.0
        layout_score = 0.0
        semantic_score = 0.0
        negative_reasons: list[str] = []

        # 1. Negative Academic Keywords Check
        for kw in FooterVerifier.NEGATIVE_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", lower_combined):
                negative_score += 40.0
                negative_reasons.append(f"Contains negative academic/body keyword: '{kw}'")
                break

        # 2. Experiment / Chapter / Section Number Check
        if FooterVerifier.RE_EXP_CHAPTER.search(combined_text):
            negative_score += 45.0
            negative_reasons.append(f"Contains experiment/chapter pattern: '{combined_text[:30]}'")

        # 3. Solitary Page Number Check
        if len(candidate_texts) == 1 and FooterVerifier.RE_SOLITARY_PAGE_NUMBER.match(candidate_texts[0]):
            negative_score += 45.0
            negative_reasons.append("Solitary page number alone (not a student footer)")

        # 4. Prose / Running Paragraph Check
        prose_matches = FooterVerifier.RE_PROSE_INDICATORS.findall(combined_text)
        if len(prose_matches) >= 3 or (len(combined_text.split()) > 14 and combined_text.endswith(".")):
            negative_score += 40.0
            negative_reasons.append(f"Prose-like running sentence structure ({len(prose_matches)} prose indicators)")

        # 5. Layout Signals
        # Vector separator check
        separator_y = self.footer_verifier.footer_detector.find_footer_separator_line(page)
        if separator_y is not None and resolved_box.y0 >= (separator_y - 15.0):
            layout_score += 35.0

        # Footer compactness (footers are usually 1 or 2 lines)
        if len(selected_lines) in (1, 2):
            layout_score += 25.0
        elif len(selected_lines) >= 5:
            negative_score += 30.0
            negative_reasons.append(f"Selected area contains {len(selected_lines)} lines (typical footers are 1-2 lines)")

        # Position in lower part of page
        if resolved_box.y0 >= page_height * 0.75:
            layout_score += 25.0
        elif resolved_box.y0 >= page_height * 0.65:
            layout_score += 10.0
        else:
            # User selected top/middle body region
            negative_score += 25.0
            negative_reasons.append("Selected region is in top/middle body region (y0 < 65% page height)")

        # 6. Semantic Signals (Supporting ONLY)
        has_id_pair = bool(
            re.search(r"([A-Za-z\s.'-]{3,35})\s*[\(\[]\s*(\d{6,18}|[A-Za-z0-9\-_]{5,20})\s*[\)\]]", combined_text)
            or re.search(r"([A-Za-z\s.'-]{3,35})\s*[-–—|]\s*(\d{6,18})", combined_text)
        )
        if has_id_pair and negative_score < 35.0:
            semantic_score += 35.0

        has_labels = bool(
            re.search(r"(?i)\b(?:name|enrollment(?:\s*no\.?)?|roll(?:\s*no\.?)?|student\s*id)\s*:", combined_text)
        )
        if has_labels and negative_score < 35.0:
            semantic_score += 30.0

        # In manual selection mode, the user explicitly chose this area as a hint.
        # User intention provides a modest bonus (+15) if no negative markers are present.
        if negative_score == 0.0:
            layout_score += 15.0

        net_score = (layout_score + semantic_score) - negative_score

        # Decide Status
        if negative_score >= 40.0:
            status = FooterStatus.FOOTER_NOT_FOUND
            confidence = max(0.85, min(0.99, negative_score / 100.0))
        elif net_score >= 50.0:
            status = FooterStatus.FOOTER_CONFIRMED
            confidence = min(0.98, max(0.75, net_score / 100.0))
        elif net_score >= 20.0 and negative_score < 30.0:
            status = FooterStatus.FOOTER_UNCERTAIN
            confidence = 0.55
        else:
            status = FooterStatus.FOOTER_NOT_FOUND
            confidence = 0.85

        return {
            "status": status,
            "confidence": round(confidence, 3),
            "negative_reasons": list(set(negative_reasons)),
            "net_score": net_score,
        }

    def _extract_student_fields_from_selection(
        self,
        page: pymupdf.Page,
        page_number: int,
        selected_lines: list[StructuredLine],
        resolved_box: BoundingBox,
        is_uncertain: bool = False,
    ) -> list[DetectedField]:
        """Extracts and structures supported student fields found inside selection."""
        detected_fields: list[DetectedField] = []
        matched_line_indices: set[int] = set()

        separator_y = self.footer_verifier.footer_detector.find_footer_separator_line(page)

        # 1. Pass 1: Explicit labels ("Name: ...", "Enrollment No: ...")
        for line_idx, line in enumerate(selected_lines):
            matched_labels = FieldDetector.find_field_labels(line.text)
            if not matched_labels:
                continue

            matched_line_indices.add(line_idx)
            next_line = selected_lines[line_idx + 1] if line_idx + 1 < len(selected_lines) else None
            values = ValueExtractor.extract_from_line(
                line=line,
                matched_labels=matched_labels,
                page=page,
                next_line=next_line,
            )
            for v in values:
                conf = 0.65 if is_uncertain else 0.92
                field_id = f"{v.field_type.value}_{page_number}_man_{len(detected_fields)}"
                detected_fields.append(
                    DetectedField(
                        field_id=field_id,
                        field_type=v.field_type,
                        original_value=v.value,
                        suggested_value=v.value,
                        confidence=conf,
                        confidence_level=ConfidenceLevel.MEDIUM if is_uncertain else ConfidenceLevel.HIGH,
                        status=ReviewStatus.PENDING,
                        review_required=is_uncertain,
                        occurrences=[v.occurrence],
                        detection_method="manual_area",
                    )
                )

        # 2. Pass 2: Unlabelled identity pairs (e.g. "Vivek Dhedhi (92400120571)")
        for line_idx, line in enumerate(selected_lines):
            if line_idx in matched_line_indices:
                continue

            unlabelled_values = self.unlabelled_detector.detect_in_line(
                line=line,
                page=page,
                separator_y=separator_y,
            )
            for uv in unlabelled_values:
                conf = 0.65 if is_uncertain else 0.90
                field_id = f"{uv.field_type.value}_{page_number}_man_{len(detected_fields)}"
                detected_fields.append(
                    DetectedField(
                        field_id=field_id,
                        field_type=uv.field_type,
                        original_value=uv.value,
                        suggested_value=uv.value,
                        confidence=conf,
                        confidence_level=ConfidenceLevel.MEDIUM if is_uncertain else ConfidenceLevel.HIGH,
                        status=ReviewStatus.PENDING,
                        review_required=is_uncertain,
                        occurrences=[uv.occurrence],
                        detection_method="manual_area",
                    )
                )

        # 3. Pass 3: Single item isolated selection (when user highlighted ONLY name or ONLY enrollment)
        if not detected_fields and len(selected_lines) == 1:
            line = selected_lines[0]
            clean_text = line.text.strip().strip("()[]-|,.:")
            # Check if text is a valid student name
            is_valid_name, _ = self.unlabelled_detector.is_valid_student_name(clean_text, allow_single_token=False)
            if is_valid_name:
                field_id = f"student_name_{page_number}_man_single"
                occ = FieldOccurrence(
                    page_number=page_number,
                    raw_text=line.text,
                    bbox=line.bbox,
                    value_bbox=line.bbox,
                    label_bbox=None,
                    span_information=line.spans,
                    is_in_footer_region=True,
                )
                detected_fields.append(
                    DetectedField(
                        field_id=field_id,
                        field_type=FieldType.STUDENT_NAME,
                        original_value=clean_text,
                        suggested_value=clean_text,
                        confidence=0.88,
                        confidence_level=ConfidenceLevel.HIGH,
                        status=ReviewStatus.PENDING,
                        review_required=False,
                        occurrences=[occ],
                        detection_method="manual_text",
                    )
                )
            else:
                # Check if text is an enrollment number / roll number
                ft, _ = self.unlabelled_detector.classify_identifier(clean_text)
                if ft is not None:
                    field_id = f"{ft.value}_{page_number}_man_single"
                    occ = FieldOccurrence(
                        page_number=page_number,
                        raw_text=line.text,
                        bbox=line.bbox,
                        value_bbox=line.bbox,
                        label_bbox=None,
                        span_information=line.spans,
                        is_in_footer_region=True,
                    )
                    detected_fields.append(
                        DetectedField(
                            field_id=field_id,
                            field_type=ft,
                            original_value=clean_text,
                            suggested_value=clean_text,
                            confidence=0.88,
                            confidence_level=ConfidenceLevel.HIGH,
                            status=ReviewStatus.PENDING,
                            review_required=False,
                            occurrences=[occ],
                            detection_method="manual_text",
                        )
                    )

        return detected_fields
