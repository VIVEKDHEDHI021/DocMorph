# DocMorph Project Blueprint

**Product Tagline:** Every document, personalized.

DocMorph enables users to import academic files, assignments, and practicals, automatically or manually identify student credentials in footers, and replace them with their own saved profile locally on Android.

---

## 1. System Architecture Layers

```
┌────────────────────────────────────────────────────────┐
│                   React 18 Frontend                    │
│   (Vite, Tailwind, PDF.js, Lucide Icons, Router v6)    │
│   - WorkspacePage: 4-Step Personalization Journey      │
│   - PdfViewer: Scaled Canvas Rendering & Navigation    │
│   - SmartSelectionOverlay: Galaxy AI Selection Engine │
└───────────────────────────┬────────────────────────────┘
                            │ Capacitor Plugin Bridge
┌───────────────────────────▼────────────────────────────┐
│               Android Native Plugin Layer              │
│                 (com.docmorph.app.plugin)               │
│   - DocMorphPlugin: Bridge router                      │
│   - SecureProfileManager: Keystore AES encryption      │
│   - LocalPdfStorage: Originals & Personalized storage  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│            On-Device Engine & Detection Core           │
│   - PdfExtractorService: PDFBox text & layout          │
│   - OnnxLayoutInferenceService: Mobile ONNX inference  │
│   - FooterRegionDetector: Phase B Verification Layer   │
│   - UnlabelledIdentityDetector: Credential pairing     │
│   - SmartManualDetector: User-guided Area/Text Search  │
│   - ContentStreamRedactor: Stream-level PDF rewriting  │
│   - OutputVerifier: Post-generation SHA & byte check   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Four Canonical Footer Verification States

| State | Definition | Engine Action |
|---|---|---|
| `FOOTER_CONFIRMED` | Multi-signal evidence confirms genuine footer (separator line, layout compactness, identity pairing). | Extraction and personalization allowed. |
| `FOOTER_NOT_FOUND` | Academic negative keyword found, prose structure detected, or solitary page number. | Automatic personalization blocked; user can use Smart Select. |
| `FOOTER_UNCERTAIN` | Ambiguous position or weak evidence without explicit labels. | Requires human review before replacement. |
| `DOCUMENT_UNREADABLE` | OCR failure, corrupted PDF structure, or out-of-bounds page index. | Error reported cleanly; original file preserved. |

---

## 3. Directory Layout

```
DocMorph/
├── android/                   # Native Android application & Capacitor host
│   ├── app/src/main/java/com/docmorph/app/
│   │   ├── ai/               # ONNX Layout inference service
│   │   ├── detection/        # Footer, Unlabelled, and Smart Manual detection
│   │   ├── pdf/              # PDFBox extraction, content stream redactor
│   │   ├── plugin/           # DocMorphPlugin Capacitor bridge
│   │   └── security/         # Android Keystore secure storage
├── app/                       # Python reference implementation & schemas
│   ├── schemas/              # Pydantic v2 data models
│   └── services/             # Core Python detection and replacement engine
├── frontend/                  # React + TypeScript frontend
│   ├── src/components/       # PdfViewer, SmartSelectionOverlay, etc.
│   ├── src/pages/            # DashboardPage, WorkspacePage, etc.
│   └── src/services/         # localDocService, nativeDocMorph, api
└── tests/                     # 168+ automated unit and integration tests
```
