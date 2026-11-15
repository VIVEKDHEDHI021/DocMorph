# DocMorph — Security Audit Report

**Date:** 2026-11-01  
**Category:** Application Security, Auth, File Safety & API Hardening  
**Status:** Hardened & Verified

---

## 1. Authentication & Authorization Security

1. **Password Hashing:**
   - Implemented via direct `bcrypt` (`bcrypt.hashpw` and `bcrypt.checkpw`) using standard work factor salts.
   - Mitigated the 72-byte password length truncation vulnerability by explicitly enforcing UTF-8 slicing to 72 bytes.
2. **Stateless JWT Authorization:**
   - Tokens signed with HMAC-SHA256 (`HS256`).
   - Standard 7-day expiration with ISO-8601 timestamps.
   - Sensitive credentials (passwords, hashes) are never embedded inside JWT payloads.
3. **Multi-Tenant Ownership Boundary:**
   - Every protected API endpoint verifies `document.user_id == current_user.id` or `job.user_id == current_user.id`.
   - Access attempts to foreign documents return `404 Not Found` rather than `403 Forbidden` to prevent object identifier enumeration (IDOR mitigation).
4. **Dev Auth Mode Protection:**
   - Development guest mode (`student@docmorph.dev`) is strictly gated behind `settings.DEV_AUTH_MODE`.
   - In production (`ENVIRONMENT == "production"`), `DEV_AUTH_MODE` is forced to `False`.

---

## 2. File Security & Validation

1. **PDF Header & Magic Signature Verification:**
   - Every uploaded document must begin with the `%PDF-` signature. Plain text files, binaries, or executables disguised with a `.pdf` extension are rejected immediately with `400 Bad Request`.
2. **Password & Encryption Rejection:**
   - Encrypted or password-protected PDFs are rejected before any memory parsing (`PDFEncryptedError`).
3. **Path Traversal & Storage Isolation:**
   - User-supplied filenames are sanitized to strip directory separators, dots, and shell meta-characters.
   - Internal storage keys are generated using random UUIDs: `{uuid4().hex}_{safe_stem}.pdf`.
   - `LocalStorageProvider._resolve_file_path()` enforces `file_path.is_relative_to(target_dir)`, raising a security violation if any traversal sequence (`../../`) is supplied.
4. **Non-Public Storage:**
   - Neither `storage/uploads/` nor `storage/personalized/` is mounted as public static directory.
   - All file reads require authenticated HTTP GET streaming endpoints with active JWT Bearer verification.

---

## 3. API Security & Transport Defense

1. **Defensive HTTP Security Headers (`SecurityHeadersMiddleware`):**
   - `X-Content-Type-Options: nosniff` (Prevents MIME confusion attacks)
   - `X-Frame-Options: DENY` (Mitigates clickjacking in iframes)
   - `X-XSS-Protection: 1; mode=block`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` (In production / HTTPS)
2. **Distributed Request Tracing (`RequestIdMiddleware`):**
   - Every request is tagged with an `X-Request-ID` correlation identifier for audit logging.
3. **Adaptive Rate Limiting (`RateLimitMiddleware`):**
   - In-memory sliding-window limiter categorized by route risk profile:
     - Authentication routes (`/api/v1/auth/*`): 15 requests / minute
     - Document upload (`/api/v1/documents/upload`): 30 requests / minute
     - General API routes: 180 requests / minute
   - Returns `429 Too Many Requests` with `Retry-After: 60`.
4. **CORS Hardening:**
   - Wildcard `"*"` is purged in production. Explicit trusted origins are enforced.
5. **Safe Error Handling:**
   - Domain exceptions map to clean JSON error models with domain codes (`PDF_VALIDATION_ERROR`, `UNCONFIRMED_FIELD_ERROR`).
   - Internal database tracebacks and filesystem paths are never exposed to clients.

---

## 4. Secrets Management & Configuration Safety

1. **Validation on Startup:**
   - If `ENVIRONMENT == "production"`, `Settings` verifies that `DOCMORPH_SECRET_KEY` is not the development default and has at least 32 characters. If invalid, the service refuses to boot.
2. **Repository Cleanliness:**
   - `.gitignore` explicitly excludes `.env`, `*.db`, `storage/uploads/*`, `storage/personalized/*`, and `frontend/dist/`.
   - No credentials or API keys are committed in source code.
3. **Log Sanitization (`SensitiveDataFilter`):**
   - Logs automatically redact passwords, Bearer tokens, and secrets via regex filters before emitting log records.

