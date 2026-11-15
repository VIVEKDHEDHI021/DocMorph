# Phase C Implementation Report: Smart Manual Detection Engine

**DocMorph — Every document, personalized.**  
**Status:** Completed & Fully Validated  
**Mode:** 100% Offline On-Device PDF Processing  

---

## 1. Executive Summary

Phase C implements **Smart Manual Detection**, enabling users to guide DocMorph's local detection engine through user-defined bounding coordinates (**Area Selection**) or textual markers (**Text Selection**). 

### Core Architectural Principle
> **Selection is a detection instruction, NEVER an instruction to modify or edit PDF content.**
> Selected content serves strictly as an input boundary hint for the engine. All content within the boundary undergoes Phase B multi-signal Footer Verification and rigorous student-identity classification before any field is identified. No manual typing, text injection, or arbitrary replacements are allowed.

---

## 2. Architecture & Pipeline

1. **Coordinate Validation**: Normalizes coordinates, validates non-zero area ($\ge 15\,\text{pt}^2$), rejects inverted geometries, and clamps tightly to document dimensions.
2. **Boundary Filtering**: Selects only structured text lines whose centers fall inside the bounding box or share $\ge 20\%$ horizontal and $\ge 40\%$ vertical overlap. Unrelated body text outside the selection is strictly excluded.
3. **Phase B Verification**: Evaluates academic stop words, experiment/chapter patterns, solitary page numbers, running prose, and vertical positioning ($\ge 65\%$ for lower-page footers).
4. **Student Information Detection**:
   - **Pass 1**: Explicit labels (`Name:`, `Enrollment No:`, `Roll No:`).
   - **Pass 2**: Unlabelled identity pairs (`Name (Enrollment)` / `Name - Roll`).
   - **Pass 3**: Isolated token highlights (single name or single enrollment).
5. **Output**: Immutable structured response containing resolved PDF coordinates, verification status, and detected student candidate fields.

---

## 3. Exact Files Modified & Created

### Python Local Processing Layer
- `app/schemas/manual_detection.py` (Created): Pydantic v2 schemas (`SelectionType`, `ManualSelectionRequest`, `ManualDetectionResponse`).
- `app/services/smart_manual_detector.py` (Created): Core manual detection engine orchestrating geometry resolution, text isolation, Phase B verification, and student field extraction.
- `tests/test_smart_manual_detection.py` (Created): 17 automated unit and functional tests covering area/text selection, clamping, multi-page, non-standard dimensions, and negative rejections.

### Android Native Bridge & Engine Layer
- `android/app/src/main/java/com/docmorph/app/detection/ManualDetectionModels.kt` (Created): Native Kotlin data models (`SelectionType`, `ManualSelectionInput`, `ManualDetectionResult`).
- `android/app/src/main/java/com/docmorph/app/detection/SmartManualDetector.kt` (Created): Android-native implementation mirroring Python logic, integrated with PDFBox-Android and ML Kit OCR.
- `android/app/src/main/java/com/docmorph/app/plugin/DocMorphPlugin.kt` (Modified): Added `@PluginMethod fun manualDetect(call: PluginCall)` and cached page extraction results for instant selection queries.

### Frontend Native Bridge Types
- `frontend/src/services/nativeDocMorph.ts` (Modified): Added `ManualSelectionInput`, `ManualDetectionResult`, and `manualDetect` to Capacitor plugin interface.
- `frontend/src/services/localDocService.ts` (Modified): Implemented `manualDetect()` method routing to Android native plugin with web mock fallback.

---

## 4. Coordinate Transformation & Geometry Validation

1. **Normalized to PDF Point Conversion**:
   $$\text{PDF}_x = \frac{\text{norm}_x}{1000.0} \times \text{PageWidth}, \quad \text{PDF}_y = \frac{\text{norm}_y}{1000.0} \times \text{PageHeight}$$
2. **Text Selection Padding**:
   Text selections receive $\pm 8\,\text{pt}$ horizontal and $\pm 4\,\text{pt}$ vertical padding to ensure line-level context without bleeding into adjacent lines.
3. **Clamping & Invariant Checks**:
   - $x_1 > x_0$ and $y_1 > y_0$ enforced.
   - Area threshold: $\text{Width} \times \text{Height} \ge 15.0\,\text{pt}^2$.
   - Bound clamping: $x \in [0, \text{PageWidth}]$, $y \in [0, \text{PageHeight}]$.

---

## 5. Functional Testing & Validation Matrix

All test cases executed against real synthetic and academic PDF documents:

| Test Case | Selection Method | Target Content | Expected Status | Result | Notes |
|---|---|---|---|---|---|
| **TC-01** | Area (Rect) | Genuine Footer (Name + Roll) | `FOOTER_CONFIRMED` | **PASS** | Extracted name & enrollment with conf $\ge 0.90$ |
| **TC-02** | Area (Normalized) | Bottom region $[65, 915, 950, 975]$ | `FOOTER_CONFIRMED` | **PASS** | Mapped $[0,1000]$ accurately to PDF points |
| **TC-03** | Area (Rect) | Trailing "Conclusion" paragraph | `FOOTER_NOT_FOUND` | **PASS** | Rejected due to negative academic keyword |
| **TC-04** | Area (Rect) | Header "Experiment 4: Trees" | `FOOTER_NOT_FOUND` | **PASS** | Rejected due to experiment pattern & mid-page y |
| **TC-05** | Area (Rect) | Out-of-bounds $[-50, 720, 700, 850]$ | `FOOTER_CONFIRMED` | **PASS** | Clamped to $[0, 612, 792]$ without text leakage |
| **TC-06** | Area (Rect) | Inverted box ($x_1 < x_0$) | `FOOTER_NOT_FOUND` | **PASS** | Validation error: "Invalid dimensions" |
| **TC-07** | Area (Rect) | Empty white margin | `FOOTER_NOT_FOUND` | **PASS** | Validation error: "No selectable text found" |
| **TC-08** | Text Selection | Student name "Vivek Dhedhi" | `FOOTER_CONFIRMED` | **PASS** | Isolated student name field with conf 0.88 |
| **TC-09** | Text Selection | Enrollment digits "92400120571" | `FOOTER_CONFIRMED` | **PASS** | Isolated enrollment number field with conf 0.88 |
| **TC-10** | Text Selection | Running prose sentence | `FOOTER_NOT_FOUND` | **PASS** | Rejected prose running sentence structure |
| **TC-11** | Text Selection | Solitary "Page 1 of 4" | `FOOTER_NOT_FOUND` | **PASS** | Solitary page number penalty triggered |
| **TC-12** | Area (Rect) | Landscape ($792 \times 612$) & A4 ($595 \times 842$) | `FOOTER_CONFIRMED` | **PASS** | Coordinate scaling verified across aspect ratios |
| **TC-13** | Area (Rect) | Invalid page index ($99$) | `DOCUMENT_UNREADABLE`| **PASS** | Page bounds error reported cleanly |
| **TC-14** | Text Selection | Text Bounding Box (no text string) | `FOOTER_CONFIRMED` | **PASS** | Coordinate box isolated text correctly |
| **TC-15** | Area (Rect) | Partial footer (enrollment digits only)| `FOOTER_CONFIRMED` | **PASS** | Bounding box intersection detected field |
| **TC-16** | Area (Rect) | Mid-page student name ($y \approx 420\,\text{pt}$)| `FOOTER_UNCERTAIN` | **PASS** | Low vertical position penalized |
| **TC-17** | Area (Rect) | Multi-page PDF (Page 3 of 4) | `FOOTER_CONFIRMED` | **PASS** | Targeted specifically Page 3 context |

---

## 6. Regression & Build Suite Verification

- **Python Regression Suite:** 163 passed in 76.90s (100% pass rate).
- **Android Gradle Verification:** `BUILD SUCCESSFUL in 21s`.
- **Frontend Build (`tsc && vite build`):** Built cleanly in 4.29s with 0 errors.

---

## 7. 100% Offline Architecture Verification

- All extraction executed through on-device libraries (PyMuPDF locally; PDFBox-Android and bundled Google ML Kit in Android).
- Zero remote API calls, network sockets, or cloud dependencies.
- Original source PDF files remain immutable and untouched.

---

## 8. Remaining Limitations & Edge Cases

1. **Extreme Rotation ($90^\circ$ / $270^\circ$)**: Coordinate transforms assume unrotated or pre-normalized page coordinate frames.
2. **Heavily Degraded Scans**: If OCR produces illegible characters for an enrollment number, the engine marks the result as `FOOTER_UNCERTAIN` or `DOCUMENT_UNREADABLE`, requiring user review rather than hallucinating.

---

## 9. Hand-off for Phase D

The smart manual detection engine is ready to receive selection events from the user interface.

**Phase D Scope (Awaiting Approval):**
- Circle to Search-inspired selection interaction in the PDF viewer.
- Samsung Galaxy AI-inspired visual styling (shimmering glows, selection halos, and confirmation dialogs).
- Connecting viewer drag/tap events to `localDocService.manualDetect()`.
- Interactive candidate review overlay.
