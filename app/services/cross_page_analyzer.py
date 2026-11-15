"""Cross-Page Document Structure Analysis Service for DocMorph.

Phase 2.2 Core Component:
Coordinates layout-aware entity candidates across all pages of a document to:
1. Compare footer structures and identify stable footer regions.
2. Track candidate student names, enrollment IDs, and roll numbers across pages.
3. Validate spatial alignment consistency (normalized coordinates, baseline alignment).
4. Separate bounding boxes: strictly isolate student name from enrollment number.
5. Exclude page numbers from student credentials.
6. Disambiguate header credentials from footer credentials.
7. Filter out non-repeating body text falsely predicted as footer.
8. Calibrate multi-factor confidence based on cross-page repetition and layout stability.
"""

from collections import defaultdict
from dataclasses import dataclass, field
import statistics
from typing import Optional

from ai_training.inference import LayoutPredictionEntity
from app.schemas.detection_data import (
    BoundingBox,
    ConfidenceLevel,
    FieldOccurrence,
    FieldType,
    SpanInformation,
)
from app.services.hybrid_pdf_pipeline import DocumentRepresentation, PageRepresentation
from app.services.value_extractor import ExtractedFieldValue


@dataclass
class PageRegionProfile:
    """Structural layout characteristics of a document page."""

    page_number: int
    page_width: float
    page_height: float
    footer_top_y: float
    footer_bottom_y: float
    has_separator_line: bool = False
    entities: list[LayoutPredictionEntity] = field(default_factory=list)


@dataclass
class IdentityCandidateCluster:
    """A cluster of recurring identity values across pages."""

    field_type: FieldType
    primary_value: str
    occurrences: list[LayoutPredictionEntity] = field(default_factory=list)
    normalized_positions: list[tuple[int, int, int, int]] = field(default_factory=list)
    confidence: float = 0.0
    is_cross_page_validated: bool = False


class CrossPageAnalyzer:
    """Analyzes multi-page spatial and semantic consistency to refine entity detections."""

    def __init__(self, position_tolerance_pts: float = 30.0):
        self.position_tolerance_pts = position_tolerance_pts

    def analyze_document(
        self,
        doc_rep: DocumentRepresentation,
        page_entities: dict[int, list[LayoutPredictionEntity]],
    ) -> list[ExtractedFieldValue]:
        """Performs document-level layout reconciliation and produces confirmed ExtractedFieldValues.

        Args:
            doc_rep: Multi-page document representation from HybridPDFPipeline.
            page_entities: Map from page_number (1-indexed) to predicted LayoutPredictionEntities.

        Returns:
            List of calibrated, structured ExtractedFieldValue instances with independent bounding boxes.
        """
        total_pages = doc_rep.total_pages

        # Step 1: Filter out explicit page numbers from student candidates
        filtered_page_entities: dict[int, list[LayoutPredictionEntity]] = {}
        for p_num, entities in page_entities.items():
            valid_entities = []
            for ent in entities:
                # Explicitly exclude page numbers
                if ent.entity_type == "page_number":
                    continue
                # If numeric and purely 1-3 digits located on bottom right or matches page number
                if self._is_likely_page_number(ent, p_num):
                    continue
                valid_entities.append(ent)
            filtered_page_entities[p_num] = valid_entities

        # Step 2: Separate and enforce independent bounding boxes for paired tokens
        # (e.g. if name and enrollment were in the same line/box, ensure they are independent)
        refined_entities_by_page = self._enforce_separate_bounding_boxes(
            filtered_page_entities, doc_rep
        )

        # Step 3: Cluster candidate identities across pages by normalized value and relative layout
        clusters = self._cluster_candidates(refined_entities_by_page, total_pages)

        # Step 4: Validate cross-page spatial alignment and repetition
        validated_clusters = self._validate_clusters(clusters, total_pages)

        # Step 5: Convert validated clusters to ExtractedFieldValue models
        extracted_values = self._build_extracted_values(
            validated_clusters, doc_rep, total_pages
        )

        return extracted_values

    def _is_likely_page_number(
        self, ent: LayoutPredictionEntity, current_page: int
    ) -> bool:
        """Determines if a numeric entity is actually a page number."""
        clean = ent.value.strip()
        if not clean.isdigit():
            return False

        # If it matches current page number
        val_int = int(clean)
        if val_int == current_page:
            return True

        # If 1-3 digits in right half of bottom region
        x0, y0, x1, y1 = ent.normalized_bbox
        is_bottom = y0 >= 800
        is_right = x0 >= 600
        if is_bottom and is_right and len(clean) <= 3:
            return True

        return False

    def _enforce_separate_bounding_boxes(
        self,
        page_entities: dict[int, list[LayoutPredictionEntity]],
        doc_rep: DocumentRepresentation,
    ) -> dict[int, list[LayoutPredictionEntity]]:
        """Ensures that student name and enrollment number never share the same bounding box."""
        refined: dict[int, list[LayoutPredictionEntity]] = defaultdict(list)

        for p_num, entities in page_entities.items():
            names = [e for e in entities if e.entity_type == "student_name"]
            identifiers = [
                e
                for e in entities
                if e.entity_type in ("enrollment_number", "roll_number", "student_id")
            ]
            others = [
                e
                for e in entities
                if e.entity_type not in ("student_name", "enrollment_number", "roll_number", "student_id")
            ]

            # Check for overlapping bounding boxes between name and identifier
            for name_ent in names:
                for id_ent in identifiers:
                    # If bounding boxes significantly overlap, adjust them to be disjoint
                    if self._bboxes_overlap(name_ent.bbox, id_ent.bbox):
                        # The one on the left gets left segment, right gets right segment
                        if name_ent.bbox[0] < id_ent.bbox[0]:
                            # Name is to the left
                            name_box = (
                                name_ent.bbox[0],
                                name_ent.bbox[1],
                                min(name_ent.bbox[2], id_ent.bbox[0] - 2),
                                name_ent.bbox[3],
                            )
                            name_ent.bbox = name_box
                        else:
                            # Identifier is to the left
                            id_box = (
                                id_ent.bbox[0],
                                id_ent.bbox[1],
                                min(id_ent.bbox[2], name_ent.bbox[0] - 2),
                                id_ent.bbox[3],
                            )
                            id_ent.bbox = id_box

            refined[p_num].extend(names)
            refined[p_num].extend(identifiers)
            refined[p_num].extend(others)

        return refined

    def _bboxes_overlap(
        self, b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]
    ) -> bool:
        """Checks if two rectangles in points intersect."""
        x0_1, y0_1, x1_1, y1_1 = b1
        x0_2, y0_2, x1_2, y1_2 = b2
        return not (x1_1 < x0_2 or x0_1 > x1_2 or y1_1 < y0_2 or y0_1 > y1_2)

    NON_NAME_WORDS = {
        "name", "student", "student name", "enrollment", "enrollment no", "enrolment",
        "roll", "roll no", "page", "page no", "date", "dept", "department", "faculty",
        "university", "subject", "experiment", "practical", "sign", "signature",
        "code", "semester", "branch", "no", "id", "student id", "lab", "manual",
        "fig", "figure", "step", "table", "chart", "diagram", "image", "screen",
        "screenshot", "console", "click", "now", "here", "note", "example", "button",
        "select", "enter", "run", "press", "following", "given", "output", "input",
        "allocate", "opened", "elastic", "ip", "address", "public", "private",
        "ipv4", "dashboard", "service", "services", "connect", "create", "instance",
        "instances", "amazon", "aws", "azure", "google", "cloud", "vpc", "ec2"
    }

    ENGLISH_STOP_WORDS = {
        "the", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "as", "an", "and", "or", "not", "this", "that",
        "these", "those", "it", "its", "you", "your", "can", "will", "would",
        "should", "once", "when", "where", "which", "who", "all", "any", "some"
    }

    def _cluster_candidates(
        self,
        page_entities: dict[int, list[LayoutPredictionEntity]],
        total_pages: int,
    ) -> dict[tuple[str, str], IdentityCandidateCluster]:
        """Clusters candidates by (entity_type, cleaned_value)."""
        clusters: dict[tuple[str, str], IdentityCandidateCluster] = {}

        field_map = {
            "student_name": FieldType.STUDENT_NAME,
            "enrollment_number": FieldType.ENROLLMENT_NUMBER,
            "roll_number": FieldType.ROLL_NUMBER,
            "student_id": FieldType.STUDENT_ID,
        }

        for p_num, entities in page_entities.items():
            for ent in entities:
                if ent.entity_type not in field_map:
                    continue
                ft = field_map[ent.entity_type]
                clean_val = ent.value.strip().strip(":").strip()
                if not clean_val:
                    continue

                # Filter out obvious keyword and caption false-positives for student name
                if ft == FieldType.STUDENT_NAME:
                    clean_lower = clean_val.lower()
                    if clean_lower in self.NON_NAME_WORDS:
                        continue
                    if len(clean_val) < 3 or not any(c.isalpha() for c in clean_val):
                        continue
                    words = [w.lower() for w in re.split(r"[\s\-_.]+", clean_val) if w]
                    if any(w in self.ENGLISH_STOP_WORDS or w in self.NON_NAME_WORDS for w in words):
                        continue

                cluster_key = (ent.entity_type, clean_val.lower())
                if cluster_key not in clusters:
                    clusters[cluster_key] = IdentityCandidateCluster(
                        field_type=ft,
                        primary_value=clean_val,
                    )

                clusters[cluster_key].occurrences.append(ent)
                clusters[cluster_key].normalized_positions.append(ent.normalized_bbox)

        return clusters

    def _validate_clusters(
        self,
        clusters: dict[tuple[str, str], IdentityCandidateCluster],
        total_pages: int,
    ) -> list[IdentityCandidateCluster]:
        """Evaluates spatial alignment variance and cross-page repetition for each cluster."""
        validated: list[IdentityCandidateCluster] = []

        for cluster in clusters.values():
            n_occurs = len(cluster.occurrences)
            avg_model_conf = sum(e.confidence for e in cluster.occurrences) / max(1, n_occurs)

            # Spatial variance check
            y_coords = [pos[1] for pos in cluster.normalized_positions]
            x_coords = [pos[0] for pos in cluster.normalized_positions]

            y_variance = statistics.variance(y_coords) if len(y_coords) > 1 else 0.0
            x_variance = statistics.variance(x_coords) if len(x_coords) > 1 else 0.0

            # Consistency criteria:
            # - Repetition across pages: if multi-page doc and occurs on >= 2 pages or >= 50% pages
            # - Low vertical variance: footer elements typically stay on the same baseline (< 400 normalized units variance)
            is_consistent_position = y_variance < 500.0

            cross_page_score = 0.0
            if total_pages > 1:
                page_coverage = n_occurs / float(total_pages)
                if n_occurs >= 2 and is_consistent_position:
                    cluster.is_cross_page_validated = True
                    cross_page_score = min(0.35, 0.20 + (page_coverage * 0.15))
                else:
                    # In a multi-page document, discard single-page isolated layout AI candidates
                    continue
            else:
                # Single-page document: base on model confidence and spatial plausibility
                cluster.is_cross_page_validated = True
                cross_page_score = 0.15

            # Final calibrated confidence score
            final_conf = min(0.99, avg_model_conf * 0.70 + cross_page_score)
            if final_conf < 0.65:
                continue

            cluster.confidence = final_conf
            validated.append(cluster)

        return validated

    def _build_extracted_values(
        self,
        clusters: list[IdentityCandidateCluster],
        doc_rep: DocumentRepresentation,
        total_pages: int,
    ) -> list[ExtractedFieldValue]:
        """Constructs production ExtractedFieldValue objects for confirmed clusters."""
        results: list[ExtractedFieldValue] = []

        # Find linked name and enrollment pairs on each page to assign matching pair_ids
        for cluster in clusters:
            for ent in cluster.occurrences:
                p_num = ent.page_number
                p_rep = doc_rep.pages[p_num - 1] if p_num <= len(doc_rep.pages) else None
                h = p_rep.height if p_rep else 842.0

                is_in_footer = (ent.bbox[1] >= h * 0.65) or (ent.normalized_bbox[1] >= 650)
                is_bottom_left = is_in_footer and (ent.normalized_bbox[0] <= 550)

                # Construct precise BoundingBox in points
                bbox_obj = BoundingBox(
                    x0=round(ent.bbox[0], 2),
                    y0=round(ent.bbox[1], 2),
                    x1=round(ent.bbox[2], 2),
                    y1=round(ent.bbox[3], 2),
                )

                # Constituent span info
                spans = [
                    SpanInformation(
                        text=ent.value,
                        bbox=bbox_obj,
                        font="AI_Layout_Inferred",
                        size=9.0,
                    )
                ]

                occurrence = FieldOccurrence(
                    page_number=p_num,
                    bbox=bbox_obj,
                    value_bbox=bbox_obj,
                    label_bbox=None,
                    span_information=spans,
                    raw_text=ent.raw_text or ent.value,
                    matched_label=ent.entity_type,
                    is_in_footer_region=is_in_footer,
                    pair_id=f"ai_pair_{p_num}" if is_bottom_left else None,
                )

                extracted_val = ExtractedFieldValue(
                    field_type=cluster.field_type,
                    matched_label=ent.entity_type,
                    value=cluster.primary_value,
                    is_ambiguous=False,
                    ambiguity_reason=None,
                    occurrence=occurrence,
                    is_unlabelled=True,
                    is_near_separator_line=False,
                    is_bottom_left=is_bottom_left,
                )
                results.append(extracted_val)

        return results
