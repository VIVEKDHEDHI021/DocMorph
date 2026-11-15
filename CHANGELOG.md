# DocMorph Changelog

All notable changes to the DocMorph PDF personalization engine.

---

## [Phase E] - 2026-11-15
### Added
- Integrated Smart Manual Detection with complete PDF personalization workflow.
- Connected `manualDetect` candidate outputs to native `candidateCache` and TypeScript `localDocService`.
- Added end-to-end integration tests in `tests/test_phase_e_integration.py`.
- Source document immutability verification (SHA-256 pre and post personalizing).
- 168/168 automated regression tests passing.

## [Phase D] - 2026-11-15
### Added
- `SmartSelectionOverlay.tsx`: Interactive selection interface inspired by Google Circle to Search and Samsung Galaxy AI.
- Rectangular touch-and-drag area selection with 4 corner resize handles.
- Outer background dimming (`box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.45)`).
- Text token selection using PDF.js text layer.
- Floating contextual action & results panel with asynchronous race-condition prevention (`requestSeqRef`).
- Added Smart Select toggle to `PdfViewer.tsx` toolbar.

## [Phase C] - 2026-11-15
### Added
- `SmartManualDetector.kt` and `smart_manual_detector.py`: User-guided area and text selection engine.
- Bounding box coordinate resolution between normalized $[0, 1000]$ and PDF points.
- 17 unit and functional tests in `tests/test_smart_manual_detection.py`.
- Bridge integration via `@PluginMethod fun manualDetect` in `DocMorphPlugin.kt`.

## [Phase B] - 2026-11-15
### Added
- Dedicated Footer Verification Layer (`FooterVerifier.py` / `FooterStatus.kt`).
- 4 canonical verification states (`FOOTER_CONFIRMED`, `FOOTER_NOT_FOUND`, `FOOTER_UNCERTAIN`, `DOCUMENT_UNREADABLE`).
- Fixed vertical-position bias in `OnnxLayoutInferenceService.kt` and `_heuristic_layout_prediction`.
- Solitary page number penalty and comprehensive academic stop words.
- Eliminated false-positive "Conclusion" classification.

## [Phase A] - 2026-11-15
### Added
- Initial system audit and root cause reproduction report.
- Verified 100% offline architectural boundaries.
- Watermark removal from app icon and generated mipmaps across Android densities (`mdpi` through `xxxhdpi`).
- Initialized and synchronized GitHub repository: `https://github.com/VIVEKDHEDHI021/DocMorph.git`.
