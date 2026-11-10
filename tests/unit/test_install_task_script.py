"""Unit test untuk skrip PowerShell otomasi Windows Task Scheduler (scripts/install_task.ps1)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install_task.ps1"


def test_install_task_script_file_exists() -> None:
    assert SCRIPT_PATH.exists(), f"File skrip {SCRIPT_PATH} tidak ditemukan."
    assert SCRIPT_PATH.is_file()


def test_install_task_script_powershell_syntax() -> None:
    """Memverifikasi sintaksis PowerShell valid menggunakan PowerShell AST parser resmi jika tersedia."""
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin or sys.platform != "win32":
        pytest.skip("PowerShell tidak tersedia di lingkungan pengujian.")

    # Gunakan AST Parser internal PowerShell untuk memverifikasi file tanpa menjalankannya
    parse_cmd = (
        f"$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT_PATH.as_posix()}', [ref]$null, [ref]$errors); "
        f"if ($errors.Count -eq 0) {{ exit 0 }} else {{ $errors | ForEach-Object {{ Write-Error $_ }}; exit 1 }}"
    )
    res = subprocess.run(
        [ps_bin, "-NoProfile", "-NonInteractive", "-Command", parse_cmd],
        capture_output=True,
        text=True,
        check=False,
    )

    assert res.returncode == 0, f"Sintaksis PowerShell error: {res.stderr or res.stdout}"


def test_install_task_script_parameters_and_configuration() -> None:
    """Memverifikasi bahwa skrip mendefinisikan parameter dan pengaturan wajib sesuai PRD / Issue 05."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    # 1. Parameter yang wajib didukung
    assert "[switch]$Install" in content
    assert "[switch]$Uninstall" in content
    assert "[switch]$Status" in content

    # 2. Dual triggers harian: 16:30 dan 20:00
    assert '16:30' in content
    assert '20:00' in content
    assert re.search(r"magang-log\s+run\s+--mode\s+review", content), "Perintah --mode review harus ada."
    assert re.search(r"magang-log\s+run\s+--resume", content), "Perintah --resume harus ada."

    # 3. Pengaturan tangguh Task Scheduler
    assert "-StartWhenAvailable" in content
    assert "-AllowStartIfOnBatteries" in content
    assert "-DontStopIfGoingOnBatteries" in content
    assert re.search(r"-ExecutionTimeLimit\s+\(New-TimeSpan\s+-Minutes\s+10\)", content)

    # 4. Akun pengguna tanpa kredensial tersimpan
    assert "$env:USERNAME" in content
    assert "-LogonType Interactive" in content

    # 5. Non-interactive & log output ke data/logs/
    assert "-WindowStyle Hidden" in content
    assert "-NonInteractive" in content
    assert "data/logs" in content
    assert "task_review.log" in content
    assert "task_resume.log" in content
    assert "exit `$LASTEXITCODE" in content or "LASTEXITCODE" in content


def test_install_task_script_status_execution() -> None:
    """Memverifikasi eksekusi flag -Status mengembalikan kode keluar 0 dan informasi jadwal."""
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin or sys.platform != "win32":
        pytest.skip("PowerShell tidak tersedia di lingkungan pengujian.")

    res = subprocess.run(
        [ps_bin, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT_PATH), "-Status"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert res.returncode == 0
    assert "STATUS PENJADWALAN OTOMASI MAGANG-LOG" in res.stdout
    assert "16:30" in res.stdout
    assert "20:00" in res.stdout
    assert "magang-log run --mode review" in res.stdout
    assert "magang-log run --resume" in res.stdout


def test_install_task_script_custom_task_prefix() -> None:
    """Memverifikasi bahwa parameter -TaskPrefix dihormati pada -Status."""
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin or sys.platform != "win32":
        pytest.skip("PowerShell tidak tersedia di lingkungan pengujian.")

    res = subprocess.run(
        [
            ps_bin,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT_PATH),
            "-TaskPrefix",
            "CustomPrefixTest",
            "-Status",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert res.returncode == 0
    assert "CustomPrefixTest-Review" in res.stdout
    assert "CustomPrefixTest-Resume" in res.stdout
