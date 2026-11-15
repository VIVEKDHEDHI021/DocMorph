# ==============================================================================
# DocMorph Backend Dockerfile
# Production-ready multi-stage Python 3.12 container
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /build

# Install compilation dependencies for PyMuPDF and bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Image
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies required by PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create non-root user for least privilege security
RUN useradd -m -u 1000 -U docmorph && \
    mkdir -p /app/storage/uploads /app/storage/personalized && \
    chown -R docmorph:docmorph /app

COPY --chown=docmorph:docmorph . .

USER docmorph

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    DOCMORPH_ENVIRONMENT=production

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

