"""Integration tests for SetupWizard API endpoints (/api/setup/*)."""

import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from magang_log.server.app import create_app
from magang_log.workprofile import ApplicationConfig, WorkProfile


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_presets_returns_bundled_roles(client: TestClient) -> None:
    response = client.get("/api/setup/presets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    names = [item["profile_name"] for item in data]
    assert "Software Engineer" in names
    assert "UI/UX Designer" in names

    first = data[0]
    assert "profile_name" in first
    assert "natural_description" in first
    assert "applications" in first
    assert "browser_domains" in first
    assert "watch_folders" in first


def test_test_gemini_empty_key_fails(client: TestClient) -> None:
    response = client.post("/api/setup/test-gemini", json={"api_key": ""})
    assert response.status_code == 400
    assert "API key" in response.json()["detail"]


def test_test_gemini_valid_key(client: TestClient) -> None:
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        response = client.post("/api/setup/test-gemini", json={"api_key": "valid-api-key"})
        assert response.status_code == 200
        assert response.json() == {"valid": True, "model": "gemini-2.5-flash"}


def test_test_gemini_invalid_key_http_400(client: TestClient) -> None:
    err = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com",
        code=400,
        msg="Bad Request",
        hdrs={},  # type: ignore[arg-type]
        fp=MagicMock(read=lambda: b'{"error": {"message": "API key not valid"}}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        response = client.post("/api/setup/test-gemini", json={"api_key": "invalid-key"})
        assert response.status_code == 400
        assert "API key not valid" in response.json()["detail"]


def test_test_gemini_network_failure_http_502(client: TestClient) -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("Network unreachable")):
        response = client.post("/api/setup/test-gemini", json={"api_key": "any-key"})
        assert response.status_code == 502
        assert "Network unreachable" in response.json()["detail"]


def test_predict_profile_gemini_success(client: TestClient) -> None:
    mock_profile = WorkProfile(
        profile_name="DevOps Engineer",
        natural_description="Managing Kubernetes clusters and CI/CD pipelines.",
        applications=[
            ApplicationConfig(
                name="Docker Desktop",
                process_names=["Docker Desktop.exe"],
                file_extensions=[".yaml", ".yml"],
            )
        ],
        browser_domains=["github.com", "hub.docker.com"],
    )

    with patch(
        "magang_log.server.services.setup_service.call_gemini_for_profile",
        return_value=mock_profile,
    ):
        response = client.post(
            "/api/setup/predict-profile",
            json={
                "description": "Mengelola deployment cluster kubernetes dan docker container",
                "api_key": "valid-key",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "gemini"
        assert data["profile"]["profile_name"] == "DevOps Engineer"
        assert len(data["profile"]["applications"]) == 1


def test_predict_profile_fallback_to_preset(client: TestClient) -> None:
    response = client.post(
        "/api/setup/predict-profile",
        json={
            "description": "Membuat antarmuka visual prototipe dan wireframe di Figma",
            "api_key": None,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "preset_fallback"
    assert data["profile"]["profile_name"] == "UI/UX Designer"
