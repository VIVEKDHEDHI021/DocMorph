# DOCMORPH — ANDROID CONVERSION AUDIT & FEASIBILITY REPORT

**Product:** DocMorph  
**Tagline:** Every document, personalized.  
**Target Platform:** Android (Capacitor 8 / Android SDK 34-36)  
**Date:** 2026-11-11  
**Audit Status:** Complete & Verified  

---

## 1. Executive Summary & Verification

A comprehensive audit of the DocMorph codebase was conducted across the FastAPI backend, PyMuPDF PDF processing engine, AI detection model, and React TypeScript frontend.

- **Backend Status:** Fully implemented, operational, and robust. All 133 automated backend unit/integration tests pass with 100% pass rate (`pytest`).
- **Frontend Status:** Built with React 18, Vite 5, Tailwind CSS, TanStack Query v5, PDF.js v3. Production build succeeds cleanly (`tsc && vite build`).
- **Device & Native Toolchain:** Host machine running Windows with OpenJDK 17.0.20, Android SDK Build-Tools 35.0.0 & 36.0.0, Platforms 34/35/36, and an active connected Android device (`Samsung SM-X510`, API Level 36).
- **Primary Transition Objective:** Package the existing responsive React frontend into a native Android app via Capacitor, establish native file-picking and document-saving capabilities, securely isolate anonymous student processing sessions, integrate client-side profile persistence, and communicate with the FastAPI backend over HTTPS/HTTP without requiring Google/password logins.

---

## 2. Existing Repository Architecture Audit

### 2.1 React Frontend
- **Framework & Runtime:** React 18.3.1, TypeScript 5.4.5, Vite 5.2.13.
- **Styling:** Tailwind CSS 3.4.4, Lucide React icons (`lucide-react`).
- **Build Output:** Configured to compile to `frontend/dist/`. Code-splitting splits vendor chunks (`vendor-react`, `vendor-pdfjs`, `vendor-query`, `vendor-icons`).
- **Routing:** `react-router-dom` v6.23.1. Routes:
  - `/` — `LandingPage` (marketing, hero, comparison visualizer, how-it-works, FAQ)
  - `/login` — `LoginPage` (email/password auth for web users)
  - `/signup` — `SignupPage` (account creation for web users)
  - `/dashboard` — `DashboardPage` (recent personalized practical documents, upload dropzone, status badges)
  - `/workspace/:documentId` — `WorkspacePage` (5-stage interactive studio: PDF viewer, AI detections, replacement controls, verification report, download)
- **State Management:** `@tanstack/react-query` v5 for remote server queries and mutations; local React state (`useState`, `useContext`) for UI state and modal management.
- **Client-Side PDF Preview:** `pdfjs-dist` v3.11.174 rendering canvas pages in `PdfViewer.tsx`.
- **API Services:** `frontend/src/services/api.ts` wrapping Fetch API with JWT bearer tokens from storage.

### 2.2 FastAPI Backend Architecture
- **Framework:** FastAPI 0.111+ (ASGI) mounted in `app/server.py` and instantiated via `create_app()`.
- **Database:** SQLAlchemy 2.0 ORM with SQLite (`docmorph.db`) default for development, Postgres-compatible. Alembic migrations initialized.
- **Middlewares Active:**
  - `RequestIdMiddleware` (`X-Request-ID` correlation tracing).
  - `SecurityHeadersMiddleware` (X-Content-Type-Options, Frame-Options, HSTS).
  - `RateLimitMiddleware` (auth: 15/min, upload: 30/min, general API: 180/min).
  - `CORSMiddleware` (configurable origins, exposes Content-Disposition & X-Request-ID).
- **Core Processing Engines:**
  1. `app/utils/file_validator.py`: PDF magic-bytes (`%PDF-`), file size limits (20MB default), null-byte & path traversal sanitization, encryption detection.
  2. `app/services/pdf_analyzer.py`: Leak-free PyMuPDF context manager, text extraction, page geometry.
  3. `app/services/detection_engine.py`: Hybrid regex + layout-aware unlabelled footer detector + Universal AI layout classifier (`ai_training/trained_model/layout_classifier.joblib`).
  4. `app/services/unlabelled_identity_detector.py`: Detects `Name (ID)` patterns in bottom-left footer quadrant, pairing line geometry (`pair_id`, `line_bbox`).
  5. `app/services/cross_page_analyzer.py`: Multi-page structural consistency, conflict detection, separate bounding box enforcement, and page number exclusion.
  6. `app/services/pdf_replacer.py`: Vector-preserving localized text purging with PyMuPDF redaction annotations (`apply_redactions(images=0, graphics=0, text=0)`), unified identity single-span redaction/insertion, Base-14 font fallback (`"tiro"`, `"helv"`).
  7. `app/services/output_verifier.py`: Independent post-generation verification of page counts, replacement text existence, and purged value absence.

---

## 3. Detailed Backend API Verification

| Endpoint | HTTP Method | Request Schema | Response Schema | Auth / Session | Error Responses | Max Size / Timeout | Operational Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/auth/signup` | `POST` | `UserCreate` (email, password, full_name) | `UserResponse` (id, email, full_name) | None | 400, 409 Conflict | Standard JSON | Verified (operational) |
| `/api/v1/auth/login` | `POST` | `UserLogin` (email, password) | `Token` (access_token, token_type, user) | None | 400, 401 Unauthorized | Standard JSON | Verified (operational) |
| `/api/v1/auth/me` | `GET` | None | `UserResponse` | Bearer JWT (or DEV fallback) | 401 Unauthorized | Standard JSON | Verified (operational) |
| `/api/v1/documents/upload` | `POST` | `multipart/form-data` (`file: UploadFile`) | `DocumentUploadResponse` | Bearer JWT (enforces user_id) | 400, 413, 422 | 20 MB max file limit | Verified (operational) |
| `/api/v1/documents` | `GET` | Query params: `page`, `page_size` | `DocumentListResponse` (items, total) | Bearer JWT | 401 Unauthorized | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}` | `GET` | Path: `document_id` | `DocumentDetailResponse` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/preview` | `GET` | Path: `document_id` | Raw stream `application/pdf` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Response stream | Verified (operational) |
| `/api/v1/documents/{id}` | `DELETE` | Path: `document_id` | 204 No Content | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/analyze` | `POST` | Path: `document_id` | `DocumentDetectionResponse` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | ~10-30s depending on pages | Verified (operational) |
| `/api/v1/documents/{id}/detection` | `GET` | Path: `document_id` | `DocumentDetectionResponse` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/detections/{field_id}` | `PATCH` | `DetectionReviewAction` | `DetectionFieldDTO` | Bearer JWT (checks owner) | 401, 404 FieldNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/detections/{field_id}/confirm` | `POST` | Path params | `DetectionFieldDTO` | Bearer JWT (checks owner) | 401, 404 FieldNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/detections/{field_id}/reject` | `POST` | Path params | `DetectionFieldDTO` | Bearer JWT (checks owner) | 401, 404 FieldNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/personalize` | `POST` | `PersonalizeRequest` (`replacements`) | `JobDetailResponse` | Bearer JWT (checks owner + review status) | 400 UnconfirmedField, 404 | ~5-15s replacement & verify | Verified (operational) |
| `/api/v1/jobs/{job_id}` | `GET` | Path: `job_id` | `JobDetailResponse` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/result` | `GET` | Path: `document_id` | `JobDetailResponse` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Standard JSON | Verified (operational) |
| `/api/v1/documents/{id}/download` | `GET` | Path: `document_id` | Raw stream `attachment; filename=...` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Response stream | Verified (operational) |
| `/api/v1/documents/{id}/personalized-preview` | `GET` | Path: `document_id` | Raw stream `inline; filename=...` | Bearer JWT (checks owner) | 401, 404 PDFNotFoundError | Response stream | Verified (operational) |

---

## 4. Gap Analysis & Missing Functionality Identified

### 4.1 Anonymous Session Lifecycle
- **Current State:** Backend supports registration/login via `/api/v1/auth/signup` and `/api/v1/auth/login`, plus a development fallback when `DEV_AUTH_MODE=True`.
- **Requirement:** Android application must be account-free (no email/password registration or login screen for Android users), yet all documents and jobs must remain securely isolated per device/workspace.
- **Solution:** Add `/api/v1/auth/anonymous-session` endpoint. On first Android launch, the client requests an anonymous session. The backend issues a standard JWT token tied to an isolated anonymous user record (`anon_<uuid>`). The token is stored securely in native Android storage. Subsequent uploads and personalization operations automatically validate document ownership against this anonymous session ID.

### 4.2 One-Time Student Profile & Profile Matching Engine
- **Current State:** `app/schemas/profile_data.py` and `app/services/profile_matcher.py` were designed but empty on disk (bytecode recovered during audit).
- **Requirement:** User enters their Full Name and Enrollment Number once. On document upload and detection, the backend compares detected values with the student profile:
  - If identical $\rightarrow$ marks `already_matching` (no replacement needed).
  - If different with high confidence $\rightarrow$ plans automatic replacement with student's profile value.
  - If ambiguous or conflicting $\rightarrow$ flags for manual review.
- **Solution:** Implement `profile_data.py`, `profile_matcher.py`, and endpoint `/api/v1/documents/{id}/match-profile` and `/api/v1/documents/{id}/auto-personalize`. Implement client-side profile setup and editing dialogs (`ProfileSetupModal.tsx`, `ProfileSettingsModal.tsx`, and `profileStorage.ts`).

### 4.3 Native Android Document Picker
- **Current State:** Web uses `<input type="file" accept=".pdf">` and drag-and-drop.
- **Requirement:** Native Android document picker supporting content URIs from system storage and cloud document providers (Google Drive, Files, Downloads), validating size and PDF MIME type without unbounded memory overhead.
- **Solution:** Integrate `@capawesome/capacitor-file-picker` or `@capacitor/filesystem` with fallback to standard web picker, properly reading file blobs/streams into multipart upload.

### 4.4 Native Android PDF Download, Open, and Share
- **Current State:** Web uses browser download link `<a download="..." href="/documents/{id}/download">`.
- **Requirement:**
  - Download to Android Downloads directory with verified write.
  - Open PDF via Android View Intent (e.g. Acrobat Reader, Google PDF Viewer, Samsung Notes).
  - Share PDF via native Android Share Sheet (`@capacitor/share`).
- **Solution:** Use `@capacitor/filesystem` (Directory.Documents / Directory.Downloads) + `@capacitor/share` + `@capawesome-team/capacitor-file-opener` (or equivalent native intent opener).

### 4.5 Capacitor 8 / Android Toolchain Configuration
- **Current State:** Repository is purely web + backend. No `capacitor.config.ts` or `android/` directory yet.
- **Requirement:** Capacitor 8 initialization, Android project generation, package identifier `com.docmorph.app`, adaptive icons, splash screen, status bar configuration, build scripts for debug and release APK/AAB.

---

## 5. Backend Compatibility & Network Configuration

1. **CORS Origins:**
   - In Capacitor Android, web assets are served from `http://localhost`, `capacitor://localhost`, or `https://localhost`.
   - Update `app/core/config.py` `CORS_ORIGINS` to include `http://localhost`, `https://localhost`, and `capacitor://localhost`.
2. **Cleartext Traffic / Network Security Config:**
   - For local development with backend at `http://10.0.2.2:8000` (Android emulator) or local LAN IP (e.g., `http://192.168.x.x:8000`), Android requires `network_security_config.xml` permitting cleartext traffic to the development server or local loopback. Production uses HTTPS.
3. **Environment-Based API URL:**
   - Frontend Vite configuration must support `VITE_API_URL`. When running in native Android mode, the API client targets the configured backend URL (e.g. `http://10.0.2.2:8000` or production host) instead of relative `/api/v1`.

---

## 6. Known Risks & Mitigations

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| Large PDF memory footprint in WebView | App crash / Out-of-memory | Limit uploads to 20MB, stream bytes in chunks where feasible, release PDF.js canvas references upon page unmount. |
| Android back button exits app unexpectedly | Poor UX | Implement Capacitor `App.addListener('backButton')` to handle navigation stack and modal dismissals gracefully. |
| Content URI permission expiration | File read failure | Read selected file stream into memory or cache immediately upon selection from document picker. |
| Missing external PDF viewer on device | "Unable to open" error | Fall back to embedded PDF.js preview with clear toast notice and provide native Share Sheet option. |
| Anonymous token loss on app data clear | Student profile and document history reset | Document behavior in guide; allow effortless profile recreation on launch without requiring server recovery. |

---

## 7. Gate-by-Gate Implementation Plan

- **Gate A (Completed):** Audit repository, verify backend operational status, document gaps and feasibility report (`docs/ANDROID_CONVERSION_AUDIT.md`).
- **Gate B — Capacitor Foundation:**
  - Install Capacitor 8 dependencies (`@capacitor/core`, `@capacitor/cli`, `@capacitor/android`).
  - Configure `capacitor.config.ts` with app ID `com.docmorph.app`, app name `DocMorph`, webDir `frontend/dist`.
  - Generate Android project (`npx cap add android`).
  - Update `frontend/package.json` scripts (`build:android`, `cap:sync`, `cap:open`).
  - Configure Android `network_security_config.xml` and manifest permissions.
- **Gate C — Native Integration & Account-Free Profile:**
  - Implement `frontend/src/services/profileStorage.ts` (storage abstraction with native/IndexedDB support).
  - Implement `ProfileSetupModal.tsx` and `ProfileSettingsModal.tsx`.
  - Install `@capacitor/share`, `@capacitor/filesystem`, `@capacitor/status-bar`, and file-opening capabilities.
  - Implement native file picker integration in upload dropzone.
  - Implement native download, open, and share actions in `WorkspacePage.tsx`.
- **Gate D — Backend Integration & Anonymous Sessions:**
  - Implement `POST /api/v1/auth/anonymous-session` on FastAPI backend.
  - Implement `app/schemas/profile_data.py` and `app/services/profile_matcher.py`.
  - Add `/api/v1/documents/{id}/match-profile` and `/api/v1/documents/{id}/auto-personalize` routes.
  - Add backend tests for anonymous sessions and profile auto-matching (`tests/test_profile_and_auto_personalization.py`).
  - Verify all 133+ backend tests pass.
- **Gate E — Complete Workflow Validation:**
  - Test end-to-end flow: First launch $\rightarrow$ Profile setup $\rightarrow$ Dashboard $\rightarrow$ Native PDF pick $\rightarrow$ Upload $\rightarrow$ AI detection $\rightarrow$ Profile match $\rightarrow$ Personalize $\rightarrow$ Verification $\rightarrow$ Preview $\rightarrow$ Download $\rightarrow$ Open $\rightarrow$ Share.
- **Gate F — Release Readiness & Packaging:**
  - Configure release signing, build debug APK, build signed release APK and AAB.
  - Test on connected Samsung Android device (`SM-X510`).
  - Update all project documentation (`PROJECT_MEMORY.md`, `DEVELOPMENT_LOG.md`, `docs/ANDROID_BUILD_GUIDE.md`, `docs/ANDROID_ARCHITECTURE.md`, `docs/ANDROID_RELEASE_GUIDE.md`, `docs/ANDROID_TESTING.md`).

