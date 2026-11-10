"""Integration tests for SetupWizard API endpoints (/api/setup/*)."""

import json
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
        assert response.json() == {"valid": True, "model": "gemini-3.5-flash"}


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


def test_save_config_endpoint_with_gemini_api_key(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    target_config = tmp_path / "config.yaml"
    monkeypatch.setattr("magang_log.server.routers.setup.find_repo_root", lambda: tmp_path)

    payload = {
        "timezone": "Asia/Jakarta",
        "llm": {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "AIzaSySecretApiKey123",
        },
        "config_path": str(target_config),
    }

    response = client.post("/api/setup/save", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert target_config.exists()

    env_file = tmp_path / ".env"
    assert env_file.exists()
    assert "GEMINI_API_KEY=AIzaSySecretApiKey123" in env_file.read_text(encoding="utf-8")


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


def test_get_requirements_scanning_and_payload_structure(client: TestClient) -> None:
    response = client.get("/api/setup/requirements")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    req_names = [item["name"] for item in data]
    assert "Python" in req_names
    assert "Playwright" in req_names

    for item in data:
        assert "name" in item
        assert "min_version" in item
        assert item["status"] in ("ok", "version_mismatch", "missing")
        assert "guidance" in item
        guidance = item["guidance"]
        assert isinstance(guidance, dict)
        assert "download_url" in guidance and guidance["download_url"].startswith("http")
        assert "install_steps" in guidance and isinstance(guidance["install_steps"], list)
        assert "verification_command" in guidance
        assert "expected_output" in guidance
        assert "troubleshooting" in guidance and isinstance(guidance["troubleshooting"], list)


def test_recheck_requirement_endpoint_success(client: TestClient) -> None:
    response = client.post("/api/setup/recheck-requirement", json={"name": "Python"})
    assert response.status_code == 200
    item = response.json()
    assert item["name"] == "Python"
    assert item["status"] == "ok"
    assert item["installed_version"] is not None
    assert item["guidance"]["verification_command"] == "python --version"


def test_recheck_requirement_endpoint_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/setup/recheck-requirement", json={"name": "NonExistentTool123"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_recheck_requirement_mock_mismatch_and_missing(client: TestClient) -> None:
    with patch(
        "magang_log.server.services.setup_service.get_installed_version",
        return_value="3.8.0",
    ):
        response = client.post("/api/setup/recheck-requirement", json={"name": "Python"})
        assert response.status_code == 200
        item = response.json()
        assert item["status"] == "version_mismatch"
        assert item["installed_version"] == "3.8.0"

    with patch(
        "magang_log.server.services.setup_service.get_installed_version",
        return_value=None,
    ):
        response = client.post("/api/setup/recheck-requirement", json={"name": "Python"})
        assert response.status_code == 200
        item = response.json()
        assert item["status"] == "missing"
        assert item["installed_version"] is None


def test_validate_folders_endpoint(client: TestClient, tmp_path: Path) -> None:
    git_dir = tmp_path / "my_project_git"
    git_dir.mkdir()
    (git_dir / ".git").mkdir()

    non_git_dir = tmp_path / "notes_folder"
    non_git_dir.mkdir()

    missing_dir = tmp_path / "does_not_exist"

    payload = {
        "paths": [str(git_dir), str(non_git_dir), str(missing_dir)],
    }
    response = client.post("/api/setup/validate-folders", json=payload)
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 3

    r_git = next(r for r in results if r["path"] == str(git_dir.resolve()))
    assert r_git["exists"] is True
    assert r_git["readable"] is True
    assert r_git["is_git"] is True
    assert r_git["error"] is None

    r_non_git = next(r for r in results if r["path"] == str(non_git_dir.resolve()))
    assert r_non_git["exists"] is True
    assert r_non_git["readable"] is True
    assert r_non_git["is_git"] is False
    assert r_non_git["error"] is None

    r_missing = next(r for r in results if r["path"] == str(missing_dir.resolve()))
    assert r_missing["exists"] is False
    assert r_missing["readable"] is False
    assert r_missing["is_git"] is False
    assert "tidak ditemukan" in r_missing["error"].lower()


def test_wizard_progress_endpoints(client: TestClient, tmp_path: Path) -> None:
    progress_file = tmp_path / "wizard-progress.yaml"

    with patch(
        "magang_log.server.services.setup_service.get_wizard_progress_path",
        return_value=progress_file,
    ):
        # 1. Initial read should return default 0 state
        get_res = client.get("/api/setup/wizard-progress")
        assert get_res.status_code == 200
        state = get_res.json()
        assert state["current_step"] == 0
        assert state["completed_steps"] == []
        assert state["step_data"] == {}

        # 2. Save progress
        save_payload = {
            "current_step": 2,
            "completed_steps": [0, 1],
            "step_data": {
                "folders": [str(tmp_path)],
                "git_intensity": "sering",
            },
        }
        post_res = client.post("/api/setup/save-progress", json=save_payload)
        assert post_res.status_code == 200
        data = post_res.json()
        assert data["success"] is True
        assert "saved_at" in data

        # 3. Read again to confirm persistence
        get_res2 = client.get("/api/setup/wizard-progress")
        assert get_res2.status_code == 200
        state2 = get_res2.json()
        assert state2["current_step"] == 2
        assert state2["completed_steps"] == [0, 1]
        assert state2["step_data"]["git_intensity"] == "sering"


def test_save_config_cleans_up_wizard_progress(
    client: TestClient, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    target_config = config_dir / "config.yaml"
    progress_file = config_dir / "wizard-progress.yaml"
    progress_file.write_text("current_step: 4\n", encoding="utf-8")
    assert progress_file.exists()

    payload = {
        "timezone": "Asia/Jakarta",
        "config_path": str(target_config),
    }

    with patch(
        "magang_log.server.services.setup_service.get_wizard_progress_path",
        return_value=progress_file,
    ):
        response = client.post("/api/setup/save", json=payload)
        assert response.status_code == 200
        assert target_config.exists()
        # wizard-progress.yaml should be removed after final save
        assert not progress_file.exists()


def test_get_config_endpoint(client: TestClient) -> None:
    response = client.get("/api/setup/config")
    assert response.status_code == 200
    data = response.json()

    assert "timezone" in data
    assert "workdays" in data
    assert "portal" in data
    assert "review" in data
    assert "llm" in data
    assert "sources" in data
    assert "notify" in data
    assert "retention_days" in data


def test_get_scheduler_status_registered(client: TestClient) -> None:
    mock_status = {
        "status": "registered",
        "is_registered": True,
        "review_task_name": "MagangLog-Review",
        "resume_task_name": "MagangLog-Resume",
        "review_time": "16:30",
        "resume_time": "20:00",
        "diagnostic_message": "Tugas otomatis aktif terdaftar di Windows Task Scheduler.",
    }
    with patch(
        "magang_log.server.routers.setup.inspect_scheduler_status",
        return_value=mock_status,
    ):
        response = client.get("/api/setup/scheduler-status?task_prefix=MagangLog")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "registered"
        assert data["is_registered"] is True
        assert data["review_time"] == "16:30"
        assert data["resume_time"] == "20:00"


def test_get_scheduler_status_unregistered(client: TestClient) -> None:
    mock_status = {
        "status": "unregistered",
        "is_registered": False,
        "review_task_name": "MagangLog-Review",
        "resume_task_name": "MagangLog-Resume",
        "review_time": None,
        "resume_time": None,
        "diagnostic_message": "Tugas terjadwal belum terdaftar di Windows Task Scheduler.",
    }
    with patch(
        "magang_log.server.routers.setup.inspect_scheduler_status",
        return_value=mock_status,
    ):
        response = client.get("/api/setup/scheduler-status?task_prefix=MagangLog")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unregistered"
        assert data["is_registered"] is False


def test_unregister_scheduler_endpoint(client: TestClient) -> None:
    with patch(
        "magang_log.server.routers.setup.unregister_task_scheduler",
        return_value={"success": True, "message": "Tugas berhasil dihapus."},
    ):
        response = client.post(
            "/api/setup/unregister-scheduler",
            json={"task_prefix": "MagangLog"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "berhasil" in data["message"].lower()


def test_register_scheduler_dual_times_and_validation(client: TestClient) -> None:
    with patch(
        "magang_log.server.routers.setup.register_task_scheduler",
        return_value={
            "success": True,
            "task_name": "MagangLog-Review",
            "review_time": "16:30",
            "resume_time": "20:00",
        },
    ):
        # 1. Valid dual times
        valid_payload = {
            "review_time": "16:30",
            "resume_time": "20:00",
            "task_prefix": "MagangLog",
            "active_days": ["mon", "tue", "wed", "thu", "fri"],
        }
        res = client.post("/api/setup/register-scheduler", json=valid_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["review_time"] == "16:30"
        assert data["resume_time"] == "20:00"

        # 2. Legacy payload (trigger_time only)
        legacy_payload = {
            "trigger_time": "17:15",
            "task_prefix": "MagangLog",
        }
        res_legacy = client.post("/api/setup/register-scheduler", json=legacy_payload)
        assert res_legacy.status_code == 200

    # 3. Invalid time format should fail with 400 or 422
    invalid_payload = {
        "review_time": "26:99",
        "resume_time": "20:00",
    }
    res_invalid = client.post("/api/setup/register-scheduler", json=invalid_payload)
    assert res_invalid.status_code in (400, 422)


def test_get_gemini_models_fallback_without_key(client: TestClient) -> None:
    res = client.get("/api/setup/gemini-models")
    assert res.status_code == 200
    data = res.json()
    assert "models" in data
    assert len(data["models"]) > 0
    assert any(m["id"] == "gemini-3.5-flash" for m in data["models"])
    assert data["source"] in ("fallback_offline", "fallback_error", "google_api")


def test_get_gemini_models_with_mocked_google_api(client: TestClient) -> None:
    mock_google_response = {
        "models": [
            {
                "name": "models/gemini-3.5-flash",
                "displayName": "Gemini 3.5 Flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3.8-flash",
                "displayName": "Gemini 3.8 Flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash (Deprecated)",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3.5-flash-tts",
                "displayName": "Gemini TTS",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_google_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        res = client.get("/api/setup/gemini-models?api_key=mock-key")
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "google_api"
        model_ids = [m["id"] for m in data["models"]]
        # gemini-3.5-flash and gemini-3.8-flash must be included
        assert "gemini-3.5-flash" in model_ids
        assert "gemini-3.8-flash" in model_ids
        # deprecated models and tts models must be excluded
        assert "gemini-2.5-flash" not in model_ids
        assert "gemini-3.5-flash-tts" not in model_ids
        rec_model = next(m for m in data["models"] if m["id"] == "gemini-3.5-flash")
        assert rec_model["is_recommended"] is True


def test_delete_gemini_key_endpoint(client: TestClient) -> None:
    res = client.post("/api/setup/delete-gemini-key")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "message" in data


