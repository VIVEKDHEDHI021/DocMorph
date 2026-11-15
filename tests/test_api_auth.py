"""Automated test suite for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAuthAPI:
    """Tests registration, login, and profile retrieval."""

    def test_signup_success(self, client: TestClient) -> None:
        """Verifies creating a new user account succeeds with 201."""
        res = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "newstudent@example.com",
                "password": "SecurePassword123!",
                "full_name": "New Student",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "newstudent@example.com"
        assert data["full_name"] == "New Student"
        assert "id" in data

    def test_signup_duplicate_email_rejected(self, client: TestClient) -> None:
        """Verifies duplicate registration with same email returns 409 conflict."""
        client.post(
            "/api/v1/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "SecurePassword123!",
                "full_name": "Dup Student",
            },
        )
        res = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "AnotherPassword123!",
                "full_name": "Another Name",
            },
        )
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"].lower()

    def test_login_success(self, client: TestClient) -> None:
        """Verifies login returns a valid JWT access token."""
        email = "logintest@example.com"
        password = "LoginPass123!"
        client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "full_name": "Login Tester"},
        )

        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email

    def test_login_invalid_password_rejected(self, client: TestClient) -> None:
        """Verifies incorrect password returns 401 unauthorized."""
        email = "wrongpass@example.com"
        client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": "CorrectPassword123!"},
        )

        res = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert res.status_code == 401
        assert "incorrect email or password" in res.json()["detail"].lower()

    def test_get_current_user_profile(
        self, client: TestClient, user_a_headers: dict[str, str]
    ) -> None:
        """Verifies /auth/me returns the profile of the bearer token owner."""
        res = client.get("/api/v1/auth/me", headers=user_a_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "usera@test.com"
        assert data["full_name"] == "User Alpha"

