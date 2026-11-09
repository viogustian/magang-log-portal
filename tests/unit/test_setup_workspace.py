"""Unit tests for repository scanning, configuration persistence, and scheduler registration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magang_log.server.services.setup_service import (
    register_task_scheduler,
    save_app_configuration,
    scan_workspace_repos,
)
from magang_log.settings import AppConfig


def test_scan_workspace_repos_valid(tmp_path: Path) -> None:
    repo_a = tmp_path / "project_a"
    repo_a.mkdir()
    (repo_a / ".git").mkdir()

    repo_b = tmp_path / "project_b"
    repo_b.mkdir()
    (repo_b / ".git").mkdir()

    non_repo = tmp_path / "docs"
    non_repo.mkdir()

    results = scan_workspace_repos(str(tmp_path))
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"project_a", "project_b"}
    for r in results:
        assert r["is_git"] is True


def test_scan_workspace_repos_invalid_path() -> None:
    with pytest.raises(FileNotFoundError):
        scan_workspace_repos("nonexistent_path_xyz_123")


def test_save_app_configuration_atomic(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    cfg = AppConfig()
    cfg.timezone = "Asia/Jayapura"

    res = save_app_configuration(cfg, target_path=config_file)
    assert res["success"] is True
    assert "saved_at" in res
    assert config_file.exists()
    content = config_file.read_text(encoding="utf-8")
    assert "Asia/Jayapura" in content


def test_register_task_scheduler_success() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "Tugas 'MagangLog-Review' berhasil didaftarkan"
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res) as mock_run:
        result = register_task_scheduler(trigger_time="17:00", task_prefix="MagangLog")
        assert result["success"] is True
        assert result["task_name"] == "MagangLog-Review"
        mock_run.assert_called_once()


def test_register_task_scheduler_failure() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = ""
    mock_res.stderr = "Access is denied"

    with patch("subprocess.run", return_value=mock_res):
        with pytest.raises(RuntimeError, match="Access is denied"):
            register_task_scheduler(trigger_time="17:00", task_prefix="MagangLog")


def test_register_task_scheduler_invalid_time_format() -> None:
    with pytest.raises(ValueError, match="HH:MM"):
        register_task_scheduler(trigger_time="invalid-time")
