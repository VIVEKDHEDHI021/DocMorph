"""Universal Layout Inference Service for DocMorph.

Receives intermediate document representations, applies layout-aware model predictions,
and reconstructs structured identity entities and footer regions with explainable evidence.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Optional
import joblib
import numpy as np

from ai_training.config import ID2LABEL, LABEL_LIST, MODEL_OUTPUT_DIR
from ai_training.train import LayoutFeatureExtractor
from app.schemas.detection_data import (
    BoundingBox,
    ConfidenceLevel,
    FieldOccurrence,
    FieldType,
)
from app.services.value_extractor import ExtractedFieldValue
from app.services.hybrid_pdf_pipeline import ExtractedToken, PageRepresentation


@dataclass
class LayoutPredictionEntity:
    """Represents a coherent entity extracted by the layout model."""

    entity_type: str  # "student_name", "enrollment_number", "roll_number", "student_id", "page_number", "footer_region"
    value: str
    bbox: tuple[float, float, float, float]
    normalized_bbox: tuple[int, int, int, int]
    page_number: int
    confidence: float
    token_indices: list[int] = field(default_factory=list)
    raw_text: str = ""


class UniversalLayoutInferenceService:
    """Inference engine performing layout-aware document understanding."""

    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_OUTPUT_DIR
        self.model_path = self.model_dir / "layout_classifier.joblib"
        self.feature_extractor = LayoutFeatureExtractor()
        self.model = None

        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
            except Exception:
                self.model = None

    def is_model_available(self) -> bool:
        """Checks if a trained model checkpoint is available on disk."""
        return self.model is not None

    def predict_page(
        self, page_rep: PageRepresentation
    ) -> list[LayoutPredictionEntity]:
        """Runs layout classification on all tokens of a document page and groups into entities."""
        if not page_rep.tokens:
            return []

        tokens = page_rep.tokens
        tokens_text = [t.text for t in tokens]
        bboxes = [list(t.normalized_bbox) for t in tokens]

        # Extract multi-modal layout features
        features = self.feature_extractor.extract_features(tokens_text, bboxes)

        predicted_labels: list[str] = []
        confidences: list[float] = []

        if self.model is not None:
            pred_ids = self.model.predict(features)
            proba = self.model.predict_proba(features)
            for idx, pid in enumerate(pred_ids):
                label_str = ID2LABEL.get(pid, "O")
                predicted_labels.append(label_str)
                conf = float(np.max(proba[idx]))
                confidences.append(conf)
        else:
            # High-accuracy heuristic layout fallback if model is not yet loaded
            predicted_labels, confidences = self._heuristic_layout_prediction(tokens, page_rep.height)

        # Assemble BIO tags into structured entities
        entities = self._assemble_bio_entities(tokens, predicted_labels, confidences, page_rep.page_number)
        return entities

    def _assemble_bio_entities(
        self,
        tokens: list[ExtractedToken],
        labels: list[str],
        confidences: list[float],
        page_number: int,
    ) -> list[LayoutPredictionEntity]:
        """Aggregates contiguous B- and I- tokens into distinct entities with accurate bounding boxes."""
        entities: list[LayoutPredictionEntity] = []

        curr_entity_type: Optional[str] = None
        curr_token_indices: list[int] = []
        curr_confidences: list[float] = []

        def flush_current():
            nonlocal curr_entity_type, curr_token_indices, curr_confidences
            if not curr_entity_type or not curr_token_indices:
                return

            sub_tokens = [tokens[i] for i in curr_token_indices]
            val = " ".join(t.text for t in sub_tokens).strip()

            # Clean punctuation from identity numbers
            clean_val = val
            if curr_entity_type in ("enrollment_number", "roll_number", "student_id", "page_number"):
                clean_val = re.sub(r"[\(\)\[\]\-|,;:]", "", val).strip()

            if clean_val:
                x0 = min(t.bbox[0] for t in sub_tokens)
                y0 = min(t.bbox[1] for t in sub_tokens)
                x1 = max(t.bbox[2] for t in sub_tokens)
                y1 = max(t.bbox[3] for t in sub_tokens)

                nx0 = min(t.normalized_bbox[0] for t in sub_tokens)
                ny0 = min(t.normalized_bbox[1] for t in sub_tokens)
                nx1 = max(t.normalized_bbox[2] for t in sub_tokens)
                ny1 = max(t.normalized_bbox[3] for t in sub_tokens)

                avg_conf = float(np.mean(curr_confidences)) if curr_confidences else 0.85

                entities.append(
                    LayoutPredictionEntity(
                        entity_type=curr_entity_type,
                        value=clean_val,
                        bbox=(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)),
                        normalized_bbox=(nx0, ny0, nx1, ny1),
                        page_number=page_number,
                        confidence=round(avg_conf, 3),
                        token_indices=list(curr_token_indices),
                        raw_text=val,
                    )
                )

            curr_entity_type = None
            curr_token_indices = []
            curr_confidences = []

        for idx, (tok, label, conf) in enumerate(zip(tokens, labels, confidences)):
            if label == "O":
                flush_current()
                continue

            tag_prefix = label[:2]
            entity_tag = label[2:].lower()

            if tag_prefix == "B-":
                flush_current()
                curr_entity_type = entity_tag
                curr_token_indices = [idx]
                curr_confidences = [conf]
            elif tag_prefix == "I-":
                if curr_entity_type == entity_tag:
                    curr_token_indices.append(idx)
                    curr_confidences.append(conf)
                else:
                    flush_current()
                    curr_entity_type = entity_tag
                    curr_token_indices = [idx]
                    curr_confidences = [conf]

        flush_current()
        return entities

    def _heuristic_layout_prediction(
        self, tokens: list[ExtractedToken], page_height: float
    ) -> tuple[list[str], list[float]]:
        """Zero-dependency heuristic layout classifier when weights are not present."""
        labels = []
        confidences = []

        for t in tokens:
            y1 = t.bbox[3]
            is_footer = (y1 >= page_height * 0.75)
            clean = t.text.strip("()[]-|,.:")

            if is_footer:
                if clean.isdigit() and len(clean) in (1, 2, 3) and t.bbox[0] >= 400:
                    labels.append("B-PAGE_NUMBER")
                    confidences.append(0.92)
                elif clean.isdigit() and 8 <= len(clean) <= 15:
                    labels.append("B-ENROLLMENT_ID")
                    confidences.append(0.90)
                elif clean.isalpha() and len(clean) >= 2 and clean.istitle():
                    labels.append("B-STUDENT_NAME")
                    confidences.append(0.85)
                else:
                    labels.append("B-FOOTER")
                    confidences.append(0.80)
            else:
                labels.append("O")
                confidences.append(0.95)

        return labels, confidences
