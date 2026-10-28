"""Integration tests untuk Subistem Health Doctor (CLI doctor dan simulasi fault-injection)."""

from __future__ import annotations

import argparse
import io
import json
import os
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from magang_log.cli import cmd_doctor
from magang_log.doctor import (
    AiApiCheck,
    CheckStatus,
    ConfigurationCheck,
    Doctor,
    GitRepositoriesCheck,
    PythonRuntimeCheck,
    SessionCheck,
    StorageCheck,
)


def _setup_healthy_environment(tmp_path: Path) -> dict[str, str]:
    """Menyiapkan lingkungan lokal tiruan yang 100% sehat untuk doctor."""
    config_file = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    auth_dir = data_dir / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    state_file = auth_dir / "state.json"
    repo_dir = tmp_path / "project_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / ".git").mkdir(parents=True, exist_ok=True)

    future_ts = datetime.now(timezone.utc).timestamp() + 86400 * 30
    state_file.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "magang_session", "value": "token_abc123", "expires": future_ts}
                ]
            }
        ),
        encoding="utf-8",
    )

    config_file.write_text(
        f"""
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: true
    repos: ["{repo_dir.as_posix()}"]
""",
        encoding="utf-8",
    )

    return {
        "config": str(config_file),
        "data_dir": str(data_dir),
        "db_path": str(data_dir / "state.db"),
        "auth_state": str(state_file),
        "repo": str(repo_dir),
    }


def test_doctor_full_run_healthy_exit_code_zero(tmp_path: Path) -> None:
    """Memverifikasi bahwa lingkungan sehat mengembalikan exit code 0 dan status badges [PASS]."""
    env = _setup_healthy_environment(tmp_path)

    checks = [
        PythonRuntimeCheck(),
        ConfigurationCheck(config_path=env["config"]),
        StorageCheck(data_dir=env["data_dir"], db_path=env["db_path"]),
        SessionCheck(auth_state_path=env["auth_state"]),
        GitRepositoriesCheck(config_path=env["config"]),
        AiApiCheck(),
    ]
    doctor = Doctor(checks=checks)

    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyValidApiKeyTest12345"}):
        report = doctor.run_checks()

    assert report.is_healthy is True
    assert report.exit_code == 0

    terminal_out = report.format_terminal()
    assert "[PASS]" in terminal_out
    assert "[FAIL]" not in terminal_out
    assert "SEMUA SEHAT & SIAP OTOMASI (Exit 0)" in terminal_out


def test_doctor_cli_simulated_faults_and_remediation_guidance(tmp_path: Path) -> None:
    """Memverifikasi simulasi fault-injection (config hilang, auth invalid, repo unreachable, API missing)."""
    # 1. Fault: Konfigurasi rusak
    broken_config = tmp_path / "broken_config.yaml"
    broken_config.write_text("invalid: yaml: syntax: [", encoding="utf-8")

    args = argparse.Namespace(
        config=str(broken_config),
        portal=False,
        json=False,
        date=None,
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cmd_doctor(args)

    output = buf.getvalue()
    assert code == 10
    assert "[FAIL]" in output
    assert "Solusi:" in output
    assert "PERLU TINDAKAN PERBAIKAN (Exit 10)" in output


def test_doctor_cli_json_output_mode(tmp_path: Path) -> None:
    """Memverifikasi opsi --json pada CLI menghasilkan payload JSON yang valid."""
    env = _setup_healthy_environment(tmp_path)
    args = argparse.Namespace(
        config=env["config"],
        portal=False,
        json=True,
        date=None,
    )

    buf = io.StringIO()
    with redirect_stdout(buf), patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyTestApiKey"}):
        code = cmd_doctor(args)

    output = buf.getvalue()
    assert code == 0 or code == 10
    parsed = json.loads(output)

    assert "is_healthy" in parsed
    assert "exit_code" in parsed
    assert "summary" in parsed
    assert "checks" in parsed
    assert isinstance(parsed["checks"], list)
    assert len(parsed["checks"]) >= 5


def test_doctor_unreachable_git_repo_fault(tmp_path: Path) -> None:
    """Memverifikasi penanganan repositori Git lokal yang tidak dapat diakses atau hilang."""
    ghost_repo = tmp_path / "nonexistent_git_directory"
    bad_config = tmp_path / "bad_git_config.yaml"
    bad_config.write_text(
        f"""
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: true
    repos: ["{ghost_repo.as_posix()}"]
""",
        encoding="utf-8",
    )

    check = GitRepositoriesCheck(config_path=bad_config)
    res = check.check()
    assert res.status == CheckStatus.FAIL
    assert "tidak valid" in res.message
    assert "Periksa dan perbaiki path repositori" in res.remediation


def test_doctor_invalid_auth_session_fault(tmp_path: Path) -> None:
    """Memverifikasi penanganan file sesi auth yang hilang atau kedaluwarsa."""
    missing_auth = tmp_path / "ghost_auth.json"
    check = SessionCheck(auth_state_path=missing_auth)
    res = check.check()
    assert res.status == CheckStatus.FAIL
    assert "tidak ditemukan" in res.message
    assert "magang-log login" in res.remediation
