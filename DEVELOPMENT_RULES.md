# DOCMORPH — DEVELOPMENT RULES & CODING STANDARDS

**Product:** DocMorph  
**Tagline:** Every document, personalized.  
**Audience:** All engineers, pair programmers, and AI coding agents working on the DocMorph codebase.  

---

## 1. Non-Negotiable Golden Rules

1. **NEVER Mutate Original Source PDFs**
   - Source PDFs uploaded by users are strictly immutable.
   - Pre- and post-processing SHA-256 hashes must always match.
   - Personalized documents are always written to unique destination paths (`output/` or `storage/personalized/`).

2. **Maintain Zero Test Regressions**
   - The test suite contains **138 automated tests** (including Phase 6 anonymous sessions and auto-personalization).
   - Every single test must pass before any branch is merged or any task is marked complete.
   - If a new feature or fix is introduced, you must add corresponding automated tests in `tests/`.

3. **Never Expose Raw Local Filesystem Paths**
   - API endpoints, database records, and frontend responses must use `storage_key` identifiers, never raw server file paths like `C:\Users\...` or `/var/storage/...`.
   - All filesystem I/O must route through the `StorageProvider` abstraction.

4. **Never Bypass Authentication or Permission Checks**
   - Every document endpoint must verify ownership: users may only read, personalize, or download documents they own.

---

## 2. PDF Processing & Geometry Rules

### 1. Coordinate Space & Units
- All coordinates are in PDF user points ($1/72$ inch) with origin $(0, 0)$ at the top-left of the page.
- Bounding boxes are represented as `BoundingBox(x0, y0, x1, y1)`.
- **Do not hardcode coordinates.** Always use layout-aware geometry extracted dynamically from `page.get_text("dict")` or `TextSegmenter`.

### 2. PyMuPDF Base-14 Font Code Mapping
- PyMuPDF requires exact internal font codes for Base-14 standard fonts.
- **Rule:** Never pass `"times"` to PyMuPDF text insertion methods (`page.insert_text()`, `get_text_length()`). It will crash with `ValueError: Font 'times' is unsupported`.
- **Allowed font codes:**
  - Times-Roman: `"tiro"`
  - Times-Bold: `"tibo"`
  - Times-Italic: `"tiit"`
  - Times-BoldItalic: `"tibi"`
  - Helvetica: `"helv"`
  - Helvetica-Bold: `"hebo"`
  - Helvetica-Oblique: `"hebi"`
  - Courier: `"cour"`
  - Courier-Bold: `"cobo"`
- Always route font resolution through `FormattingAnalyzer.map_font_name()`, and wrap text insertions in defensive `try/except` fallbacks.

### 3. Precision Redaction & Vector Preservation
- When purging old text from a page, always call:
  ```python
  page.apply_redactions(images=0, graphics=0, text=0)
  ```
  Setting `images=0` and `graphics=0` is **mandatory** to guarantee that vector line art, diagrams, curves, and borders are completely untouched.

### 4. Text Baseline Origin
- In PDF rendering, text is drawn from its **baseline**, not its top bounding box edge.
- When inserting replacement text, use `Point(line_rect.x0, baseline_y)`.
- Baseline $Y$ is obtained from PyMuPDF span origin metadata (`span["origin"][1]`).

### 5. Identity Pairing vs Labeled Fields
- **Unlabelled Identity Lines:**
  - When student credentials in footers appear as a combined unlabelled pattern (e.g. `Vivekdhedhi(92400120571)` or `Vivek dhedhi (92400120571)`), both occurrences are linked via `pair_id`.
  - At replacement time, **never** replace them as two separate micro-boxes.
  - The engine must redact the entire line bounding box and draw the unified replacement string (`NeelVyas (92400120560)`) in a single draw call.
  - If only one field is replaced, retain the original partner value in the unified string to preserve document typography.
- **Labeled Fields:**
  - Fields with explicit labels (e.g. `Student Name: Rahul Patel`, `Enrollment No: 2300012345`) must NOT be merged into unlabelled unified lines.
  - They must be replaced in-place at their individual `value_bbox` coordinates, keeping explicit labels intact.

---

## 3. Python & Backend Standards

### 1. Strict Pydantic v2 Schemas
- All API inputs, responses, and internal data structures must be modeled as Pydantic v2 classes with explicit field descriptions and validation constraints.
- Avoid passing raw dictionaries across service boundaries.

### 2. Error Taxonomy & Exception Handling
- All domain exceptions must inherit from `DocMorphError` in `app/core/exceptions.py`.
- Common exceptions:
  - `PDFValidationError`: Corrupt or invalid PDF upload.
  - `PDFReplacementError`: Replacement engine failure.
  - `UnconfirmedFieldError`: Attempt to replace an unconfirmed field.
  - `ResourceNotFoundError`: Document or job not found.
  - `AuthorizationError`: Tenant permission violation.
- Never let unhandled 500 exceptions bubble up to users without structured logging and user-safe error messages.

### 3. Database & Sessions
- Always use the `get_db` FastAPI dependency for database sessions.
- Do not commit transactions inside service helper methods; let the API layer or repository control transaction boundaries.

### 4. Structured Logging
- Use the central logger (`app.core.logging.logger`).
- Never log raw passwords, JWT tokens, or client credentials. The `SensitiveDataFilter` will redact sensitive keys, but avoid logging them in the first place.

---

## 4. Frontend & React Standards

1. **TypeScript Strictness:** Strict mode is enabled. Do not use `any` types; define typed interfaces for all props, states, and API responses.
2. **Server State Management:** Use TanStack Query hooks (`useQuery`, `useMutation`). Always invalidate relevant queries on successful mutations.
3. **Responsive Design:** Use mobile-friendly Tailwind CSS utility classes. Test across desktop (1920px), laptop (1366px), and tablet/mobile viewports.
4. **PDF.js Safety:** Always clean up canvas render tasks when unmounting or changing pages to avoid memory leaks.

---

## 5. Android & Capacitor Standards

1. **Principle of Least Privilege:**
   - Declare only necessary Android permissions. Never request `READ_EXTERNAL_STORAGE` or `WRITE_EXTERNAL_STORAGE` when Storage Access Framework (SAF) suffices.
   - Do not request camera, location, contacts, or microphone permissions without explicit architectural approval.
2. **Account-Free & Session Security:**
   - Mobile users do not require credentials. Always use `POST /api/v1/auth/anonymous-session` to retrieve an isolated, cryptographically secure Bearer JWT.
   - Never weaken ownership validation on documents, jobs, or results.
3. **Storage Access Framework (SAF) & Content URIs:**
   - Handle Android content URIs gracefully using `@capawesome/capacitor-file-picker`.
   - Never assume files have normal Unix/Windows filesystem paths on Android. Read byte streams or base64 directly into standard `File`/`Blob` objects.
4. **Keystore & Secret Hygiene:**
   - Never commit signing keys (`*.jks`, `*.keystore`) or passwords to Git.
   - Use environment variables (`DOCMORPH_KEYSTORE_PASSWORD`, `DOCMORPH_KEY_PASSWORD`) in CI/CD.
5. **Mobile Viewport & Hardware Controls:**
   - Handle Android back button via `App.addListener('backButton')` to avoid sudden app exits while reviewing or processing documents.
   - Ensure all touch targets are at least $48 \times 48\,\text{dp}$.

---

## 6. Testing & Verification Checklist

Before committing any changes:

```bash
# 1. Run the entire backend test suite (all 138 tests must pass)
python -m pytest -q

# 2. Build the production React frontend cleanly
npm run frontend:build

# 3. Synchronize Capacitor assets
npx cap sync android

# 4. Verify Android debug & release builds
cd android
.\gradlew.bat assembleDebug
.\gradlew.bat assembleRelease bundleRelease
```

### Windows Process Cleanup Reminder
If the server fails to start with `[WinError 10048]`, check and terminate lingering Python worker processes holding port 8000:
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
python -m app.main --serve --host 127.0.0.1 --port 8000
```

