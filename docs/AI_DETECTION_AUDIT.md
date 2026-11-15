# DocMorph — AI Detection Engine Audit
**Phase 2.2 — Layout-Aware, Style-Independent Document Understanding**  
**Date:** November 2026  
**Document Status:** Complete Audit & Architecture Specification  

---

## 1. Executive Summary

DocMorph was created to solve academic document personalization ("Every document, personalized") by replacing student identity fields (such as student name, enrollment number, and roll number) across lab manuals, assignment sheets, and project reports without damaging formatting or surrounding graphics.

The current rule-based Phase 2 detection engine operates primarily on:
1. Regex matching on explicit field labels (`Student Name:`, `Enrollment No:`).
2. Spatial heuristic scanning of bottom margins ($y \ge 0.60$ or adaptive footer boundaries).
3. Hardcoded syntactic patterns (e.g. `Name (Enrollment)` combinations).

While this rule-based approach succeeded on the specific test datasets from Marwadi University (e.g., `DWDM_P7_571.pdf`, `92400120571_CCE_Lab01.pdf`), it exhibits fundamental limitations when deployed across diverse, unseen academic documents from other universities and departments.

This audit evaluates the existing codebase, identifies points of failure, analyzes OCR availability, and specifies the architecture for **Phase 2.2: Universal Layout-Aware Document Understanding AI**.

---

## 2. Current Codebase Inspection

### 2.1 Existing Components
| Component | File Path | Current Capabilities | Key Limitations |
| :--- | :--- | :--- | :--- |
| **Text Segmenter** | `app/services/text_segmenter.py` | Extracts text blocks, lines, and character spans with bounding boxes using PyMuPDF. | Native text only. Scanned or image-only pages return 0 spans. |
| **Footer Detector** | `app/services/footer_detector.py` | Calculates adaptive footer boundary using bottom-gap clustering; looks for horizontal separator lines. | Fails on documents with no separator line or varying content height across pages. |
| **Field Detector** | `app/services/field_detector.py` | Regex label recognition (`Student:`, `Enrollment No:`). | Misses 100% of unlabelled credentials unless handled by custom unlabelled regex. |
| **Unlabelled Detector**| `app/services/unlabelled_identity_detector.py` | Matches patterns like `Name (ID)` in the bottom 40% margin. | Hardcoded delimiters (`(`, `-`, `\|`). Confuses titles or faculty names if in footer. |
| **Value Extractor** | `app/services/value_extractor.py` | Splits label from value; computes value bounding box. | Fragile character-offset approximations. |
| **Field Grouper** | `app/services/field_grouper.py` | Groups occurrences across pages; flags conflicts. | Heuristic clustering; lacks semantic embeddings. |
| **Confidence Scorer** | `app/services/confidence_scorer.py` | Computes weighted score based on label match, format, and position. | Simple linear sum; no learned probabilities. |
| **PDF Replacer** | `app/services/pdf_replacer.py` | Phase 3 vector redaction, unified identity alignment, adaptive Base-14 typography. | Works reliably once field bounding boxes and values are confirmed. |

---

## 3. Failure Mode & Limitation Analysis

### 3.1 Template & Position Fragility
* **Assumption of Bottom-Left Position:** Current heuristics give strict bias to bottom-left coordinates. Footers with centered page numbers, right-aligned student names, or two-column tabular footers risk being partially dropped or split incorrectly.
* **Assumption of Separator Lines:** Many university report templates (e.g., IIT, NIT, GTU, VTU) do not use a horizontal vector line above footers, or use shaded bounding boxes, dots, or tables.
* **Label Dependence:** In student project reports, names frequently appear as bare text `John Doe 19BCE1024` without any prefix label.

### 3.2 False Positives & False Negatives
* **False Positives:**
  * University name or department name in the footer mistakenly classified as student name.
  * Experiment number, lab code, or subject code (e.g. `01CE0509`, `CS301`) classified as enrollment numbers.
  * Page number in footer (e.g., `Page 1 of 12` or bare `1`) grouped into student identity string.
  * Faculty in-charge signatures in footer classified as student name.
* **False Negatives:**
  * Scanned PDF pages where text is rasterized into images: returns 0 detected fields.
  * Non-standard delimiters: e.g., `John Doe / 2021-CS-45`, `John Doe [20210034]`.
  * Names with middle initials, honorifics, or single names.
  * Enrollment numbers with letters, slashes, or dashes (e.g. `2021/BIT/042`, `CS-2022-89`).

### 3.3 OCR Status
* Current codebase lacks an automated OCR fallback pipeline. If a student uploads a scanned lab manual or photocopied assignment, the existing `TextSegmenter` extracts empty lines.
* **Solution:** Integrate PyMuPDF's built-in OCR capabilities (`Page.get_textpage_ocr`) and Tesseract fallback into a unified Hybrid PDF Input Pipeline.

---

## 4. Phase 2.2 Target Architecture

To achieve universal layout-aware footer detection without template overfitting, DocMorph Phase 2.2 introduces:

```
[Uploaded PDF]
       │
       ▼
[Hybrid PDF Input Pipeline]
├── Native PyMuPDF Text Extractor (Vector & Spans)
├── OCR Fallback Engine (Scanned & Mixed Pages)
└── Unified Intermediate Representation (Tokens, BBoxes, Images, Confidence)
       │
       ▼
[Layout-Aware Document Understanding Model]
├── Spatial Bounding Box Normalization [0, 1000]
├── Multi-Token Sequence Classification (BIO Tagging)
│   ├── B-FOOTER, I-FOOTER
│   ├── B-STUDENT_NAME, I-STUDENT_NAME
│   ├── B-ENROLLMENT_ID, I-ENROLLMENT_ID
│   ├── B-ROLL_NUMBER, I-ROLL_NUMBER
│   ├── B-STUDENT_ID, I-STUDENT_ID
│   ├── B-PAGE_NUMBER, I-PAGE_NUMBER
│   └── O
└── Visual & Positional Context
       │
       ▼
[Cross-Page Document Structure Analyzer]
├── Multi-Page Alignment & Repetition Verification
├── Recurring Header vs. Recurring Footer Disambiguation
└── Bounding Box Separation (Independent Name & ID Rectangles)
       │
       ▼
[Calibrated Confidence & Evidence Engine]
├── Positional, Layout, Semantic, Cross-Page, Model Evidence
└── Explainable Detection Metadata & Review Routing
       │
       ▼
[Phase 3 PDF Personalization Engine (Preserved)]
```

---

## 5. Required Token Classes & BIO Tagging Schema

The layout-aware model classifies every token into one of 13 BIO labels:
1. `O`: Outside any entity or footer.
2. `B-FOOTER`: Beginning of generic footer region text (e.g., department, institute name).
3. `I-FOOTER`: Continuation of generic footer region text.
4. `B-STUDENT_NAME`: Beginning of student name tokens.
5. `I-STUDENT_NAME`: Continuation of student name tokens.
6. `B-ENROLLMENT_ID`: Beginning of enrollment identifier token.
7. `I-ENROLLMENT_ID`: Continuation of enrollment identifier token.
8. `B-ROLL_NUMBER`: Beginning of roll number token.
9. `I-ROLL_NUMBER`: Continuation of roll number token.
10. `B-STUDENT_ID`: Beginning of student ID token.
11. `I-STUDENT_ID`: Continuation of student ID token.
12. `B-PAGE_NUMBER`: Beginning of page number token.
13. `I-PAGE_NUMBER`: Continuation of page number token.

---

## 6. Training & Evaluation Strategy

1. **Dataset Pipeline (`ai_training/`):**
   * Generate annotated academic documents covering diverse universities (NIT, IIT, GTU, Marwadi, Anna Univ, etc.).
   * Support native, scanned, and multi-column documents.
   * Split 70% Train, 15% Validation, 15% Test strictly by *document* (never leaking pages of the same document across splits).
2. **Model Training:**
   * Provide a reproducible PyTorch / HuggingFace fine-tuning script (`ai_training/train.py`).
   * Provide an ultra-fast, zero-overhead layout classifier fallback (`ai_training/inference.py`) to guarantee high-performance CPU inference in production environments.
3. **Evaluation Metrics:**
   * Token-level and entity-level Precision, Recall, F1 score.
   * Document-level exact-match accuracy.
   * False-positive rate on non-footer body content.

---

## 7. Migration & Compatibility Guarantee
* Phase 1 (Text & Metadata Analysis) remains intact.
* Phase 3 (Vector Redaction, Adaptive Scaling, Unified Alignment Replacement) remains completely compatible.
* Bounding boxes produced by Phase 2.2 seamlessly feed `DetectionResult` and `FieldOccurrence` schemas.

