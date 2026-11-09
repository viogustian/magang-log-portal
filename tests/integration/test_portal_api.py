"""Integration tests for Portal Authentication endpoints (/api/portal/*)."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from magang_log.server.app import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_auth_status_missing(client: TestClient, tmp_path: Path) -> None:
    fake_state = tmp_path / "nonexistent.json"
    with patch("magang_log.server.services.portal_service.get_auth_state_path", return_value=fake_state):
        response = client.get("/api/portal/auth-status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["session_status"] == "missing"
        assert data["expires_at"] is None
        assert data["username"] is None


def test_get_auth_status_valid(client: TestClient, tmp_path: Path) -> None:
    fake_state = tmp_path / "valid.json"
    future_time = time.time() + 3600 * 24 * 7
    data = {
        "cookies": [
            {"name": "session_id", "value": "abc123token", "expires": future_time},
            {"name": "user_email", "value": "peserta@kemnaker.go.id", "expires": future_time},
        ],
        "origins": [],
    }
    fake_state.write_text(json.dumps(data), encoding="utf-8")

    with patch("magang_log.server.services.portal_service.get_auth_state_path", return_value=fake_state):
        response = client.get("/api/portal/auth-status")
        assert response.status_code == 200
        res = response.json()
        assert res["authenticated"] is True
        assert res["session_status"] == "active"
        assert res["expires_at"] is not None
        assert res["username"] == "peserta@kemnaker.go.id"


def test_post_open_login_success(client: TestClient) -> None:
    with patch(
        "magang_log.server.services.portal_service.PortalAuthService.launch_interactive_login",
        return_value=(True, "Login berhasil, sesi autentikasi tersimpan."),
    ) as mock_launch:
        response = client.post("/api/portal/open-login", json={"timeout_seconds": 60})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["authenticated"] is True
        assert "Login berhasil" in data["message"]
        mock_launch.assert_called_once_with(timeout_seconds=60)


def test_post_open_login_concurrent_guard(client: TestClient) -> None:
    from magang_log.server.services.portal_service import get_portal_auth_service

    service = get_portal_auth_service()
    with service.acquire_login():
        # While login is locked, calling endpoint should return HTTP 409
        response = client.post("/api/portal/open-login", json={"timeout_seconds": 60})
        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]
