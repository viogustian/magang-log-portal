"""Integration tests untuk otomasi penjadwalan Windows Task Scheduler dan diagnostik doctor."""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magang_log.doctor import CheckStatus, SchedulerCheck

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install_task.ps1"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Task Scheduler hanya berlaku di OS Windows")
def test_install_and_uninstall_lifecycle_with_isolated_prefix() -> None:
    """Menguji siklus hidup registrasi dan deregistrasi Task Scheduler menggunakan prefix terisolasi."""
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin:
        pytest.skip("PowerShell tidak ditemukan di sistem.")

    # Gunakan prefix acak unik agar tidak menabrak tugas produksi
    random_id = uuid.uuid4().hex[:6]
    test_prefix = f"MagangLogTest_{random_id}"

    try:
        # 1. Jalankan -Install
        res_install = subprocess.run(
            [
                ps_bin,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-Install",
                "-TaskPrefix",
                test_prefix,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        assert res_install.returncode == 0, f"Install gagal: {res_install.stderr}"
        assert f"Tugas '{test_prefix}-Review' berhasil didaftarkan" in res_install.stdout
        assert f"Tugas '{test_prefix}-Resume' berhasil didaftarkan" in res_install.stdout

        # 2. Periksa status via -Status
        res_status = subprocess.run(
            [
                ps_bin,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-Status",
                "-TaskPrefix",
                test_prefix,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert res_status.returncode == 0
        assert f"{test_prefix}-Review" in res_status.stdout
        assert f"{test_prefix}-Resume" in res_status.stdout
        assert "Ready" in res_status.stdout or "terdaftar aktif" in res_status.stdout

        # 3. Verifikasi SchedulerCheck pada doctor subsystem mendeteksi tugas ini
        check = SchedulerCheck(task_name=f"{test_prefix}-Review")
        res_check = check.check()
        assert res_check.status == CheckStatus.PASS
        assert f"{test_prefix}-Review" in res_check.message

    finally:
        # 4. Bersihkan: Jalankan -Uninstall
        res_uninstall = subprocess.run(
            [
                ps_bin,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-Uninstall",
                "-TaskPrefix",
                test_prefix,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert res_uninstall.returncode == 0
        assert "Penghapusan selesai" in res_uninstall.stdout


def test_scheduler_check_unit_scenarios() -> None:
    """Menguji skenario unit SchedulerCheck: registered, not registered, non-windows, missing binary."""
    # 1. Platform non-windows
    with patch("sys.platform", "linux"):
        res_non_win = SchedulerCheck().check()
        assert res_non_win.status == CheckStatus.WARN
        assert "Bukan platform Windows" in res_non_win.message

    # 2. Binary schtasks tidak ada
    with patch("sys.platform", "win32"), patch("shutil.which", return_value=None):
        res_no_bin = SchedulerCheck().check()
        assert res_no_bin.status == CheckStatus.WARN
        assert "tidak ditemukan" in res_no_bin.message

    # 3. Tugas terdaftar (schtasks exit code 0)
    with patch("sys.platform", "win32"), patch("shutil.which", return_value="C:\\Windows\\System32\\schtasks.exe"):
        mock_proc_ok = MagicMock()
        mock_proc_ok.returncode = 0
        with patch("subprocess.run", return_value=mock_proc_ok):
            res_pass = SchedulerCheck().check()
            assert res_pass.status == CheckStatus.PASS
            assert "terdaftar aktif" in res_pass.message

    # 4. Tugas tidak terdaftar (schtasks exit code 1) -> rekomendasi ke install_task.ps1
    with patch("sys.platform", "win32"), patch("shutil.which", return_value="C:\\Windows\\System32\\schtasks.exe"):
        mock_proc_missing = MagicMock()
        mock_proc_missing.returncode = 1
        with patch("subprocess.run", return_value=mock_proc_missing):
            res_warn = SchedulerCheck().check()
            assert res_warn.status == CheckStatus.WARN
            assert "belum terdaftar" in res_warn.message
            assert "install_task.ps1" in res_warn.remediation
