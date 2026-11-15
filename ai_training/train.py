"""Model Training Pipeline for Layout-Aware Universal Footer Detection.

Trains a layout-aware sequence token classifier combining spatial bounding box geometry,
text semantics, typographical features, and document structural context into the 13-class BIO schema.
Supports CPU and GPU environments with checkpoint saving and reproducible metric logging.
"""

import json
from pathlib import Path
import random
import time
from typing import Any, Optional
import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import classification_report, f1_score

from ai_training.config import (
    CHECKPOINT_DIR,
    LABEL_LIST,
    LABEL2ID,
    MODEL_OUTPUT_DIR,
    RANDOM_SEED,
    TRAINING_CONFIG,
)
from ai_training.dataset import DatasetManager, PageAnnotation


class LayoutFeatureExtractor:
    """Extracts rich multi-modal spatial, typographic, and semantic features for each token."""

    @staticmethod
    def extract_features(
        tokens: list[str],
        bboxes: list[list[int]],
        page_width: float = 1000.0,
        page_height: float = 1000.0,
    ) -> np.ndarray:
        """Extracts dense feature vectors for a sequence of tokens on a page."""
        features = []
        n_tokens = len(tokens)

        for i in range(n_tokens):
            w = tokens[i]
            bbox = bboxes[i]
            x0, y0, x1, y1 = bbox
            w_w = max(1, x1 - x0)
            w_h = max(1, y1 - y0)

            # 1. Spatial & Positional features (Normalized 0..1000 scale)
            norm_x0 = x0 / 1000.0
            norm_y0 = y0 / 1000.0
            norm_x1 = x1 / 1000.0
            norm_y1 = y1 / 1000.0
            mid_x = (x0 + x1) / 2000.0
            mid_y = (y0 + y1) / 2000.0
            dist_bottom = max(0.0, 1.0 - norm_y1)
            dist_left = norm_x0
            dist_right = max(0.0, 1.0 - norm_x1)
            aspect_ratio = min(10.0, w_w / max(1.0, w_h))

            # Binary spatial zone indicators
            is_bottom_zone = 1.0 if y0 >= 850 else 0.0
            is_deep_footer = 1.0 if y0 >= 900 else 0.0
            is_header_zone = 1.0 if y1 <= 150 else 0.0
            is_left_aligned = 1.0 if x0 <= 150 else 0.0
            is_right_aligned = 1.0 if x1 >= 850 else 0.0
            is_centered = 1.0 if abs(mid_x - 0.5) <= 0.15 else 0.0

            # 2. Text Lexical & Syntactic features
            text_len = min(30, len(w))
            clean_w = w.strip("()[]-|,.:")
            digits_count = sum(1 for c in clean_w if c.isdigit())
            alpha_count = sum(1 for c in clean_w if c.isalpha())
            digit_ratio = digits_count / max(1, text_len)
            alpha_ratio = alpha_count / max(1, text_len)

            is_pure_digits = 1.0 if clean_w.isdigit() else 0.0
            is_pure_alpha = 1.0 if clean_w.isalpha() else 0.0
            is_title_case = 1.0 if w.istitle() else 0.0
            is_upper_case = 1.0 if w.isupper() else 0.0
            has_parens = 1.0 if ("(" in w or ")" in w or "[" in w or "]" in w) else 0.0
            has_dash = 1.0 if ("-" in w or "–" in w or "|" in w) else 0.0

            # Length characteristics for typical academic numbers
            is_enrollment_len = 1.0 if (clean_w.isdigit() and 9 <= len(clean_w) <= 15) else 0.0
            is_roll_len = 1.0 if (clean_w.isdigit() and 1 <= len(clean_w) <= 3) else 0.0
            is_page_num_candidate = 1.0 if (clean_w.isdigit() and int(clean_w) <= 100 and (x1 >= 800 or is_centered)) else 0.0

            # 3. Contextual neighbor features (previous & next tokens)
            prev_y_diff = 0.0
            prev_x_diff = 0.0
            if i > 0:
                prev_b = bboxes[i - 1]
                prev_y_diff = abs(y0 - prev_b[1]) / 1000.0
                prev_x_diff = (x0 - prev_b[2]) / 1000.0

            next_y_diff = 0.0
            next_x_diff = 0.0
            if i < n_tokens - 1:
                next_b = bboxes[i + 1]
                next_y_diff = abs(y0 - next_b[1]) / 1000.0
                next_x_diff = (next_b[0] - x1) / 1000.0

            # Keyword contextual cues
            w_lower = clean_w.lower()
            is_name_kw = 1.0 if w_lower in ("name", "student", "candidate") else 0.0
            is_enr_kw = 1.0 if w_lower in ("enrollment", "enrolment", "enr", "reg", "registration") else 0.0
            is_roll_kw = 1.0 if w_lower in ("roll", "rollno") else 0.0
            is_page_kw = 1.0 if w_lower in ("page", "of") else 0.0

            vec = [
                norm_x0, norm_y0, norm_x1, norm_y1,
                mid_x, mid_y, dist_bottom, dist_left, dist_right,
                aspect_ratio, is_bottom_zone, is_deep_footer, is_header_zone,
                is_left_aligned, is_right_aligned, is_centered,
                text_len / 30.0, digit_ratio, alpha_ratio,
                is_pure_digits, is_pure_alpha, is_title_case, is_upper_case,
                has_parens, has_dash,
                is_enrollment_len, is_roll_len, is_page_num_candidate,
                prev_y_diff, prev_x_diff, next_y_diff, next_x_diff,
                is_name_kw, is_enr_kw, is_roll_kw, is_page_kw,
            ]
            features.append(vec)

        return np.array(features, dtype=np.float32)


class ModelTrainer:
    """Trains and validates the universal layout document understanding model."""

    def __init__(self, output_dir: Optional[Path] = None, seed: int = RANDOM_SEED):
        self.output_dir = output_dir or MODEL_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir = CHECKPOINT_DIR
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.feature_extractor = LayoutFeatureExtractor()

        # Set deterministic seeds
        random.seed(seed)
        np.random.seed(seed)

    def prepare_data(
        self, annotations: list[PageAnnotation]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extracts tabular layout feature matrices and ground truth label vectors."""
        all_features = []
        all_labels = []

        for annot in annotations:
            feats = self.feature_extractor.extract_features(annot.tokens, annot.bboxes)
            label_ids = [LABEL2ID[lb] for lb in annot.labels]

            all_features.append(feats)
            all_labels.extend(label_ids)

        X = np.vstack(all_features)
        y = np.array(all_labels, dtype=np.int64)
        return X, y

    def train(
        self,
        train_pages: list[PageAnnotation],
        val_pages: list[PageAnnotation],
        max_iter: int = 150,
    ) -> dict[str, Any]:
        """Trains the layout-aware classifier and evaluates on validation data."""
        start_time = time.perf_counter()

        print(f"Preparing training data from {len(train_pages)} pages...")
        X_train, y_train = self.prepare_data(train_pages)
        print(f"Training tokens: {X_train.shape[0]}, Feature dimension: {X_train.shape[1]}")

        print(f"Preparing validation data from {len(val_pages)} pages...")
        X_val, y_val = self.prepare_data(val_pages)
        print(f"Validation tokens: {X_val.shape[0]}")

        # Train high-performance gradient boosting classifier with L2 regularization
        clf = HistGradientBoostingClassifier(
            max_iter=max_iter,
            learning_rate=0.08,
            max_leaf_nodes=31,
            min_samples_leaf=15,
            l2_regularization=0.1,
            random_state=self.seed,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10,
        )

        print("Fitting layout classifier...")
        clf.fit(X_train, y_train)

        # Validation predictions
        y_val_pred = clf.predict(X_val)
        macro_f1 = f1_score(y_val, y_val_pred, average="macro", zero_division=0)
        weighted_f1 = f1_score(y_val, y_val_pred, average="weighted", zero_division=0)

        elapsed = time.perf_counter() - start_time
        print(f"Training completed in {elapsed:.2f}s | Val Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")

        # Save model checkpoint and metadata
        model_path = self.output_dir / "layout_classifier.joblib"
        meta_path = self.output_dir / "model_metadata.json"

        joblib.dump(clf, model_path)

        metadata = {
            "model_type": "LayoutAwareGradientBoosting",
            "seed": self.seed,
            "trained_tokens": int(X_train.shape[0]),
            "feature_dim": int(X_train.shape[1]),
            "training_duration_seconds": round(elapsed, 2),
            "val_macro_f1": round(float(macro_f1), 4),
            "val_weighted_f1": round(float(weighted_f1), 4),
            "labels": LABEL_LIST,
            "training_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # Also save checkpoint
        joblib.dump(clf, self.checkpoint_dir / f"checkpoint_f1_{macro_f1:.4f}.joblib")

        return metadata

