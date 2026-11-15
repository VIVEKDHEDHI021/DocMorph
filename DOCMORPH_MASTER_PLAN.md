# DOCMORPH MASTER PLAN
**Tagline:** Every document, personalized.  
**Category:** Document Personalization SaaS

---

## 1. Executive Summary

DocMorph is a specialized Document Personalization SaaS engineered specifically for students and academic institutions. It enables users to upload shared practical lab manuals, assignments, and reports in PDF format and personalize student-specific header/footer metadata (Student Name, Enrollment Number, Roll Number, Student ID) without converting the PDF to Word, breaking vector diagrams, or disturbing document layout.

---

## 2. Five-Phase Engineering Roadmap

- [x] **Phase 1: Core PDF Engine** *(Completed)*
  - PDF upload validation, signature verification, size checks, path traversal mitigation.
  - Safe document lifecycle management (leak-free context managers, non-destructive read-only access).
  - Robust metadata extraction (title, author, subject, creation date, PDF version, page count).
  - Layout-preserving page-by-page selectable text extraction with natural reading order.
  - Granular document statistics (total pages, selectable-text vs empty pages, character & word counts).
  - Pydantic v2 data models for type-safe structured responses.
  - CLI analysis interface and comprehensive automated test suite (28 tests).

- [x] **Phase 2: Intelligent Detection Engine** *(Completed & Enhanced)*
  - Geometric footer region identification across portrait, landscape, and custom page sizes.
  - Typography-aware structured text, line, span, and exact bounding box extraction via PyMuPDF.
  - Robust recognition of four student fields (`student_name`, `enrollment_number`, `roll_number`, `student_id`) across case, punctuation, and abbreviation variations.
  - **Unlabelled Student Identity Recognition:** Layout-driven, position-aware detection of combined identity pairs (e.g. `Vivek dhedhi (92400120571)`, `Name - ID`, `ID | Name`) in academic footers without explicit labels.
  - Vector footer separator line detection (`find_footer_separator_line`) with proximity-based confidence boosting.
  - Disambiguation and strict exclusion of bottom-right page numbers (`Page X of Y`, isolated digits) from student identifiers.
  - Academic stop-words validation rejecting non-name department, subject, and institutional terms.
  - Separate, non-overlapping bounding box generation isolating student name and identifier independently.
  - Contextual value extraction across single-line, multi-field, and adjacent-line associations.
  - Multi-factor explainable confidence scoring (0.0 to 1.0) with categorical tiers (`high`, `medium`, `low`).
  - Document-wide grouping of repeated field occurrences with individual coordinate retention and cross-page consistency boosting.
  - Cross-page value discrepancy and conflict detection (`conflicts`).
  - Human-in-the-loop manual review workflow (`confirm`, `correct`, `reject`, `change_type`).
  - Comprehensive automated test suite (40 detection tests, 119 total tests).

- [x] **Phase 3: PDF Personalization and Replacement Engine** *(Completed)*
  - Precise text purging using PyMuPDF redaction annotations (`apply_redactions(images=0, graphics=0, text=0)`), preserving underlying vector graphics and borders.
  - Strict security validation: requires explicit confirmation/correction (`UnconfirmedFieldError`), rejecting unconfirmed or rejected fields.
  - Advanced typography extraction: baseline origin tracking, font mapping to standard base-14 PDF fonts (`helv`, `hebo`, `times`, `cour`), and 24-bit normalized RGB color extraction.
  - Horizontal clearance & adaptive font scaling down to `MIN_REPLACEMENT_FONT_SIZE` (6.0pt) to prevent overlapping neighboring delimiters or fields.
  - Physical text collision prevention: records explicit replacement failure if text cannot fit within available horizontal clearance without corrupting layout.
  - Document immutability: original PDF remains strictly untouched with pre/post SHA-256 verification; output is written to a distinct personalized file.
  - Multi-layer independent post-generation verification (`OutputVerifier`): verifies document validity, page count, presence of new values, absence of purged old values at exact bounding boxes, and label preservation.
  - Comprehensive automated test suite (19 tests).

- [x] **Phase 4: Complete Full-Stack Application, Frontend, Backend API & User Experience** *(Completed)*
  - FastAPI REST API v1 (`/api/v1/auth`, `/api/v1/documents`, `/api/v1/detections`, `/api/v1/personalization`, `/api/v1/jobs`).
  - StorageProvider abstraction (`LocalStorageProvider`) isolating document storage and preventing directory traversal.
  - SQLAlchemy 2.0 database models & repositories for users, documents, detections, occurrences, jobs, and personalized outputs.
  - Per-user document ownership and tenant isolation across all endpoints.
  - Direct bcrypt authentication and JWT authorization with developer guest mode.
  - Responsive React 18 + Vite + TypeScript + Tailwind CSS web frontend.
  - Public Landing Page with feature showcases, interactive comparisons, and FAQ.
  - User Dashboard with live statistics, drag-and-drop upload, search, and document management.
  - 5-stage Document Workspace Studio: Upload & PDF.js preview $\rightarrow$ Detection & Review $\rightarrow$ Personalize Form $\rightarrow$ Progress $\rightarrow$ Result, Verification Checklist, Side-by-side comparison, and Download.
  - Full automated integration and component test suite (24 tests).

- [x] **Phase 5: Production Readiness, Security, Performance & Deployment** *(Completed)*
  - Comprehensive security hardening: `SecurityHeadersMiddleware`, correlation tracing via `X-Request-ID`, and sliding-window `RateLimitMiddleware`.
  - Production database migration framework using **Alembic** stamped to initial schema `ec8176948447`.
  - Remote object storage integration: **`S3StorageProvider`** supporting Cloudflare R2, AWS S3, and MinIO.
  - Frontend optimization: Route-level code-splitting and chunk partitioning reducing initial load JS bundle by ~65%.
  - Structured application logging with automatic sensitive credential redaction (`SensitiveDataFilter`).
  - Health checks: `/health` (liveness) and `/ready` (readiness verifying database connection and storage write access).
  - Deployment tooling: Production multi-stage `Dockerfile`, `frontend/Dockerfile`, `nginx.conf`, `docker-compose.yml`, and GitHub Actions CI workflow (`.github/workflows/ci.yml`).
  - 105 automated backend tests executing with 100% pass rate.

---

## 3. Production Architecture Diagram

```
                       +---------------------------------------+
                       |           React + Vite SPA            |
                       |       (Cloudflare Pages CDN)          |
                       +-------------------+-------------------+
                                           |  HTTPS / Bearer JWT
                                           v
+-----------------------------------------------------------------------------------+
|                        Containerized FastAPI ASGI Backend                         |
|                                                                                   |
|  Middlewares:                                                                     |
|  - RequestIdMiddleware (X-Request-ID correlation tracing)                         |
|  - SecurityHeadersMiddleware (HSTS, nosniff, DENY, strict-origin)                |
|  - RateLimitMiddleware (15/min auth, 30/min upload, 180/min api)                  |
|  - CORSMiddleware (Sanitized explicit origins)                                    |
|                                                                                   |
|  APIs:                                                                            |
|  +-------------------+  +---------------------+  +-----------------------------+  |
|  |   /api/v1/auth    |  |  /api/v1/documents  |  | /api/v1/detections          |  |
|  +-------------------+  +---------------------+  +-----------------------------+  |
|  | /api/v1/personalize                          |  | /api/v1/jobs & downloads    |  |
|  +---------------------------------------------+  +-----------------------------+  |
|  | /health (Liveness)                           |  | /ready (Readiness probe)    |  |
|  +---------------------------------------------+  +-----------------------------+  |
+-----------------------------------------+-----------------------------------------+
                                          |
                   +----------------------+----------------------+
                   |                                             |
                   v                                             v
     +---------------------------+                 +---------------------------+
     |   SQLAlchemy 2.0 Repos    |                 |  StorageProvider          |
     |   (PostgreSQL 16)         |                 |  - LocalStorageProvider   |
     |   - Managed by Alembic    |                 |  - S3StorageProvider (R2) |
     |   - Connection Pooling    |                 +---------------------------+
     +-------------+-------------+                               |
                   |                                             v
                   v                               +---------------------------+
     +---------------------------+                 | Core PDF Engines (Ph 1-3) |
     |   docmorph DB             |                 | - PDFAnalyzer             |
     |   (users, documents,      |                 | - DetectionEngine         |
     |    detections, jobs)      |                 | - PDFReplacer             |
     +---------------------------+                 | - OutputVerifier          |
                                                   +---------------------------+
```
