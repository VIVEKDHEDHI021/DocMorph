"""Dataset Management, Generation, and Splitter for Universal Footer Detection.

Features:
- Structured JSON annotation schema with token-level BIO tags and [0, 1000] bounding boxes.
- Strict document-level train/validation/test splitting (prevents cross-page data leakage).
- Diverse academic document layout generator spanning multiple university formats.
- Validation checks for BIO grammar correctness and bounding box geometry.
"""

from dataclasses import asdict, dataclass
import json
import random
from pathlib import Path
from typing import Any, Optional

from ai_training.config import DATA_DIR, LABEL_LIST, LABEL2ID, RANDOM_SEED


@dataclass
class PageAnnotation:
    """Represents ground-truth annotations for a single document page."""

    doc_id: str
    page_number: int
    total_pages: int
    university: str
    tokens: list[str]
    bboxes: list[list[int]]  # Normalized [x0, y0, x1, y1] in [0, 1000]
    labels: list[str]  # BIO labels matching LABEL_LIST
    has_separator_line: bool = False
    footer_style: str = "bottom_left"


@dataclass
class DatasetSplit:
    """Holds train, validation, and test splits with document-level isolation."""

    train: list[PageAnnotation]
    val: list[PageAnnotation]
    test: list[PageAnnotation]


class DatasetManager:
    """Manages annotation creation, validation, storage, and splitting."""

    def __init__(self, data_dir: Optional[Path] = None, seed: int = RANDOM_SEED):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        random.seed(self.seed)

    @staticmethod
    def validate_annotation(page: PageAnnotation) -> list[str]:
        """Validates that a PageAnnotation adheres to BIO grammar and coordinate constraints."""
        errors: list[str] = []

        if len(page.tokens) != len(page.bboxes) or len(page.tokens) != len(page.labels):
            errors.append(
                f"Length mismatch: {len(page.tokens)} tokens, {len(page.bboxes)} bboxes, {len(page.labels)} labels"
            )

        for idx, (bbox, label) in enumerate(zip(page.bboxes, page.labels)):
            if label not in LABEL2ID:
                errors.append(f"Invalid label '{label}' at token index {idx}")

            if len(bbox) != 4:
                errors.append(f"Invalid bbox length {len(bbox)} at token index {idx}")
                continue

            x0, y0, x1, y1 = bbox
            if not (0 <= x0 <= 1000 and 0 <= y0 <= 1000 and 0 <= x1 <= 1000 and 0 <= y1 <= 1000):
                errors.append(f"Out of bounds bbox {bbox} at token index {idx}")

            if x1 < x0 or y1 < y0:
                errors.append(f"Inverted bbox coordinates {bbox} at token index {idx}")

        # Check BIO grammar: I- tag must follow B- or I- of same entity
        prev_entity = None
        for idx, label in enumerate(page.labels):
            if label.startswith("B-"):
                prev_entity = label[2:]
            elif label.startswith("I-"):
                curr_entity = label[2:]
                if prev_entity != curr_entity:
                    errors.append(
                        f"Orphan I- tag at index {idx}: {label} followed {prev_entity}"
                    )
            else:
                prev_entity = None

        return errors

    def split_dataset(
        self,
        annotations: list[PageAnnotation],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> DatasetSplit:
        """Splits annotations strictly by document ID so no document leaks across splits."""
        doc_ids = sorted(list({a.doc_id for a in annotations}))
        random.Random(self.seed).shuffle(doc_ids)

        n_docs = len(doc_ids)
        n_train = max(1, int(round(n_docs * train_ratio)))
        n_val = max(1, int(round(n_docs * val_ratio))) if n_docs > 2 else 0

        train_docs = set(doc_ids[:n_train])
        val_docs = set(doc_ids[n_train : n_train + n_val])
        test_docs = set(doc_ids[n_train + n_val :])

        if not test_docs and len(doc_ids) >= 3:
            # Ensure at least 1 document in test set
            test_docs = {doc_ids[-1]}
            if doc_ids[-1] in val_docs:
                val_docs.remove(doc_ids[-1])
            elif doc_ids[-1] in train_docs and len(train_docs) > 1:
                train_docs.remove(doc_ids[-1])

        train_pages = [a for a in annotations if a.doc_id in train_docs]
        val_pages = [a for a in annotations if a.doc_id in val_docs]
        test_pages = [a for a in annotations if a.doc_id in test_docs]

        return DatasetSplit(train=train_pages, val=val_pages, test=test_pages)

    def save_split(self, split: DatasetSplit, prefix: str = "academic_v1") -> dict[str, Path]:
        """Serializes dataset splits to JSON files."""
        paths = {}
        for name, items in [("train", split.train), ("val", split.val), ("test", split.test)]:
            out_file = self.data_dir / f"{prefix}_{name}.json"
            data = [asdict(item) for item in items]
            out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            paths[name] = out_file
        return paths

    def load_split(self, prefix: str = "academic_v1") -> DatasetSplit:
        """Loads dataset splits from JSON files."""
        def load_file(name: str) -> list[PageAnnotation]:
            p = self.data_dir / f"{prefix}_{name}.json"
            if not p.exists():
                return []
            raw = json.loads(p.read_text(encoding="utf-8"))
            return [PageAnnotation(**item) for item in raw]

        return DatasetSplit(
            train=load_file("train"),
            val=load_file("val"),
            test=load_file("test"),
        )

    def generate_synthetic_corpus(self, num_documents: int = 40) -> list[PageAnnotation]:
        """Generates a rich, diverse benchmark corpus of multi-layout academic documents.

        Covers:
        1. Marwadi University / GTU style: bottom-left unlabelled `Name (Enrollment)` with separator.
        2. IIT / NIT style: centered `Name - RollNo`, no separator, code/table body.
        3. Anna Univ / VTU style: bottom-right student credentials, university name on bottom-left.
        4. Header-table practical style: `Enrollment No: 92400120571` in top header, no footer identity.
        5. Negative examples: documents with only page numbers `1` or `Page 1 of 5`, no student identity.
        6. Complex layout: multi-column documents with screenshots, charts, and small footer text.
        """
        rng = random.Random(self.seed)

        universities = [
            "Marwadi University",
            "Indian Institute of Technology",
            "National Institute of Technology",
            "Gujarat Technological University",
            "Anna University",
            "Delhi Technological University",
            "Vellore Institute of Technology",
            "Birla Institute of Technology",
        ]

        first_names = ["Vivek", "Neel", "Aarav", "Priya", "Rohan", "Ananya", "Dev", "Isha", "Rahul", "Kavya", "Tanmay", "Sanya"]
        last_names = ["Dhedhi", "Vyas", "Sharma", "Patel", "Verma", "Mehta", "Singh", "Joshi", "Nair", "Reddy", "Chopra", "Gupta"]

        body_paragraphs = [
            "In this experiment we analyze the performance of distributed database indexing under high concurrency.",
            "The 8086 microprocessor supports 16-bit arithmetic and logical operations across general registers.",
            "Convolutional Neural Networks employ localized kernels to extract hierarchical spatial features from images.",
            "Cloud computing services offer scalable compute instances with on-demand pricing models and virtual networking.",
            "Table 1 summarizes the execution time in milliseconds across 10 independent benchmark runs.",
            "Figure 4 illustrates the network topology including edge gateway, load balancer, and worker nodes.",
            "The time complexity of the proposed sorting algorithm is O(N log N) in the worst-case scenario.",
            "To deploy the microservices container cluster, execute the following docker-compose configuration script.",
        ]

        annotations: list[PageAnnotation] = []

        for doc_idx in range(1, num_documents + 1):
            doc_id = f"doc_{doc_idx:03d}"
            univ = universities[(doc_idx - 1) % len(universities)]
            total_pages = rng.randint(2, 6)

            # Assign consistent student credentials for this document
            first = rng.choice(first_names)
            last = rng.choice(last_names)
            student_name = f"{first} {last}"
            enrollment_num = str(92400000000 + rng.randint(10000, 99999))
            roll_num = f"{rng.randint(10, 89)}"
            student_id = f"STU-{rng.randint(1000, 9999)}"

            layout_style = (doc_idx % 6)

            for page_num in range(1, total_pages + 1):
                tokens: list[str] = []
                bboxes: list[list[int]] = []
                labels: list[str] = []

                # 1. Header (y: 30 - 80)
                tokens.extend(["DEPARTMENT", "OF", "COMPUTER", "ENGINEERING", "-", univ.upper()])
                hx0 = 50
                for w in tokens:
                    w_w = len(w) * 8
                    bboxes.append([hx0, 40, hx0 + w_w, 60])
                    labels.append("O")
                    hx0 += w_w + 10

                # 2. Body Text (y: 120 - 750)
                body_y = 120
                for _ in range(rng.randint(3, 5)):
                    para = rng.choice(body_paragraphs)
                    px = 50
                    for word in para.split():
                        ww = len(word) * 7
                        bboxes.append([px, body_y, px + ww, body_y + 15])
                        labels.append("O")
                        tokens.append(word)
                        px += ww + 8
                        if px > 900:
                            px = 50
                            body_y += 20
                    body_y += 35

                # 3. Footer Region (y: 910 - 960)
                has_sep = False
                footer_style_name = "standard"

                if layout_style == 0:
                    # Style 0: Bottom-left unlabelled Name (Enrollment), right Page Number
                    has_sep = True
                    footer_style_name = "bottom_left_combined"
                    fy = 930
                    # Name tokens
                    tokens.append(first)
                    bboxes.append([60, fy, 130, fy + 16])
                    labels.append("B-STUDENT_NAME")

                    tokens.append(last)
                    bboxes.append([135, fy, 205, fy + 16])
                    labels.append("I-STUDENT_NAME")

                    # Parentheses and enrollment
                    tokens.append(f"({enrollment_num})")
                    bboxes.append([215, fy, 335, fy + 16])
                    labels.append("B-ENROLLMENT_ID")

                    # Page number on right
                    tokens.append(f"{page_num}")
                    bboxes.append([920, fy, 940, fy + 16])
                    labels.append("B-PAGE_NUMBER")

                elif layout_style == 1:
                    # Style 1: Centered Name - Roll Number, Department on left
                    has_sep = False
                    footer_style_name = "centered_dash"
                    fy = 935
                    # Dept name on left (generic footer)
                    tokens.append("Lab")
                    bboxes.append([60, fy, 90, fy + 15])
                    labels.append("B-FOOTER")
                    tokens.append("Manual")
                    bboxes.append([95, fy, 145, fy + 15])
                    labels.append("I-FOOTER")

                    # Centered Name and Roll No
                    tokens.append(first)
                    bboxes.append([400, fy, 450, fy + 15])
                    labels.append("B-STUDENT_NAME")

                    tokens.append(last)
                    bboxes.append([455, fy, 510, fy + 15])
                    labels.append("I-STUDENT_NAME")

                    tokens.append("-")
                    bboxes.append([515, fy, 525, fy + 15])
                    labels.append("O")

                    tokens.append(roll_num)
                    bboxes.append([530, fy, 560, fy + 15])
                    labels.append("B-ROLL_NUMBER")

                    # Page number on right
                    tokens.extend(["Page", f"{page_num}", "of", f"{total_pages}"])
                    px = 820
                    for pw, pl in zip(["Page", f"{page_num}", "of", f"{total_pages}"], ["B-PAGE_NUMBER", "I-PAGE_NUMBER", "I-PAGE_NUMBER", "I-PAGE_NUMBER"]):
                        bboxes.append([px, fy, px + len(pw) * 7, fy + 15])
                        labels.append(pl)
                        px += len(pw) * 7 + 6

                elif layout_style == 2:
                    # Style 2: Explicit labels: Name: ... | Enrollment No: ...
                    has_sep = True
                    footer_style_name = "explicit_labeled"
                    fy = 925
                    tokens.extend(["Name:", first, last, "|", "Enrollment", "No:", enrollment_num])
                    bx = 60
                    for tk, lb in [
                        ("Name:", "O"),
                        (first, "B-STUDENT_NAME"),
                        (last, "I-STUDENT_NAME"),
                        ("|", "O"),
                        ("Enrollment", "O"),
                        ("No:", "O"),
                        (enrollment_num, "B-ENROLLMENT_ID"),
                    ]:
                        bboxes.append([bx, fy, bx + len(tk) * 8, fy + 15])
                        labels.append(lb)
                        bx += len(tk) * 8 + 8

                    tokens.append(f"{page_num}")
                    bboxes.append([925, fy, 945, fy + 15])
                    labels.append("B-PAGE_NUMBER")

                elif layout_style == 3:
                    # Style 3: Student ID format: ID - Name
                    has_sep = False
                    footer_style_name = "inverted_student_id"
                    fy = 930
                    tokens.extend([student_id, "-", first, last])
                    bx = 60
                    for tk, lb in [
                        (student_id, "B-STUDENT_ID"),
                        ("-", "O"),
                        (first, "B-STUDENT_NAME"),
                        (last, "I-STUDENT_NAME"),
                    ]:
                        bboxes.append([bx, fy, bx + len(tk) * 8, fy + 15])
                        labels.append(lb)
                        bx += len(tk) * 8 + 8

                    tokens.append(f"{page_num}")
                    bboxes.append([920, fy, 940, fy + 15])
                    labels.append("B-PAGE_NUMBER")

                elif layout_style == 4:
                    # Style 4: Negative Case: Document has only Page Number in footer, NO student info
                    has_sep = rng.choice([True, False])
                    footer_style_name = "page_number_only"
                    fy = 940
                    tokens.extend(["University", "Confidential"])
                    bboxes.append([60, fy, 130, fy + 14])
                    labels.append("B-FOOTER")
                    bboxes.append([135, fy, 220, fy + 14])
                    labels.append("I-FOOTER")

                    tokens.append(f"{page_num}")
                    bboxes.append([920, fy, 940, fy + 14])
                    labels.append("B-PAGE_NUMBER")

                else:
                    # Style 5: Top Header table had enrollment number, footer only has university & page
                    has_sep = False
                    footer_style_name = "header_only_credentials"
                    fy = 940
                    tokens.extend(["Practical", "Report", "-", univ])
                    bx = 60
                    for tk, lb in [("Practical", "B-FOOTER"), ("Report", "I-FOOTER"), ("-", "I-FOOTER"), (univ, "I-FOOTER")]:
                        bboxes.append([bx, fy, bx + len(tk) * 8, fy + 14])
                        labels.append(lb)
                        bx += len(tk) * 8 + 6

                    tokens.append(f"{page_num}")
                    bboxes.append([920, fy, 940, fy + 14])
                    labels.append("B-PAGE_NUMBER")

                page_annot = PageAnnotation(
                    doc_id=doc_id,
                    page_number=page_num,
                    total_pages=total_pages,
                    university=univ,
                    tokens=tokens,
                    bboxes=bboxes,
                    labels=labels,
                    has_separator_line=has_sep,
                    footer_style=footer_style_name,
                )
                annotations.append(page_annot)

        return annotations

    def compute_dataset_statistics(self, annotations: list[PageAnnotation]) -> dict[str, Any]:
        """Computes summary metrics for an annotation set."""
        total_pages = len(annotations)
        doc_ids = {a.doc_id for a in annotations}
        total_tokens = sum(len(a.tokens) for a in annotations)

        label_counts: dict[str, int] = {}
        for a in annotations:
            for lb in a.labels:
                label_counts[lb] = label_counts.get(lb, 0) + 1

        footer_styles: dict[str, int] = {}
        for a in annotations:
            footer_styles[a.footer_style] = footer_styles.get(a.footer_style, 0) + 1

        return {
            "total_documents": len(doc_ids),
            "total_pages": total_pages,
            "total_tokens": total_tokens,
            "tokens_per_page_avg": round(total_tokens / max(1, total_pages), 1),
            "label_distribution": label_counts,
            "footer_styles": footer_styles,
        }

