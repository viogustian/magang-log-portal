"""Integration tests for SetupWizard API endpoints (/api/setup/*)."""

import urllib.error
from pathlib import Path
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


def test_scan_repos_endpoint(client: TestClient, tmp_path: Path) -> None:
    workspace = tmp_path / "repos"
    workspace.mkdir()
    repo1 = workspace / "frontend_app"
    repo1.mkdir()
    (repo1 / ".git").mkdir()

    repo2 = workspace / "backend_api"
    repo2.mkdir()
    (repo2 / ".git").mkdir()

    response = client.post("/api/setup/scan-repos", json={"root_path": str(workspace)})
    assert response.status_code == 200
    repos = response.json()
    assert len(repos) == 2
    names = {r["name"] for r in repos}
    assert names == {"frontend_app", "backend_api"}
    assert all(r["is_git"] is True for r in repos)


def test_scan_repos_endpoint_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/setup/scan-repos", json={"root_path": "invalid_dir_path_does_not_exist"}
    )
    assert response.status_code == 404


def test_save_config_endpoint_success(
    client: TestClient, tmp_path: Path
) -> None:
    tmp_dir = tmp_path / "config_test"
    tmp_dir.mkdir()
    target_config = tmp_dir / "config.yaml"

    payload = {
        "timezone": "Asia/Makassar",
        "workdays": ["mon", "tue", "wed"],
        "portal": {"headless": False},
        "config_path": str(target_config),
    }

    response = client.post("/api/setup/save", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "saved_at" in data

    assert target_config.exists()
    saved_text = target_config.read_text(encoding="utf-8")
    assert "Asia/Makassar" in saved_text


def test_save_config_endpoint_validation_error(
    client: TestClient, tmp_path: Path
) -> None:
    # Invalid workday "holiday_day" should fail Pydantic validation (422)
    payload = {
        "workdays": ["invalid_day_name"],
        "config_path": str(tmp_path / "never_written.yaml"),
    }
    response = client.post("/api/setup/save", json=payload)
    assert response.status_code == 422


def test_register_scheduler_endpoint_success(client: TestClient) -> None:
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "Installed"
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res):
        response = client.post(
            "/api/setup/register-scheduler",
            json={"trigger_time": "17:30", "task_prefix": "TestTask"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_name"] == "TestTask-Review"


def test_register_scheduler_endpoint_invalid_time(client: TestClient) -> None:
    response = client.post(
        "/api/setup/register-scheduler",
        json={"trigger_time": "25:99"},
    )
    assert response.status_code == 400
    assert "HH:MM" in response.json()["detail"]


def test_register_scheduler_endpoint_failure_500(client: TestClient) -> None:
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = ""
    mock_res.stderr = "Administrative privilege required"

    with patch("subprocess.run", return_value=mock_res):
        response = client.post(
            "/api/setup/register-scheduler",
            json={"trigger_time": "18:00"},
        )
        assert response.status_code == 500
        assert "Administrative privilege required" in response.json()["detail"]
