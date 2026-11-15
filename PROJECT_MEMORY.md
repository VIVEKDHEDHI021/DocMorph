# DOCMORPH — PROJECT MEMORY

**Product:** DocMorph  
**Tagline:** Every document, personalized.  
**Category:** Academic Document Personalization SaaS  
**Version:** 1.0.0 (Production-Ready)  
**Last Updated:** November 2026  

---

## 1. Project Overview & Mission

DocMorph is a specialized document personalization SaaS engineered specifically for students and academic institutions. It enables users to upload shared practical lab manuals, assignments, and reports in PDF format and personalize student-specific header/footer metadata (**Student Name**, **Enrollment Number**, **Roll Number**, **Student ID**) without converting the PDF to Word, breaking vector diagrams, disturbing formatting, or compromising document layout.

### Core Supported Fields
1. `student_name` — e.g., "Vivek Dhedhi", "Rahul Patel", "Neel Vyas"
2. `enrollment_number` — e.g., "92400120571", "2300012345" (typically 6–18 digits)
3. `roll_number` — e.g., "25", "42", "21CS045" (numeric or alphanumeric)
4. `student_id` — e.g., "STU-99201", "ID-4021"

---

## 2. Technology Stack & Environment

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | 3.12+ | Core backend runtime |
| **Backend API** | FastAPI | 0.115+ | High-performance RESTful API |
| **PDF Processing** | PyMuPDF (`fitz`) | 1.25+ | Precision text/vector extraction, redaction, text insertion |
| **Data Validation** | Pydantic v2 | 2.10+ | Strict schemas, models, and type safety |
| **Database** | SQLite / PostgreSQL | SQLAlchemy 2.0 | User, document, detection, and job persistence |
| **Migrations** | Alembic | 1.14+ | Schema version control (`ec8176948447`) |
| **Frontend** | React 18 + TypeScript | Vite 6 | Modern, responsive SPA |
| **Styling** | Tailwind CSS | 3.4+ | Utility-first styling & accessible UI |
| **PDF Viewer** | PDF.js | 4.0+ | Canvas-based in-browser document preview |
| **AI Document Understanding** | scikit-learn, joblib | 1.6+ | Universal layout-aware token classification |
| **Storage** | Local / AWS S3 / MinIO | Custom Abstraction | Tenant-isolated storage provider |
| **Android Framework** | Capacitor | 8.6.0 | Native Android container and plugin bridge |
| **Android Toolchain** | Gradle / OpenJDK 17 | 8.14.3 / 17.0.20 | Native Android compilation and packaging |
| **Testing** | pytest, pytest-asyncio | 9.0+ | 138 automated unit, integration, and E2E tests |

---

## 3. Critical Architectural Invariants & Memory Bank

### 1. Source Document Immutability
- Original PDFs are **strictly read-only** and must never be altered or overwritten in place.
- SHA-256 hashes are recorded before and after every personalization job. If the pre-hash and post-hash of the input file differ, a critical `PDFReplacementError` is thrown immediately.
- Personalized files are generated as separate, unique PDF files with collision-resistant naming (`personalized_<stem>_<job_id>.pdf`).

### 2. PDF Coordinate Geometry
- Coordinates are in PDF user space points ($1/72$ inch) with the origin $(0, 0)$ at the top-left corner.
- Bounding boxes are formatted as `(x0, y0, x1, y1)`.
- Text is inserted at the **baseline origin point** $(x_0, \text{baseline\_y})$, NOT at $(x_0, y_0)$.

### 3. PyMuPDF Base-14 Font Code Mapping
- PyMuPDF's standard built-in Base-14 fonts use distinct internal font codes:
  - **Times-Roman:** `"tiro"` (NOT `"times"`, which raises `ValueError: Font 'times' is unsupported`)
  - **Times-Bold:** `"tibo"`
  - **Times-Italic:** `"tiit"`
  - **Times-BoldItalic:** `"tibi"`
  - **Helvetica:** `"helv"`
  - **Helvetica-Bold:** `"hebo"`
  - **Helvetica-Oblique:** `"hebi"`
  - **Courier:** `"cour"`
  - **Courier-Bold:** `"cobo"`
- `FormattingAnalyzer.map_font_name()` must always map Times-family fonts to `"tiro"`, with defensive fallbacks around text drawing calls.

### 4. Unlabelled Footer Identity Pairing (Unified Replacement Engine)
- In Indian and international academic PDFs, footers often lack explicit labels like "Name:" or "Enrollment No:". Instead, patterns such as:
  - `Vivekdhedhi(92400120571)`
  - `Vivek dhedhi (92400120571)`
  - `Vivek Dhedhi - 92400120571`
  - `92400120571 - Vivek Dhedhi`
- **Crucial Rule:** When both fields occur on the same unlabelled line, they **must NOT** be replaced as isolated micro-boxes.
  - Redacting them independently leaves orphaned static brackets `(` and `)` and creates gaps or collisions when replacement text lengths vary.
  - Instead, the engine groups them into a **Unified Identity Pair** (`pair_id`), redacts the entire containing line bounding box in one operation, and inserts the unified replacement string (`NeelVyas (92400120560)`) in a single draw call at the shared baseline origin.
  - If the user replaces only the name or only the enrollment number, the engine retains the unchanged partner field and still generates the unified string to preserve document typography.
  - **Explicitly labeled fields** (e.g. `Student Name: Rahul Patel | Enrollment No: 2300012345`) must NOT be merged; they are replaced in-place while keeping labels intact.

### 5. Vector Divider Line Awareness
- Academic PDFs frequently include a horizontal vector rule (e.g. blue or gray border line) separating document body from footer metadata.
- `FooterDetector.find_footer_separator_line()` scans vector drawing paths (`page.get_drawings()`) in the lower 40% of the page. Text positioned immediately below this separator receives significant confidence boosting.

### 6. Storage Provider Abstraction
- The application never stores or exposes raw server filesystem paths to clients or database records.
- All files are referenced by storage keys through `LocalStorageProvider` or `S3StorageProvider`.

### 8. Account-Free Mobile Profiles & Anonymous Sessions
- Android users do not use passwords, emails, or Google Sign-In.
- On launch, the device uses `ProfileStorageService` to retrieve the student profile (Full Name, Enrollment Number, Roll Number, Student ID).
- The client requests an isolated anonymous session via `POST /api/v1/auth/anonymous-session`.
- The backend generates a random `anon_<uuid>` subject with a signed JWT Bearer token.
- All documents and personalization jobs are strictly scoped to the token's user ID.
- File selection utilizes Android's native Storage Access Framework (SAF) via `@capawesome/capacitor-file-picker`.
- Personalized PDFs can be previewed, saved to device cache, opened in external viewers via FileOpener intent, and shared through the native Android Share Sheet.

---

## 4. Current Repository Structure

```
DocMorph/
├── android/                         # Capacitor 8 native Android project
│   ├── app/                         # Android application module (com.docmorph.app)
│   │   ├── build.gradle             # Build config, signing configs, SDK 34-36
│   │   └── src/main/                # Java MainActivity, AndroidManifest, resources
│   └── keystore/                    # Release signing keystore (git-ignored)
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py              # Login, register, guest, anonymous session endpoints
│   │   │   ├── detections.py        # Detection retrieval, field confirmation/correction
│   │   │   ├── documents.py         # PDF upload, metadata extraction, download, deletion
│   │   │   └── personalization.py  # Personalization, auto-personalize, profile matching
│   │   └── router.py                # Combined v1 API router
│   ├── core/
│   │   ├── config.py                # Pydantic Settings (.env configuration)
│   │   ├── exceptions.py            # Domain error taxonomy (DocMorphError, PDFReplacementError, etc.)
│   │   ├── logging.py               # Structured logging with SensitiveDataFilter
│   │   └── security.py              # Password hashing (bcrypt) and JWT encoding/decoding
│   ├── db/
│   │   ├── database.py              # SQLAlchemy engine and session factory
│   │   └── session.py               # Dependency for request-scoped database sessions
│   ├── models/
│   │   ├── user.py                  # User model
│   │   ├── document.py              # Document model
│   │   ├── detection.py             # DetectedField & FieldOccurrence models
│   │   └── job.py                   # PersonalizationJob model
│   ├── schemas/
│   │   ├── analysis.py              # Phase 1 PDF analysis & metadata schemas
│   │   ├── detection_data.py        # Phase 2 Detection schemas (BoundingBox, FieldOccurrence, etc.)
│   │   ├── replacement_data.py      # Phase 3 Personalization schemas (ReplacementRequest, etc.)
│   │   └── document.py              # Document API schemas
│   ├── services/
│   │   ├── pdf_analyzer.py          # Phase 1 layout, metadata, and text analysis
│   │   ├── text_segmenter.py        # Structured line, span, and substring geometry
│   │   ├── footer_detector.py       # Geometric zones & vector separator line detection
│   │   ├── unlabelled_identity_detector.py # Academic unlabelled identity pattern recognition
│   │   ├── detection_engine.py      # Phase 2 hybrid detection coordinator
│   │   ├── formatting_analyzer.py   # Typography, color, Base-14 font mapping, adaptive fitting
│   │   ├── pdf_replacer.py          # Phase 3 Unified Replacement & Personalization engine
│   │   ├── output_verifier.py       # Independent post-replacement output verification
│   │   └── replacement_validator.py # Request integrity & confirmation enforcement
│   ├── storage/
│   │   ├── base.py                  # Abstract StorageProvider interface
│   │   ├── local.py                 # Local filesystem storage implementation
│   │   └── s3.py                    # Remote S3/Cloudflare R2 storage implementation
│   ├── utils/
│   │   └── file_validator.py        # PDF magic-byte validation, sanitization, path traversal checks
│   └── main.py                      # FastAPI application entrypoint with security middlewares
├── frontend/
│   ├── src/
│   │   ├── components/              # UI components (Navbar, Footer, PDFViewer, ReviewCard, etc.)
│   │   ├── pages/                   # Landing, Dashboard, Workspace Studio, Login, Register
│   │   ├── services/                # API client & queries (TanStack Query)
│   │   └── App.tsx                  # Main router and layout
│   ├── package.json
│   └── vite.config.ts
├── tests/
│   ├── conftest.py                  # Pytest fixtures and test PDF generators
│   ├── test_pdf_analyzer.py         # Phase 1 tests
│   ├── test_detection_engine.py     # Phase 2 detection tests
│   ├── test_unlabelled_detection.py # Academic footer unlabelled identity tests
│   ├── test_pdf_replacer.py         # Phase 3 replacement tests
│   ├── test_unified_replacement.py  # Unified multi-field alignment tests
│   ├── test_api_*.py                # API integration tests
│   └── test_end_to_end_journey.py   # Full user workflow tests
├── docs/                            # Audit reports, deployment guides, security reviews
├── PROJECT_MEMORY.md                # This file
├── PROJECT_MASTER_PLAN.md           # Product master roadmap
├── SYSTEM_ARCHITECTURE.md           # Architectural blueprints & diagrams
├── DEVELOPMENT_RULES.md             # Engineering rules & guidelines
├── DEVELOPMENT_LOG.md               # Chronological development timeline
└── README.md                        # Project landing & quickstart guide
```

