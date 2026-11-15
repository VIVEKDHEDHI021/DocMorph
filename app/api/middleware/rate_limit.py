"""In-memory sliding window rate limiting middleware for DocMorph.

Protects critical API endpoints (authentication, PDF uploads, and personalization execution)
against brute-force attacks and volumetric denial-of-service without requiring external broker infrastructure.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window per-client IP rate limiter."""

    def __init__(self, app, cleanup_interval_seconds: int = 300) -> None:
        super().__init__(app)
        # Dictionary mapping: f"{client_ip}:{category}" -> list of float timestamps
        self.request_records: dict[str, list[float]] = defaultdict(list)
        self.cleanup_interval = cleanup_interval_seconds
        self.last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """Determines client IP respecting reverse-proxy forwarded headers."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First IP in the list is the client IP
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _cleanup_expired(self, now: float) -> None:
        """Periodically purges timestamps older than 60 seconds to prevent memory bloat."""
        if now - self.last_cleanup > self.cleanup_interval:
            cutoff = now - 60.0
            expired_keys = []
            for key, timestamps in self.request_records.items():
                self.request_records[key] = [t for t in timestamps if t > cutoff]
                if not self.request_records[key]:
                    expired_keys.append(key)
            for k in expired_keys:
                self.request_records.pop(k, None)
            self.last_cleanup = now

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bypass rate limiting if disabled or during automated testing
        if not settings.RATE_LIMIT_ENABLED or settings.ENVIRONMENT.lower() == "testing":
            return await call_next(request)

        now = time.time()
        self._cleanup_expired(now)

        path = request.url.path
        client_ip = self._get_client_ip(request)

        # Categorize request path and determine limit
        if "/auth/" in path:
            limit = settings.RATE_LIMIT_AUTH_PER_MINUTE
            category = "auth"
        elif "/documents/upload" in path:
            limit = settings.RATE_LIMIT_UPLOAD_PER_MINUTE
            category = "upload"
        elif path.startswith(settings.API_V1_PREFIX):
            limit = settings.RATE_LIMIT_API_PER_MINUTE
            category = "api"
        else:
            # Static files, root, health checks are not limited
            return await call_next(request)

        key = f"{client_ip}:{category}"
        cutoff = now - 60.0

        # Filter timestamps to the current 60s sliding window
        window_timestamps = [t for t in self.request_records[key] if t > cutoff]
        self.request_records[key] = window_timestamps

        if len(window_timestamps) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "detail": f"Too many requests. Limit is {limit} requests per minute for this endpoint.",
                    "status_code": 429,
                },
                headers={"Retry-After": "60"},
            )

        # Record this request
        self.request_records[key].append(now)
        return await call_next(request)

