"""Subistem Health Doctor (magang-log doctor) untuk audit lingkungan runtime."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .settings import ConfigurationError, load_config

logger = logging.getLogger(__name__)


class CheckStatus(StrEnum):
    """Status hasil evaluasi pemeriksaan kesehatan."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    """Hasil pemeriksaan kesehatan individual."""

    name: str
    status: CheckStatus
    message: str
    remediation: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class HealthCheck(Protocol):
    """Protokol pemeriksaan kesehatan mandiri."""

    def check(self) -> CheckResult:
        """Menjalankan evaluasi kesehatan dan mengembalikan CheckResult."""
        ...


class PythonRuntimeCheck:
    """Memeriksa versi runtime Python (mensyaratkan Python >= 3.12)."""

    def __init__(self, min_version: tuple[int, int] = (3, 12)) -> None:
        self.min_version = min_version

    def check(self) -> CheckResult:
        current_version = sys.version_info[:2]
        version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        min_str = f"{self.min_version[0]}.{self.min_version[1]}"

        if current_version < self.min_version:
            return CheckResult(
                name="Python Runtime",
                status=CheckStatus.FAIL,
                message=f"Versi Python saat ini ({version_str}) di bawah syarat minimal (>= {min_str}).",
                remediation=f"Perbarui interpreter Python Anda ke versi >= {min_str}.",
                details={"version": version_str, "min_required": min_str},
            )

        return CheckResult(
            name="Python Runtime",
            status=CheckStatus.PASS,
            message=f"Python {version_str} memenuhi syarat (>= {min_str}).",
            details={"version": version_str, "executable": sys.executable},
        )


class ConfigurationCheck:
    """Memvalidasi sintaks dan skema konfigurasi YAML serta mendeteksi kunci tak dikenal/usang."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = config_path

    def check(self) -> CheckResult:
        try:
            cfg = load_config(self.config_path)
            return CheckResult(
                name="Konfigurasi Sistem",
                status=CheckStatus.PASS,
                message="File konfigurasi YAML valid dan sesuai skema ketat.",
                details={"timezone": cfg.timezone, "workdays": cfg.workdays},
            )
        except ConfigurationError as exc:
            return CheckResult(
                name="Konfigurasi Sistem",
                status=CheckStatus.FAIL,
                message=f"Kesalahan konfigurasi: {exc}",
                remediation="Periksa dan perbaiki file config/config.yaml sesuai template config.example.yaml.",
                details={"error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Konfigurasi Sistem",
                status=CheckStatus.FAIL,
                message=f"Gagal memuat konfigurasi: {exc}",
                remediation="Pastikan file konfigurasi ada dan memiliki sintaks YAML yang benar.",
                details={"error": str(exc)},
            )


class StorageCheck:
    """Menguji hak akses baca-tulis direktori data/ dan konektivitas ledger SQLite."""

    def __init__(
        self,
        data_dir: str | Path = "data",
        db_path: str | Path = "data/state.db",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)

    def check(self) -> CheckResult:
        # 1. Uji akses baca-tulis pada direktori data
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.data_dir / f".doctor_write_test_{os.getpid()}"
            test_file.write_text("ok", encoding="utf-8")
            content = test_file.read_text(encoding="utf-8")
            test_file.unlink()
            if content != "ok":
                raise OSError("Konten uji tulis direktori data tidak sesuai.")
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Penyimpanan Data",
                status=CheckStatus.FAIL,
                message=f"Direktori data/ ({self.data_dir}) tidak dapat ditulisi: {exc}",
                remediation=f"Pastikan direktori {self.data_dir} memiliki izin baca dan tulis untuk pengguna saat ini.",
                details={"data_dir": str(self.data_dir), "error": str(exc)},
            )

        # 2. Uji koneksi database SQLite
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS _doctor_probe (id INTEGER PRIMARY KEY, ts TEXT)")
            cur.execute("INSERT INTO _doctor_probe (ts) VALUES (datetime('now'))")
            conn.commit()
            cur.execute("DROP TABLE _doctor_probe")
            conn.commit()
            conn.close()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Penyimpanan Data",
                status=CheckStatus.FAIL,
                message=f"Gagal mengakses database SQLite ({self.db_path}): {exc}",
                remediation="Periksa apakah database terkunci oleh proses lain atau file korup.",
                details={"db_path": str(self.db_path), "error": str(exc)},
            )

        return CheckResult(
            name="Penyimpanan Data",
            status=CheckStatus.PASS,
            message="Direktori data/ dan database SQLite dapat diakses baca-tulis.",
            details={"data_dir": str(self.data_dir), "db_path": str(self.db_path)},
        )


class SessionCheck:
    """Memverifikasi keberadaan, keterbacaan, dan usia kedaluwarsa sesi autentikasi portal."""

    def __init__(
        self,
        auth_state_path: str | Path = "data/auth/state.json",
        max_age_days: int = 14,
    ) -> None:
        self.auth_state_path = Path(auth_state_path)
        self.max_age_days = max_age_days

    def check(self) -> CheckResult:
        if not self.auth_state_path.exists():
            return CheckResult(
                name="Sesi Autentikasi Portal",
                status=CheckStatus.FAIL,
                message=f"File autentikasi portal tidak ditemukan di {self.auth_state_path}.",
                remediation="Jalankan 'magang-log login' untuk mengotentikasi sesi MagangHub.",
                details={"path": str(self.auth_state_path)},
            )

        try:
            raw = self.auth_state_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict) or "cookies" not in data:
                return CheckResult(
                    name="Sesi Autentikasi Portal",
                    status=CheckStatus.FAIL,
                    message="Struktur file state.json tidak valid (tanpa kunci 'cookies').",
                    remediation="Jalankan 'magang-log login' untuk membuat sesi baru yang valid.",
                    details={"path": str(self.auth_state_path)},
                )

            cookies = data.get("cookies", [])
            if not cookies:
                return CheckResult(
                    name="Sesi Autentikasi Portal",
                    status=CheckStatus.FAIL,
                    message="File state.json kosong atau tidak memuat cookie autentikasi.",
                    remediation="Jalankan 'magang-log login' untuk membuat sesi baru.",
                    details={"cookies_count": 0},
                )

            # Periksa tanggal kedaluwarsa cookie bila ada
            now_ts = datetime.now(timezone.utc).timestamp()
            expired_cookies = []
            for c in cookies:
                exp = c.get("expires", -1)
                if exp > 0 and exp < now_ts:
                    expired_cookies.append(c.get("name", "unknown"))

            if expired_cookies:
                return CheckResult(
                    name="Sesi Autentikasi Portal",
                    status=CheckStatus.FAIL,
                    message=f"Terdapat {len(expired_cookies)} cookie sesi yang telah kedaluwarsa.",
                    remediation="Jalankan 'magang-log login' untuk memperbarui sesi portal.",
                    details={"expired_cookies": expired_cookies},
                )

            # Periksa usia file
            stat = self.auth_state_path.stat()
            age_days = (datetime.now().timestamp() - stat.st_mtime) / (24 * 3600)
            if age_days > self.max_age_days:
                return CheckResult(
                    name="Sesi Autentikasi Portal",
                    status=CheckStatus.WARN,
                    message=f"File sesi telah berusia {int(age_days)} hari (mendekati batas kedaluwarsa).",
                    remediation="Pertimbangkan menjalankan 'magang-log login' untuk memperbarui sesi.",
                    details={"age_days": round(age_days, 1)},
                )

            return CheckResult(
                name="Sesi Autentikasi Portal",
                status=CheckStatus.PASS,
                message=f"Sesi portal valid ({len(cookies)} cookies tersimpan).",
                details={"cookies_count": len(cookies), "age_days": round(age_days, 1)},
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Sesi Autentikasi Portal",
                status=CheckStatus.FAIL,
                message=f"Gagal membaca sesi autentikasi: {exc}",
                remediation="Jalankan 'magang-log login' untuk membuat file state.json baru.",
                details={"error": str(exc)},
            )


class SchedulerCheck:
    """Memverifikasi registrasi jadwal tugas pada Windows Task Scheduler."""

    def __init__(self, task_name: str | list[str] = "MagangLog-Review") -> None:
        if isinstance(task_name, str):
            self.task_name = task_name
            if task_name in ("MagangLog-Review", "MagangLogSubmission"):
                self.task_names = ["MagangLog-Review", "MagangLog-Resume", "MagangLogSubmission"]
            else:
                self.task_names = [task_name]
        else:
            self.task_names = list(task_name)
            self.task_name = self.task_names[0] if self.task_names else "MagangLog-Review"

    def check(self) -> CheckResult:
        if sys.platform != "win32":
            return CheckResult(
                name="Windows Task Scheduler",
                status=CheckStatus.WARN,
                message="Bukan platform Windows; Windows Task Scheduler tidak berlaku.",
                remediation="Gunakan cron atau systemd timer jika berjalan di lingkungan Linux/macOS.",
                details={"platform": sys.platform},
            )

        schtasks_bin = shutil.which("schtasks")
        if not schtasks_bin:
            return CheckResult(
                name="Windows Task Scheduler",
                status=CheckStatus.WARN,
                message="Perintah 'schtasks' tidak ditemukan di sistem PATH.",
                remediation="Pastikan Windows System32 berada di environment variable PATH.",
            )

        registered: list[str] = []
        try:
            for tn in self.task_names:
                res = subprocess.run(
                    ["schtasks", "/query", "/tn", tn, "/fo", "CSV"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    registered.append(tn)

            if registered:
                return CheckResult(
                    name="Windows Task Scheduler",
                    status=CheckStatus.PASS,
                    message=f"Tugas '{', '.join(registered)}' terdaftar aktif di Windows Task Scheduler.",
                    details={"task_names": registered},
                )
            return CheckResult(
                name="Windows Task Scheduler",
                status=CheckStatus.WARN,
                message=f"Tugas '{self.task_name}' belum terdaftar di Windows Task Scheduler.",
                remediation="Daftarkan jadwal tugas otomatis dengan perintah 'magang-log schedule register' atau jalankan 'powershell -File scripts/install_task.ps1 -Install'.",
                details={"task_names": self.task_names},
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Windows Task Scheduler",
                status=CheckStatus.WARN,
                message=f"Gagal memeriksa Task Scheduler: {exc}",
                remediation="Periksa izin akun Anda untuk menjalankan perintah 'schtasks'.",
                details={"error": str(exc)},
            )



class GitRepositoriesCheck:
    """Memverifikasi keberadaan dan akses baca pada seluruh repositori Git lokal yang dikonfigurasi."""

    def __init__(
        self,
        repos: list[str | Path] | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self._explicit_repos = repos
        self.config_path = config_path

    def check(self) -> CheckResult:
        repos: list[Path] = []
        if self._explicit_repos is not None:
            repos = [Path(r).expanduser() for r in self._explicit_repos]
        else:
            try:
                cfg = load_config(self.config_path)
                if not cfg.sources.git.enabled:
                    return CheckResult(
                        name="Repositori Git",
                        status=CheckStatus.PASS,
                        message="Sumber Git dinonaktifkan dalam konfigurasi.",
                        details={"enabled": False},
                    )
                configured = cfg.sources.git.get_repositories()
                repos = [Path(r).expanduser() for r in configured]
            except Exception as exc:  # noqa: BLE001
                return CheckResult(
                    name="Repositori Git",
                    status=CheckStatus.FAIL,
                    message=f"Gagal membaca daftar repositori Git dari konfigurasi: {exc}",
                    remediation="Periksa konfigurasi 'sources.git.repos' pada config/config.yaml.",
                    details={"error": str(exc)},
                )

        if not repos:
            return CheckResult(
                name="Repositori Git",
                status=CheckStatus.WARN,
                message="Tidak ada repositori Git yang dikonfigurasi (sources.git.repos kosong).",
                remediation="Tambahkan path repositori lokal Anda pada konfigurasi 'sources.git.repos'.",
                details={"repos_count": 0},
            )

        missing_or_invalid: list[str] = []
        valid_repos: list[str] = []

        for repo in repos:
            repo_resolved = repo.resolve() if repo.exists() else repo
            if not repo_resolved.exists():
                missing_or_invalid.append(f"{repo} (tidak ditemukan)")
            elif not repo_resolved.is_dir():
                missing_or_invalid.append(f"{repo} (bukan direktori)")
            elif not (repo_resolved / ".git").exists():
                missing_or_invalid.append(f"{repo} (bukan repositori git; tanpa .git)")
            else:
                valid_repos.append(str(repo_resolved))

        if missing_or_invalid:
            return CheckResult(
                name="Repositori Git",
                status=CheckStatus.FAIL,
                message=f"Terdapat {len(missing_or_invalid)} repositori Git yang tidak valid: {', '.join(missing_or_invalid)}.",
                remediation="Periksa dan perbaiki path repositori Git pada config/config.yaml.",
                details={"invalid": missing_or_invalid, "valid": valid_repos},
            )

        return CheckResult(
            name="Repositori Git",
            status=CheckStatus.PASS,
            message=f"{len(valid_repos)} repositori Git terverifikasi dan dapat diakses.",
            details={"valid_repos": valid_repos},
        )


class AiApiCheck:
    """Memverifikasi ketersediaan kunci API provider AI (GEMINI_API_KEY)."""

    def __init__(self, env_var: str = "GEMINI_API_KEY") -> None:
        self.env_var = env_var

    def check(self) -> CheckResult:
        key = os.environ.get(self.env_var, "").strip()
        if not key:
            return CheckResult(
                name="Kunci API AI",
                status=CheckStatus.FAIL,
                message=f"Variabel lingkungan '{self.env_var}' tidak ditemukan atau kosong.",
                remediation=f"Setel environment variable '{self.env_var}' dengan API key Google AI Studio yang valid.",
                details={"env_var": self.env_var},
            )

        masked_key = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else "****"
        return CheckResult(
            name="Kunci API AI",
            status=CheckStatus.PASS,
            message=f"API key '{self.env_var}' terdeteksi ({masked_key}).",
            details={"env_var": self.env_var, "masked": masked_key},
        )


class CanaryPortalHealthCheck:
    """Pemeriksaan kesehatan DOM canary portal MagangHub menggunakan sesi aktif."""

    def __init__(
        self,
        portal_config: Any | None = None,
        target_date: date | None = None,
    ) -> None:
        if portal_config is not None:
            self.portal_config = portal_config
        else:
            from .portal import PortalConfig

            self.portal_config = PortalConfig()
        self.target_date = target_date or date.today()

    def check(self) -> CheckResult:
        try:
            from .portal import PlaywrightPortal

            with PlaywrightPortal(self.portal_config) as portal:
                report = portal.check(self.target_date)

            login_ok = bool(report.get("login"))
            selectors_ok = bool(report.get("all_selectors_healthy", True))
            error = report.get("error")

            if not login_ok:
                return CheckResult(
                    name="Canary Portal DOM",
                    status=CheckStatus.FAIL,
                    message=f"Gagal login ke portal: {error or 'Sesi tidak valid'}",
                    remediation="Jalankan 'magang-log login' untuk otentikasi ulang.",
                    details=report,
                )

            if not selectors_ok:
                return CheckResult(
                    name="Canary Portal DOM",
                    status=CheckStatus.FAIL,
                    message="Terdapat locator selector semantik portal yang rusak atau tidak ditemukan.",
                    remediation="Perbarui src/magang_log/portal/selectors.py sesuai perubahan DOM portal terbaru.",
                    details=report,
                )

            return CheckResult(
                name="Canary Portal DOM",
                status=CheckStatus.PASS,
                message="Canary DOM portal berhasil: login valid dan seluruh selector semantik sehat.",
                details=report,
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                name="Canary Portal DOM",
                status=CheckStatus.FAIL,
                message=f"Canary portal gagal diakses: {exc}",
                remediation="Periksa konektivitas jaringan atau login ulang dengan 'magang-log login'.",
                details={"error": str(exc)},
            )


@dataclass
class DoctorReport:
    """Laporan komprehensif audit kesehatan sistem."""

    results: list[CheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Mengembalikan True jika tidak ada pemeriksaan yang berstatus FAIL."""
        return all(r.status != CheckStatus.FAIL for r in self.results)

    @property
    def exit_code(self) -> int:
        """Kode keluar proses: 0 jika semua lolos/peringatan, 10 jika ada kegagalan."""
        return 0 if self.is_healthy else 10

    def to_dict(self) -> dict[str, Any]:
        """Mengonversi laporan ke struktur dictionary untuk format JSON."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "is_healthy": self.is_healthy,
            "exit_code": self.exit_code,
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.status == CheckStatus.PASS),
                "warnings": sum(1 for r in self.results if r.status == CheckStatus.WARN),
                "failed": sum(1 for r in self.results if r.status == CheckStatus.FAIL),
            },
            "checks": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "remediation": r.remediation,
                    "details": r.details,
                }
                for r in self.results
            ],
        }

    def format_terminal(self) -> str:
        """Membuat output terminal berformat dengan badge status [PASS], [WARN], [FAIL]."""
        lines = [
            "=" * 70,
            "MAGANG-LOG SYSTEM HEALTH DOCTOR",
            "=" * 70,
        ]

        for r in self.results:
            badge = f"[{r.status.value}]"
            lines.append(f"{badge:<7} {r.name:<26}: {r.message}")
            if r.remediation and r.status != CheckStatus.PASS:
                lines.append(f"        Solusi: {r.remediation}")

        passed = sum(1 for r in self.results if r.status == CheckStatus.PASS)
        warns = sum(1 for r in self.results if r.status == CheckStatus.WARN)
        fails = sum(1 for r in self.results if r.status == CheckStatus.FAIL)

        status_text = (
            "SEMUA SEHAT & SIAP OTOMASI (Exit 0)"
            if self.is_healthy
            else "PERLU TINDAKAN PERBAIKAN (Exit 10)"
        )

        lines.extend(
            [
                "-" * 70,
                f"Hasil Pemeriksaan: {passed} Lulus, {warns} Peringatan, {fails} Gagal",
                f"Status Akhir     : {status_text}",
                "=" * 70,
            ]
        )
        return "\n".join(lines)


def get_default_health_checks(
    config_path: str | Path | None = None,
    include_canary: bool = False,
    portal_config: Any | None = None,
) -> list[HealthCheck]:
    """Mengembalikan rantai pemeriksaan kesehatan inti standar."""
    checks: list[HealthCheck] = [
        PythonRuntimeCheck(),
        ConfigurationCheck(config_path=config_path),
        StorageCheck(),
        SessionCheck(),
        SchedulerCheck(),
        GitRepositoriesCheck(config_path=config_path),
        AiApiCheck(),
    ]
    if include_canary:
        checks.append(CanaryPortalHealthCheck(portal_config=portal_config))
    return checks


class Doctor:
    """Koordinator pelaksana pemeriksaan kesehatan sistem."""

    def __init__(self, checks: list[HealthCheck] | None = None) -> None:
        self.checks = checks if checks is not None else get_default_health_checks()

    def run_checks(self) -> DoctorReport:
        results = [check.check() for check in self.checks]
        return DoctorReport(results=results)
