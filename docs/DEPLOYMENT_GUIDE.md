# DocMorph — Production Deployment Guide

**Product:** DocMorph  
**Tagline:** Every document, personalized.  
**Target Architecture:** Multi-Cloud Cloudflare R2 + PostgreSQL + Containerized FastAPI + Vite Static Hosting

---

## 1. Architecture Overview

```
                      +---------------------------------------+
                      |         Cloudflare Pages CDN          |
                      |  (React 18 + Vite SPA Static Build)   |
                      +-------------------+-------------------+
                                          |
                                          | HTTPS /api/v1/*
                                          v
+-----------------------------------------------------------------------------------+
|                        Containerized Python Runtime                               |
|                     (AWS ECS / Railway / Render / Fly.io)                         |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                 FastAPI ASGI Service (Uvicorn Workers)                      |  |
|  |     - Rate Limiting Middleware                                              |  |
|  |     - Security Headers Middleware (HSTS, CSP, nosniff)                     |  |
|  |     - Request ID Correlation Tracing                                        |  |
|  +-----------------------+-----------------------------+-----------------------+  |
+--------------------------|-----------------------------|--------------------------+
                           |                             |
                           v                             v
           +-------------------------------+  +-------------------------------+
           |    Managed PostgreSQL 16      |  |    Cloudflare R2 Storage      |
           |    (AWS RDS / Supabase)       |  |    (S3-Compatible Object Store|
           |    - Scaled Connection Pool   |  |    - Private Document Bucket  |
           |    - Automated Daily Snapshots|  |    - Zero Egress Bandwidth Fee|
           +-------------------------------+  +-------------------------------+
```

> **CRITICAL ARCHITECTURAL DIRECTIVE:** PyMuPDF (`fitz`) relies on compiled C-extensions. It CANNOT execute inside Cloudflare Workers or serverless V8 isolates. Deploy the backend to a standard Linux container environment (Railway, Render, AWS ECS, Fly.io, or Docker host).

---

## 2. Environment Configuration

Deployments require environment variables defined via your cloud secrets manager or hosting dashboard.

| Variable Name | Required | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| `DOCMORPH_ENVIRONMENT` | **Yes** | `production` | Enables production security invariants |
| `DOCMORPH_DEBUG` | **Yes** | `false` | Disables verbose debug logging and endpoints |
| `DOCMORPH_SECRET_KEY` | **Yes** | `(random 64-character hex)` | Cryptographic key for signing JWT tokens |
| `DOCMORPH_DATABASE_URL` | **Yes** | `postgresql://user:pass@host:5432/docmorph` | Production database connection string |
| `DOCMORPH_STORAGE_BACKEND` | **Yes** | `s3` | Activates remote S3/Cloudflare R2 storage |
| `DOCMORPH_S3_ENDPOINT_URL` | S3 only | `https://<account_id>.r2.cloudflarestorage.com` | Cloudflare R2 S3 API endpoint |
| `DOCMORPH_S3_BUCKET_NAME` | S3 only | `docmorph-documents-prod` | Private document bucket name |
| `DOCMORPH_S3_ACCESS_KEY_ID` | S3 only | `(R2 API Access Token ID)` | Cloudflare R2 Access Key |
| `DOCMORPH_S3_SECRET_ACCESS_KEY` | S3 only | `(R2 Secret Access Key)` | Cloudflare R2 Secret Key |
| `DOCMORPH_S3_REGION` | S3 only | `auto` | Bucket region |
| `DOCMORPH_CORS_ORIGINS` | **Yes** | `["https://docmorph.dev", "https://app.docmorph.dev"]` | Explicit allowed frontend origins |
| `DOCMORPH_DEV_AUTH_MODE` | No | `false` | Prevents test user creation in production |

---

## 3. Database Migration Procedure

Before routing traffic to a new version, apply Alembic database schema migrations:

```bash
# Set production database connection string
export DOCMORPH_DATABASE_URL="postgresql://user:pass@host:5432/docmorph"

# Run migrations to the latest revision
python -m alembic upgrade head

# Verify current revision status
python -m alembic current
```

---

## 4. Docker Deployment

### 4.1 Local Staging with Docker Compose
To run the full stack (PostgreSQL + FastAPI Backend + Nginx Frontend) in an isolated containerized environment:

```bash
docker compose up -d --build
```

- Web UI: `http://localhost:80`
- API Health Check: `http://localhost:8000/health`
- Readiness Check: `http://localhost:8000/ready`

### 4.2 Production Container Build
```bash
# Build backend image
docker build -t docmorph-backend:1.0.0 -f Dockerfile .

# Build frontend image
docker build -t docmorph-frontend:1.0.0 -f frontend/Dockerfile ./frontend
```

---

## 5. Health Probes & Monitoring

Configure your cloud load balancer / ingress orchestrator with the following endpoints:

- **Liveness Probe:** `GET /health` (Returns `200 OK` if the Python application process is healthy)
- **Readiness Probe:** `GET /ready` (Returns `200 OK` only when both PostgreSQL and storage write checks succeed; returns `503 Service Unavailable` if degraded)

---

## 6. Backup & Recovery Strategy

1. **Database Snapshots:**
   - Configure managed automated daily snapshots with point-in-time recovery (PITR) enabled for 14 days.
   - For manual backup: `pg_dump -Fc docmorph > docmorph_backup_$(date +%Y%m%d).dump`
2. **Object Storage Replication:**
   - Enable Cloudflare R2 object versioning to protect against accidental deletions.
   - Retention policy: Automatically purge temporary cache files older than 30 days.

---

## 7. Rollback Strategy

1. **Frontend:** In Cloudflare Pages, rollbacks are instant by switching active deployment target in the Cloudflare dashboard.
2. **Backend:** Re-deploy the previously tagged Docker image tag (e.g. `docmorph-backend:v0.9.8`).
3. **Database Downgrades:** In the rare event of a database rollback:
   ```bash
   python -m alembic downgrade -1
   ```

