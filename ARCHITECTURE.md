# DocMorph Technical Architecture

DocMorph is designed as a **100% offline, privacy-first Android application**.

---

## 1. Complete Workflow Pipeline

```
[Import PDF]
    │  (Stored in Android internal sandbox: files/originals/<id>.pdf)
    ▼
[PDF Preview & Canvas Render]
    │  (Rendered via local pdfjs-dist worker in PdfViewer.tsx)
    ▼
[Automatic Detection OR Smart Manual Selection]
    │  - Automatic: DetectionOrchestrator runs multi-modal scan
    │  - Smart Manual: User draws rectangle or highlights text via SmartSelectionOverlay
    ▼
[Phase B Footer Verification Layer]
    │  - Evaluates layout compactness, separator lines, academic stop words
    │  - Produces canonical status: CONFIRMED / NOT_FOUND / UNCERTAIN / UNREADABLE
    ▼
[Student Identity Extraction]
    │  - Matches explicit labels (Name:, Enrollment No:, Roll No:)
    │  - Identifies unlabelled identity pairs: Name (ID)
    ▼
[Profile Matching & Replacement Plan Preview]
    │  - Compares detected original values with local saved student profile
    │  - User reviews and confirms proposed replacements
    ▼
[PDF Personalization Engine]
    │  - PdfPersonalizerService & ContentStreamRedactor rewrite text in PDF stream
    │  - Adaptive typography scaling preserves font sizes and visual baseline
    ▼
[Output Verification & Storage]
    │  - OutputVerifier verifies output file integrity and non-empty streams
    │  - Stored in files/personalized/<id>_personalized.pdf
    │  - Original SHA-256 verified unchanged
    ▼
[User Actions]
    - View personalized PDF in PdfViewer
    - Share via Android Intent
    - Export to device Downloads directory
```

---

## 2. Coordinate Transformation System

All selections and replacements are governed by the coordinate transformation model:

1. **Screen / Touch Pixels to Display Pixels**:
   $$x_{\text{canvas}} = \text{clientX} - \text{canvas.left}$$
   $$y_{\text{canvas}} = \text{clientY} - \text{canvas.top}$$

2. **Display Pixels to Native PDF User Points**:
   $$x_{\text{pdf}} = \frac{x_{\text{canvas}}}{\text{scale}}$$
   $$y_{\text{pdf}} = \frac{y_{\text{canvas}}}{\text{scale}}$$

3. **Normalized [0, 1000] Space**:
   $$x_{\text{norm}} = \text{round}\left(\frac{x_{\text{pdf}}}{\text{pageWidth}} \times 1000\right)$$
   $$y_{\text{norm}} = \text{round}\left(\frac{y_{\text{pdf}}}{\text{pageHeight}} \times 1000\right)$$

This mapping is invariant across zoom levels, orientation changes, screen densities, and device pixel ratios.
