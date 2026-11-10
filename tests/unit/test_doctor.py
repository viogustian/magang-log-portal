"""Unit tests untuk Subistem Health Doctor (HealthCheck protocol, checks, dan report)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from magang_log.doctor import (
    AiApiCheck,
    CanaryPortalHealthCheck,
    CheckResult,
    CheckStatus,
    ConfigurationCheck,
    Doctor,
    GitRepositoriesCheck,
    HealthCheck,
    PythonRuntimeCheck,
    SchedulerCheck,
    SessionCheck,
    StorageCheck,
)


def test_health_check_protocol_conformance() -> None:
    """Memverifikasi seluruh implementasi check mematuhi protokol HealthCheck."""
    checks = [
        PythonRuntimeCheck(),
        ConfigurationCheck(),
        StorageCheck(),
        SessionCheck(),
        SchedulerCheck(),
        GitRepositoriesCheck(),
        AiApiCheck(),
        CanaryPortalHealthCheck(),
    ]
    for c in checks:
        assert isinstance(c, HealthCheck)


def test_python_runtime_check() -> None:
    """Memverifikasi evaluasi runtime Python."""
    # Skenario 1: Versi memenuhi syarat (mis. min_version <= versi saat ini)
    check_ok = PythonRuntimeCheck(min_version=(3, 10))
    res_ok = check_ok.check()
    assert res_ok.status == CheckStatus.PASS
    assert "memenuhi syarat" in res_ok.message

    # Skenario 2: Versi di bawah syarat (mis. min_version 3.99)
    check_fail = PythonRuntimeCheck(min_version=(3, 99))
    res_fail = check_fail.check()
    assert res_fail.status == CheckStatus.FAIL
    assert "di bawah syarat minimal" in res_fail.message
    assert "Perbarui interpreter Python" in res_fail.remediation


def test_configuration_check_valid_and_invalid(tmp_path: Path) -> None:
    """Memverifikasi ConfigurationCheck pada file valid, rusak, atau hilang."""
    # Skenario 1: File konfigurasi tidak ditemukan
    missing_config = tmp_path / "nonexistent.yaml"
    res_missing = ConfigurationCheck(config_path=missing_config).check()
    assert res_missing.status == CheckStatus.FAIL
    assert "tidak ditemukan" in res_missing.message
    assert res_missing.remediation

    # Skenario 2: File konfigurasi valid
    valid_yaml = tmp_path / "valid.yaml"
    valid_yaml.write_text(
        """
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: true
    repos: []
""",
        encoding="utf-8",
    )
    res_valid = ConfigurationCheck(config_path=valid_yaml).check()
    assert res_valid.status == CheckStatus.PASS
    assert "valid" in res_valid.message

    # Skenario 3: File memuat kunci terlarang/tidak dikenal (skema ketat)
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text(
        """
timezone: Asia/Jakarta
kunci_rahasia_palsu: 12345
""",
        encoding="utf-8",
    )
    res_invalid = ConfigurationCheck(config_path=invalid_yaml).check()
    assert res_invalid.status == CheckStatus.FAIL
    assert res_invalid.remediation


def test_storage_check_read_write_and_db(tmp_path: Path) -> None:
    """Memverifikasi StorageCheck menguji izin tulis data/ dan konektivitas SQLite."""
    data_dir = tmp_path / "data"
    db_path = data_dir / "state.db"

    # Skenario sukses
    check = StorageCheck(data_dir=data_dir, db_path=db_path)
    res = check.check()
    assert res.status == CheckStatus.PASS
    assert data_dir.exists()
    assert "dapat diakses baca-tulis" in res.message

    # Skenario gagal: mock sqlite3.connect melempar OperationalError
    with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("Database disk image is malformed")):
        res_fail = check.check()
        assert res_fail.status == CheckStatus.FAIL
        assert "Gagal mengakses database" in res_fail.message
        assert res_fail.remediation


def test_session_check_scenarios(tmp_path: Path) -> None:
    """Memverifikasi SessionCheck pada sesi hilang, kosong, kedaluwarsa, dan valid."""
    auth_file = tmp_path / "state.json"

    # Skenario 1: File hilang
    res_missing = SessionCheck(auth_state_path=auth_file).check()
    assert res_missing.status == CheckStatus.FAIL
    assert "tidak ditemukan" in res_missing.message
    assert "magang-log login" in res_missing.remediation

    # Skenario 2: File JSON rusak / tanpa cookies
    auth_file.write_text("{}", encoding="utf-8")
    res_empty = SessionCheck(auth_state_path=auth_file).check()
    assert res_empty.status == CheckStatus.FAIL
    assert "cookies" in res_empty.message

    # Skenario 3: Cookie telah kedaluwarsa (expires masa lalu)
    expired_data = {
        "cookies": [
            {"name": "session_id", "value": "xyz", "expires": 1000000.0}
        ]
    }
    auth_file.write_text(json.dumps(expired_data), encoding="utf-8")
    res_expired = SessionCheck(auth_state_path=auth_file).check()
    assert res_expired.status == CheckStatus.FAIL
    assert "kedaluwarsa" in res_expired.message

    # Skenario 4: Cookie valid (expires masa depan)
    future_ts = datetime.now(timezone.utc).timestamp() + 86400 * 30
    valid_data = {
        "cookies": [
            {"name": "session_id", "value": "xyz", "expires": future_ts}
        ]
    }
    auth_file.write_text(json.dumps(valid_data), encoding="utf-8")
    res_valid = SessionCheck(auth_state_path=auth_file).check()
    assert res_valid.status == CheckStatus.PASS
    assert "valid" in res_valid.message


def test_scheduler_check(tmp_path: Path) -> None:
    """Memverifikasi SchedulerCheck."""
    # Skenario platform non-Windows
    with patch("sys.platform", "linux"):
        check = SchedulerCheck()
        res = check.check()
        assert res.status == CheckStatus.WARN
        assert "Bukan platform Windows" in res.message

    # Skenario schtasks sukses (returncode 0)
    with patch("sys.platform", "win32"), patch("shutil.which", return_value="C:\\Windows\\schtasks.exe"):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            res_win_ok = SchedulerCheck(task_name="MagangLogTask").check()
            assert res_win_ok.status == CheckStatus.PASS
            assert "terdaftar" in res_win_ok.message

        # Skenario schtasks belum terdaftar (returncode 1)
        mock_proc.returncode = 1
        with patch("subprocess.run", return_value=mock_proc):
            res_win_warn = SchedulerCheck(task_name="MagangLogTask").check()
            assert res_win_warn.status == CheckStatus.WARN
            assert "belum terdaftar" in res_win_warn.message
            assert "magang-log schedule register" in res_win_warn.remediation


def test_git_repositories_check(tmp_path: Path) -> None:
    """Memverifikasi GitRepositoriesCheck pada repositori valid dan invalid."""
    # Buat repo git tiruan
    repo1 = tmp_path / "my_project"
    repo1.mkdir()
    (repo1 / ".git").mkdir()

    # Skenario repositori valid
    check = GitRepositoriesCheck(repos=[repo1])
    res = check.check()
    assert res.status == CheckStatus.PASS
    assert "1 repositori Git terverifikasi" in res.message

    # Skenario repositori tidak ditemukan
    missing_repo = tmp_path / "ghost_repo"
    check_bad = GitRepositoriesCheck(repos=[repo1, missing_repo])
    res_bad = check_bad.check()
    assert res_bad.status == CheckStatus.FAIL
    assert "tidak valid" in res_bad.message
    assert res_bad.remediation


def test_ai_api_check() -> None:
    """Memverifikasi AiApiCheck mendeteksi atau melaporkan ketiadaan GEMINI_API_KEY."""
    # Skenario variabel tidak ada
    with patch.dict(os.environ, {}, clear=True):
        res_missing = AiApiCheck(env_var="GEMINI_API_KEY").check()
        assert res_missing.status == CheckStatus.FAIL
        assert "tidak ditemukan" in res_missing.message
        assert res_missing.remediation

    # Skenario variabel ada
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSySecretToken12345"}):
        res_ok = AiApiCheck(env_var="GEMINI_API_KEY").check()
        assert res_ok.status == CheckStatus.PASS
        assert "terdeteksi" in res_ok.message
        assert "AIzaSySecretToken12345" not in res_ok.message  # Nilai harus disamarkan (masked)


def test_doctor_report_aggregation_and_exit_codes() -> None:
    """Memverifikasi agregasi DoctorReport dan perhitungan exit code 0 vs 10."""
    pass_check = MagicMock()
    pass_check.check.return_value = CheckResult(
        name="Check 1", status=CheckStatus.PASS, message="OK"
    )

    warn_check = MagicMock()
    warn_check.check.return_value = CheckResult(
        name="Check 2", status=CheckStatus.WARN, message="Warning", remediation="Fix it"
    )

    fail_check = MagicMock()
    fail_check.check.return_value = CheckResult(
        name="Check 3", status=CheckStatus.FAIL, message="Error", remediation="Fix now"
    )

    # Skenario Semua PASS + WARN -> exit code 0
    doctor_ok = Doctor(checks=[pass_check, warn_check])
    rep_ok = doctor_ok.run_checks()
    assert rep_ok.is_healthy is True
    assert rep_ok.exit_code == 0
    assert "[PASS]" in rep_ok.format_terminal()
    assert "[WARN]" in rep_ok.format_terminal()

    # Skenario Terdapat FAIL -> exit code 10
    doctor_fail = Doctor(checks=[pass_check, warn_check, fail_check])
    rep_fail = doctor_fail.run_checks()
    assert rep_fail.is_healthy is False
    assert rep_fail.exit_code == 10
    assert "[FAIL]" in rep_fail.format_terminal()
    assert "PERLU TINDAKAN" in rep_fail.format_terminal()

    # Uji struktur to_dict() untuk output JSON
    d = rep_fail.to_dict()
    assert d["is_healthy"] is False
    assert d["exit_code"] == 10
    assert d["summary"]["failed"] == 1
    assert len(d["checks"]) == 3
