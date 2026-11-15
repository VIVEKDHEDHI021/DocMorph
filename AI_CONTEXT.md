# DocMorph AI Context & Developer Guide

This document provides essential context, architectural invariants, and design guidelines for AI assistants and software engineers working on the DocMorph codebase.

---

## 1. Project Mission & Identity

DocMorph is a **100% offline, on-device Android application** designed to personalize academic files, lab assignments, and practicals.
- **Product Tagline:** *Every document, personalized.*
- **Core User Journey:** Import PDF → View document → Intelligent footer detection (automatic or Smart Manual Selection) → Verify student credentials → Match with saved student profile → Review & confirm → Personalize PDF via stream rewriting → Export/Share.

---

## 2. Non-Negotiable Architectural Invariants

1. **Zero Remote Network Dependencies at Runtime:**
   - No remote FastAPI backends.
   - No OpenAI, Gemini, or Anthropic API calls.
   - No cloud OCR, Cloudflare Workers, Supabase runtime, or AWS/GCP services.
   - All OCR is handled via bundled on-device ML Kit / Tesseract.
   - All AI inference runs via local ONNX Runtime Mobile (`onnxruntime-android`).
   - The application must function completely with Wi-Fi and mobile data turned off.

2. **Source Document Immutability:**
   - Never mutate or overwrite the imported original PDF file.
   - Original file SHA-256 is recorded upon import and verified after personalization.
   - All personalized outputs are written to separate unique files in `files/personalized/`.

3. **Selection is an Input Search Boundary, Not Content Modification:**
   - User selections (Area or Text) provide coordinate boundaries to the engine.
   - They must **never** be used as manual text editing tools, text injection inputs, or arbitrary replacements.
   - Everything inside a selection boundary must pass Phase B Footer Verification and student identity classification before any field is created.

---

## 3. Key Components & Implementation Map

- **Footer Verification Layer (Phase B):**
  - Python: `app/services/footer_verifier.py`, `app/schemas/footer_verification.py`
  - Kotlin: `android/app/src/main/java/com/docmorph/app/detection/FooterRegionDetector.kt`, `FooterStatus.kt`
  - Canonical states: `FOOTER_CONFIRMED`, `FOOTER_NOT_FOUND`, `FOOTER_UNCERTAIN`, `DOCUMENT_UNREADABLE`.
  - Negative stop words: Academic faculties, departments, "Conclusion", "References", chapter/experiment numbers, solitary page numbers.

- **Smart Manual Detection (Phase C):**
  - Python: `app/services/smart_manual_detector.py`, `app/schemas/manual_detection.py`
  - Kotlin: `android/app/src/main/java/com/docmorph/app/detection/SmartManualDetector.kt`, `ManualDetectionModels.kt`
  - Capacitor Bridge: `@PluginMethod fun manualDetect` in `DocMorphPlugin.kt`
  - Supported modes: Area Selection (rectangular bounds) and Text Selection (string/bbox).

- **Smart Selection UI (Phase D):**
  - React Component: `frontend/src/components/SmartSelectionOverlay.tsx`
  - Viewer Integration: `frontend/src/components/PdfViewer.tsx`
  - Design Inspiration: Google Circle to Search (fluid interaction) + Samsung Galaxy AI (visual accents, glowing electric blue/violet borders, dark glassmorphism card, rounded resize handles).

- **PDF Personalization & Redaction (Phase E):**
  - Native Engine: `android/app/src/main/java/com/docmorph/app/pdf/PdfPersonalizerService.kt`, `ContentStreamRedactor.kt`, `TypographyFormatter.kt`, `OutputVerifier.kt`
  - Python Reference: `app/services/pdf_replacer.py`, `UnifiedPdfReplacer`
  - Frontend Bridge: `frontend/src/services/localDocService.ts`, `nativeDocMorph.ts`
  - Workflow Page: `frontend/src/pages/WorkspacePage.tsx` (4-Step Guided Workflow).

---

## 4. Testing & Verification Rules

- **Python Tests:** `pytest -q` (168 tests, 100% pass rate).
- **Frontend Build:** `npm --prefix frontend run build` (`tsc && vite build`).
- **Android Gradle Build:** `cd android; ./gradlew.bat compileDebugSources`.
- **Honesty Rule:** Never claim a test passed if it was not executed; report all failures transparently.
