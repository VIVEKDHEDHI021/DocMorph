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
    │  - Automatic: DetectionOrchestrator runs 4-pass page-by-page scan with cross-page propagation
    │  - Smart Manual: User draws rectangle or highlights text via SmartSelectionOverlay
    ▼
[Phase B Footer Verification & Adaptive Boundary]
    │  - Evaluates layout compactness, separator lines, academic stop words
    │  - Adaptive boundary detects footers with variable vertical positions (up to 80pt variance)
    │  - Produces canonical status: CONFIRMED / NOT_FOUND / UNCERTAIN / UNREADABLE
    ▼
[Student Identity Extraction & Multi-Page Aggregation]
    │  - Matches explicit labels (Name:, Enrollment No:, Roll No:) across all pages
    │  - Identifies unlabelled identity pairs: Name (ID)
    │  - Propagates verified identity values to other pages' header/footer zones
    │  - Aggregates multi-page occurrences without dropping page indices
    ▼
[Profile Matching & Replacement Plan Preview]
    │  - Compares detected original values with local saved student profile
    │  - Expands confirmed fields across all page occurrences in candidate cache
    ▼
[PDF Personalization Engine]
    │  - PdfPersonalizerService & ContentStreamRedactor rewrite text in PDF stream
    │  - Recursively inspects and redacts shared Form XObjects (/PDFormXObject)
    │  - Adaptive typography scaling preserves font sizes and visual baseline
    │  - Scanned pages receive raster white background patching before vector insertion
    ▼
[Output Verification & Storage]
    │  - OutputVerifier conducts per-page independent audit (PageVerificationResult)
    │  - Confirms old identity values absent and new values present
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
