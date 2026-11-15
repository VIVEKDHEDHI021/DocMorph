"""Request ID tracing middleware for DocMorph.

Assigns or propagates a unique correlation ID (X-Request-ID) across all incoming HTTP requests
for distributed tracing and structured log aggregation.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propagates or assigns a unique correlation request identifier."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check incoming header or generate new UUID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Bind to request state for downstream handlers and logging
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

