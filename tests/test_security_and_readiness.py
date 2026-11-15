"""Tests for Phase 5 production readiness, security headers, rate limiting, and storage cleanup."""

from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.server import create_app
from app.storage.cleanup import cleanup_storage_cache
from app.storage.s3 import S3StorageProvider


@pytest.fixture
def test_client():
    app = create_app()
    with TestClient(app) as client:
        yield client


class TestSecurityHeadersAndReadiness:
    """Verifies production HTTP headers, correlation IDs, and probes."""

    def test_health_and_liveness_probe(self, test_client: TestClient):
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app"] == "DocMorph"

    def test_readiness_probe_database_and_storage(self, test_client: TestClient):
        response = test_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"] is True
        assert data["checks"]["storage"] is True

    def test_security_headers_present_on_response(self, test_client: TestClient):
        response = test_client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in response.headers.get("Permissions-Policy", "")

    def test_request_id_assigned_and_propagated(self, test_client: TestClient):
        # 1. Automatic generation
        response = test_client.get("/health")
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None
        assert len(request_id) > 10

        # 2. Propagation of incoming correlation ID
        custom_id = "test-correlation-uuid-12345"
        res2 = test_client.get("/health", headers={"X-Request-ID": custom_id})
        assert res2.headers.get("X-Request-ID") == custom_id


class TestRateLimitingMiddleware:
    """Verifies that rate limiting middleware triggers 429 when threshold exceeded."""

    def test_rate_limiting_triggers_429(self):
        # Temporarily enable rate limiting and set a low limit
        original_enabled = settings.RATE_LIMIT_ENABLED
        original_env = settings.ENVIRONMENT
        original_limit = settings.RATE_LIMIT_AUTH_PER_MINUTE

        try:
            settings.RATE_LIMIT_ENABLED = True
            settings.ENVIRONMENT = "production"
            settings.RATE_LIMIT_AUTH_PER_MINUTE = 3

            app = create_app()
            with TestClient(app) as client:
                # 3 requests should pass
                for _ in range(3):
                    res = client.post("/api/v1/auth/login", json={"email": "none@test.com", "password": "pass"})
                    assert res.status_code in (401, 404, 422)

                # 4th request must be rate limited
                blocked_res = client.post("/api/v1/auth/login", json={"email": "none@test.com", "password": "pass"})
                assert blocked_res.status_code == 429
                assert blocked_res.json()["error"] == "RATE_LIMIT_EXCEEDED"
                assert "Retry-After" in blocked_res.headers
        finally:
            settings.RATE_LIMIT_ENABLED = original_enabled
            settings.ENVIRONMENT = original_env
            settings.RATE_LIMIT_AUTH_PER_MINUTE = original_limit


class TestStorageReliabilityAndCleanup:
    """Verifies S3 storage provider and cache cleanup."""

    @patch("boto3.client")
    def test_s3_storage_provider_operations(self, mock_boto):
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        # Configure head_object return
        mock_s3.head_object.return_value = {"ContentLength": 100}
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"%PDF-1.4 mock content")}

        provider = S3StorageProvider(
            bucket_name="test-bucket",
            endpoint_url="https://r2.cloudflarestorage.com",
            access_key_id="test_key",
            secret_access_key="test_secret",
            region="auto",
        )

        # 1. Save file
        key = provider.save_file(b"%PDF-1.4 content", "assignment.pdf", subdirectory="uploads")
        assert key.endswith(".pdf")
        assert mock_s3.put_object.called

        # 2. Check exists
        assert provider.file_exists(key, subdirectory="uploads") is True

        # 3. Get file bytes
        bytes_out = provider.get_file(key, subdirectory="uploads")
        assert bytes_out == b"%PDF-1.4 mock content"

        # 4. Delete file
        assert provider.delete_file(key, subdirectory="uploads") is True
        assert mock_s3.delete_object.called

    def test_cleanup_storage_cache_runs_safely(self):
        cleaned = cleanup_storage_cache(max_age_hours=0)
        assert isinstance(cleaned, int)
        assert cleaned >= 0

