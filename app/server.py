"""FastAPI ASGI application server for DocMorph.

Configures enterprise security middlewares, request tracing, rate limiting,
CORS policies, health probes, exception handlers, and SPA static hosting.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.session import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown hooks."""
    # 1. Initialize structured logging
    setup_logging(log_level="DEBUG" if settings.DEBUG else "INFO")
    logger.info("Starting %s v%s in '%s' environment", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    # 2. Ensure database tables and dev seed records are initialized
    init_db()
    logger.info("Database schemas verified.")

    yield

    logger.info("Shutting down %s.", settings.APP_NAME)


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI instance."""
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        description="Every document, personalized. Backend REST API for practical manual personalization.",
        lifespan=lifespan,
    )

    # 1. Request ID correlation middleware (outermost)
    app.add_middleware(RequestIdMiddleware)

    # 2. Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Rate limiting middleware
    app.add_middleware(RateLimitMiddleware)

    # 4. CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )

    # 5. Register domain exception handlers
    register_exception_handlers(app)

    # 6. Mount versioned API routes
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # 7. Health & Readiness Probes
    @app.get("/", tags=["Health"])
    def root(request: Request):
        index_file = settings.BASE_DIR / "frontend" / "dist" / "index.html"
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header and index_file.is_file():
            return FileResponse(index_file)

        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "status": "online",
            "docs_url": "/docs",
        }

    @app.get("/health", tags=["Health"])
    def health():
        """Liveness probe: verifies process responsiveness."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.get("/ready", tags=["Health"])
    def readiness():
        """Readiness probe: validates database connectivity and storage volume health."""
        checks = {"database": False, "storage": False}

        # Check database connectivity
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                checks["database"] = True
        except Exception as e:
            logger.error("Readiness check failed on database: %s", str(e))

        # Check storage write access
        try:
            test_file = settings.uploads_dir / ".health_probe"
            test_file.write_text("probe_ok", encoding="utf-8")
            if test_file.read_text(encoding="utf-8") == "probe_ok":
                test_file.unlink(missing_ok=True)
                checks["storage"] = True
        except Exception as e:
            logger.error("Readiness check failed on storage: %s", str(e))

        all_ready = all(checks.values())
        status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_ready else "not_ready",
                "checks": checks,
                "environment": settings.ENVIRONMENT,
            },
        )

    # 8. Single Page Application (SPA) Static Files Hosting (if build exists)
    dist_dir = settings.BASE_DIR / "frontend" / "dist"
    if dist_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        # Mount assets under /assets
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # Do not intercept API, docs, or health routes
            if (
                full_path.startswith("api/")
                or full_path.startswith("docs")
                or full_path.startswith("redoc")
                or full_path == "openapi.json"
            ):
                return Response(status_code=status.HTTP_404_NOT_FOUND)

            candidate_file = dist_dir / full_path
            if candidate_file.is_file():
                return FileResponse(candidate_file)

            # Route nested asset requests (e.g. /workspace/assets/foo.js -> /assets/foo.js)
            if "assets/" in full_path:
                asset_subpath = full_path.split("assets/", 1)[1]
                asset_file = assets_dir / asset_subpath
                if asset_file.is_file():
                    return FileResponse(asset_file)
                return Response(status_code=status.HTTP_404_NOT_FOUND)

            # Never return HTML fallback for missing asset/binary files
            static_exts = (
                ".js", ".css", ".map", ".json", ".png", ".jpg", ".jpeg",
                ".svg", ".ico", ".woff", ".woff2", ".ttf", ".webp",
            )
            if any(full_path.lower().endswith(ext) for ext in static_exts):
                return Response(status_code=status.HTTP_404_NOT_FOUND)

            # Fallback to SPA index.html for client-side routing
            index_file = dist_dir / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)

            return Response(status_code=status.HTTP_404_NOT_FOUND)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
