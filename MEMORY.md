# DocMorph Project Memory

**Application:** DocMorph — Every document, personalized.  
**Target Platform:** 100% Offline Android (Capacitor + Kotlin + PDFBox-Android + ML Kit OCR + ONNX Runtime Mobile).  
**Core Mission:** Allow students and educators to import academic files, detect existing student credential footers, and replace them with their own saved student profile locally on-device.

---

## Architectural Invariants (Non-Negotiable)

1. **100% On-Device & Offline**:
   - Zero remote HTTP runtime dependencies.
   - Prohibited at runtime: FastAPI, OpenAI, Gemini API, Anthropic API, Supabase, Firebase, AWS/GCP, Cloudflare Workers, remote model/OCR downloads.
   - Core functionality must work flawlessly in Airplane Mode with Wi-Fi and mobile data disabled.

2. **Source Document Immutability**:
   - Original imported PDFs are never overwritten or mutated in-place.
   - Original SHA-256 is recorded before modification and verified after.
   - Personalized PDFs are generated into a distinct local `personalized/` directory.

3. **Selection is a Detection Hint, NOT Content Editing**:
   - Smart Selection (Area and Text selection) provides search boundary coordinates to the engine.
   - Content inside selections undergoes full Phase B Footer Verification and student-identity classification before any replacement is planned.
   - No arbitrary manual text typing into PDF streams; only structured field replacement using verified local profiles.

---

## Phase Milestones & Current State

### Phase A: Architecture & False-Positive Root Cause Audit (Completed)
- Uncovered root cause of false positives: Heuristic vertical-position bias ($\ge 80\%$ page height) in `OnnxLayoutInferenceService.kt` and `FooterRegionDetector.kt` unconditionally assumed trailing bottom text like "Conclusion" or "References" was a student footer (93.7% false confidence).

### Phase B: Footer Verification Layer (Completed)
- Introduced 4 canonical verification states: `FOOTER_CONFIRMED`, `FOOTER_NOT_FOUND`, `FOOTER_UNCERTAIN`, `DOCUMENT_UNREADABLE`.
- Implemented multi-signal verification: layout compactness, vector rule detection, academic stop words, experiment/chapter patterns, solitary page number penalties, and running prose checks.
- Prevented false positives on conclusion paragraphs, experiment numbers, and solitary page numbers.

### Phase C: Smart Manual Detection Engine (Completed)
- Implemented `SmartManualDetector.kt` and `smart_manual_detector.py`.
- Supports Area Selection (rectangle bounds) and Text Selection (string/bounding box).
- Converts normalized $[0, 1000]$ and display coordinates to exact PDF user points.
- Extracts explicit labels (`Name:`, `Enrollment:`), unlabelled identity pairs (`Name (Enrollment)`), and isolated tokens.
- 17 unit tests passing.

### Phase D: Smart Selection UI & PDF Viewer Integration (Completed)
- Added Galaxy AI and Circle to Search-inspired Smart Select button in `PdfViewer.tsx`.
- Implemented `SmartSelectionOverlay.tsx` with touch-and-drag area selection, 4 draggable corner handles, hardware-accelerated outer dimming (`box-shadow: 0 0 0 9999px rgba(15,23,42,0.45)`), and electric violet glowing border.
- Implemented interactive text token selection using PDF.js text layer.
- Added floating contextual action & results panel with asynchronous race-condition prevention (`requestSeqRef`).

### Phase E: End-to-End Personalization Integration (Completed)
- Connected Smart Manual Detection with the complete PDF personalization pipeline.
- Verified candidates from `manualDetect` merge seamlessly into `candidateCache` in `DocMorphPlugin.kt` and `localDocService.ts`.
- Integrated with `PdfPersonalizerService.kt` / `ContentStreamRedactor.kt` and Python reference `PDFReplacer`.
- Full regression suite passing: 168/168 tests (100% pass rate).
