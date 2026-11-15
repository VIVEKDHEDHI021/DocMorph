# DocMorph Project Roadmap

## Phase Status Summary

- [x] **Phase A — Existing Engine Audit & Root Cause Analysis**
  - Empirically reproduced "Conclusion" false positive (93.7% confidence bias).
  - Verified 100% offline boundaries.
- [x] **Phase B — Footer Verification Layer**
  - 4 canonical states: `FOOTER_CONFIRMED`, `FOOTER_NOT_FOUND`, `FOOTER_UNCERTAIN`, `DOCUMENT_UNREADABLE`.
  - Multi-signal verification (layout compactness, vector rules, academic stop words).
- [x] **Phase C — Smart Manual Detection Engine**
  - Area selection and text selection backend engines.
  - Coordinate resolution to PDF points.
  - Integration with Phase B verification.
- [x] **Phase D — Smart Selection UI & PDF Viewer Integration**
  - Circle to Search interaction and Samsung Galaxy AI visual language.
  - Resizing handles, background dimming, and text token highlighting.
  - Floating contextual action and results panel.
- [x] **Phase E — Smart Detection to PDF Personalization Integration**
  - End-to-end connection from selection to replacement preview and PDF generation.
  - Source document immutability verification.
  - 168/168 automated regression tests passing.

---

## Future Roadmap (Phase F & Beyond)

- [ ] **Phase F — Production Packaging & Hardening**
  - Android Release APK / AAB signing setup.
  - Performance profiling on low-end ARM64/armeabi-v7a Android devices.
  - Batch document personalization queue.
  - Dark mode enhancements for PDF canvas viewer.
