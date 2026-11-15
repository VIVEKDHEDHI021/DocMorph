# DocMorph — Document Personalization SaaS

> **Tagline:** Every document, personalized.

DocMorph is an academic document personalization platform designed to allow students to upload shared academic practical lab manuals and automatically customize header/footer student credentials (e.g., Student Name, Enrollment Number, Roll Number, Student ID) without altering or damaging the underlying document structure, formatting, or vector diagrams.

---

## 5-Phase Engineering Roadmap Status

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
  - Robust recognition of student fields (`student_name`, `enrollment_number`, `roll_number`, `student_id`) across case, punctuation, and abbreviations.
  - **Unlabelled Student Identity Recognition:** Layout-driven detection of identity pairs (e.g. `Vivek dhedhi (92400120571)`, `Name - ID`, `ID | Name`) in academic footers without explicit labels.
  - Vector footer separator line detection with proximity-based confidence scoring.
  - Strict disambiguation of page numbers (`Page X of Y`, isolated digits on bottom-right) from student credentials.
  - Academic stop-words validation rejecting non-name department and university terms.
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
  - Production-grade FastAPI REST API under `/api/v1` for Auth, Documents, Detections, Personalization, and Jobs.
  - StorageProvider abstraction (`LocalStorageProvider`) with directory traversal protection.
  - SQLAlchemy 2.0 database models & repositories for users, documents, detections, occurrences, jobs, and personalized outputs.
  - Per-user document ownership and tenant boundary enforcement across all endpoints.
  - Responsive React 18 + Vite + TypeScript + Tailwind CSS web frontend.
  - Full Landing Page, Auth Pages (with 1-click Dev Demo login), Dashboard, and 5-stage Workspace Studio.
  - In-browser PDF.js preview with zoom, fit-to-width, page navigation, and original vs personalized toggle.
  - Complete automated test suite: 97 tests passing at 100%.
- [x] **Phase 5: Production Readiness, Security, Performance & Deployment** *(Completed)*
  - Security hardening: `SecurityHeadersMiddleware` (HSTS, nosniff, DENY), correlation tracing via `X-Request-ID`, and sliding-window `RateLimitMiddleware`.
  - Production database migration framework using **Alembic** stamped to initial schema `ec8176948447`.
  - Remote object storage integration: **`S3StorageProvider`** supporting Cloudflare R2, AWS S3, and MinIO.
  - Frontend optimization: Route-level code-splitting and chunk partitioning reducing initial load JS bundle by ~65%.
  - Structured application logging with automatic sensitive credential redaction (`SensitiveDataFilter`).
  - Health checks: `/health` (liveness) and `/ready` (readiness verifying database connection and storage write access).
  - Deployment tooling: Production multi-stage `Dockerfile`, `frontend/Dockerfile`, `nginx.conf`, `docker-compose.yml`, and GitHub Actions CI workflow (`.github/workflows/ci.yml`).
  - 105 automated backend tests executing with 100% pass rate.

---

## Production Documentation

Comprehensive audit and engineering reports are available in [`docs/`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs):

- [`docs/PHASE_5_FINAL_REPORT.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/PHASE_5_FINAL_REPORT.md) — Comprehensive final report and production readiness verdict.
- [`docs/PRODUCTION_CHECKLIST.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/PRODUCTION_CHECKLIST.md) — Acceptance checklist across all 5 phases.
- [`docs/SECURITY_AUDIT.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/SECURITY_AUDIT.md) — Authentication, file safety, API security, and secret management.
- [`docs/PERFORMANCE_REPORT.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/PERFORMANCE_REPORT.md) — Frontend bundle splitting, streaming, database indexing, and memory efficiency.
- [`docs/TESTING_REPORT.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/TESTING_REPORT.md) — 105-test suite breakdown and test execution matrix.
- [`docs/DEPLOYMENT_GUIDE.md`](file:///c:/Users/smitp/OneDrive/Desktop/Work/DocMorph/docs/DEPLOYMENT_GUIDE.md) — Multi-cloud architecture, migrations, and container deployment.

---

## Technology Stack

### Backend
- **Framework:** FastAPI (`fastapi>=0.110.0`, `uvicorn[standard]>=0.29.0`)
- **PDF Engine:** PyMuPDF (`pymupdf>=2.0.0`)
- **ORM & Database:** SQLAlchemy 2.0 (`sqlalchemy>=2.0.0`, SQLite for dev/test, PostgreSQL 16 ready)
- **Migrations:** Alembic (`alembic>=1.13.0`)
- **Object Storage:** Boto3 S3 Client (`boto3>=1.34.0`, Cloudflare R2 / AWS S3) & Local Storage
- **Data Validation:** Pydantic v2 (`pydantic>=2.0.0`, `pydantic-settings>=2.0.0`)
- **Security & Auth:** Direct `bcrypt` password hashing, `python-jose` JWT tokens
- **Testing:** Pytest (`pytest>=8.0.0`, `pytest-asyncio`, `httpx>=0.27.0`)

### Frontend
- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS + Lucide React icons
- **State & Data Fetching:** TanStack Query (React Query v5)
- **PDF Rendering:** PDF.js (`pdfjs-dist`) with client-side canvas rendering and web worker execution
- **Routing:** React Router v6 (Route-level lazy loading with `React.Suspense`)

---

## Quickstart Guide

### 1. Run with Docker Compose (Recommended for Production/Staging)

```bash
docker compose up -d --build
```
- Web Application: `http://localhost:80`
- API Backend: `http://localhost:8000`
- Liveness Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/ready`

### 2. Run Locally for Development

#### Backend Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
python -m app.main --serve --host 127.0.0.1 --port 8000 --reload
```
Swagger UI: `http://127.0.0.1:8000/docs`

#### Frontend App
```bash
cd frontend
npm install
npm run dev
```
Development Server: `http://localhost:5173`

#### Run All Automated Tests
```bash
pytest -v
```

### 3. Developer Guest Mode

To quickly evaluate the platform without registering:
- Click **"Quick Dev Demo Guest Sign-In"** on the Login or Sign Up page.
- This immediately logs you in as `student@docmorph.dev` and directs you to the Dashboard.

---

## REST API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness health probe |
| `GET` | `/ready` | Readiness probe (DB ping & storage write verification) |
| `POST` | `/api/v1/auth/signup` | Register a new user |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT access token |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile |
| `POST` | `/api/v1/documents/upload` | Upload and validate a new PDF document |
| `GET` | `/api/v1/documents` | List user documents (with pagination) |
| `GET` | `/api/v1/documents/{id}` | Get document metadata and status |
| `GET` | `/api/v1/documents/{id}/preview` | Stream original PDF for in-browser viewing |
| `DELETE` | `/api/v1/documents/{id}` | Delete document and associated files |
| `POST` | `/api/v1/documents/{id}/analyze` | Trigger Phase 2 footer detection engine |
| `GET` | `/api/v1/documents/{id}/detection` | Fetch detected fields and occurrences |
| `PATCH` | `/api/v1/documents/{id}/detections/{field_id}` | Manually correct or edit detected field |
| `POST` | `/api/v1/documents/{id}/detections/{field_id}/confirm` | Confirm detected field for replacement |
| `POST` | `/api/v1/documents/{id}/detections/{field_id}/reject` | Reject detected field (exclude from replacement) |
| `POST` | `/api/v1/documents/{id}/personalize` | Execute Phase 3 personalization on confirmed fields |
| `GET` | `/api/v1/jobs/{job_id}` | Retrieve job execution details and verification report |
| `GET` | `/api/v1/documents/{id}/result` | Fetch latest personalized output metadata |
| `GET` | `/api/v1/documents/{id}/download` | Download verified personalized PDF |
| `GET` | `/api/v1/documents/{id}/personalized-preview` | Stream personalized PDF for in-browser preview |
