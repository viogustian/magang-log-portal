"""Modul structured logging JSON Lines dan manajemen exit code pipeline."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .models import Status

# Field terlarang pada log level INFO (Privacy Guardrail)
PROHIBITED_INFO_FIELDS: frozenset[str] = frozenset({
    "aktivitas",
    "pembelajaran",
    "kendala",
    "draft",
    "draft_json",
    "approved_json",
    "logbook",
    "evidence",
    "evidence_refs",
    "evidence_details",
    "secret",
    "password",
    "token",
    "api_key",
})


class PrivacyViolationError(ValueError):
    """Kesalahan ketika data privat draf/logbook/bukti dicoba dicatat pada log level INFO."""


def format_utc_iso(dt: datetime | None = None) -> str:
    """Format datetime ke string ISO 8601 UTC dengan presisi milidetik (mis. 2026-10-27T16:30:15.123Z)."""
    now = dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    ms = int(now.microsecond / 1000)
    return now.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"


def check_privacy_guard(data: dict[str, Any], level: str = "INFO") -> None:
    """Memeriksa bahwa data pada level INFO tidak memuat teks logbook atau bukti sensitif."""
    if level.upper() != "INFO":
        return

    for key, val in data.items():
        k_lower = str(key).lower()
        if k_lower in PROHIBITED_INFO_FIELDS:
            raise PrivacyViolationError(
                f"Pelanggaran privasi: field sensitif '{key}' dilarang dicatat pada log level INFO."
            )
        if isinstance(val, dict):
            check_privacy_guard(val, level=level)


@dataclass(frozen=True)
class StructuredLogEntry:
    """Struktur catatan log terstruktur JSON Lines sesuai spesifikasi NFR-OBS-01."""

    ts: str
    level: str
    run_id: str
    work_date: str
    stage: str
    status: str
    duration_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Konversi entri ke kamus data JSON-serializable."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialisasi entri ke string JSON satu baris yang ringkas."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredLogEntry:
        """Instansiasi StructuredLogEntry dari kamus data."""
        return cls(
            ts=str(data.get("ts", "")),
            level=str(data.get("level", "INFO")),
            run_id=str(data.get("run_id", "")),
            work_date=str(data.get("work_date", "")),
            stage=str(data.get("stage", "")),
            status=str(data.get("status", "")),
            duration_ms=int(data.get("duration_ms", 0)),
            tokens_in=int(data.get("tokens_in", 0)),
            tokens_out=int(data.get("tokens_out", 0)),
            error_code=data.get("error_code"),
        )

    @classmethod
    def from_json(cls, line: str) -> StructuredLogEntry:
        """Instansiasi StructuredLogEntry dari satu baris teks JSON."""
        return cls.from_dict(json.loads(line.strip()))


class StructuredLogger:
    """Engine logging terstruktur yang menghasilkan catatan JSON Lines ke file log."""

    DEFAULT_LOG_PATH = Path("data/logs/magang-log.jsonl")

    def __init__(
        self,
        log_file: Path | str | None = None,
        min_level: str = "INFO",
        auto_rotate: bool = True,
    ) -> None:
        self.log_file = Path(log_file or self.DEFAULT_LOG_PATH)
        self.min_level = min_level.upper()
        self.auto_rotate = auto_rotate

    def log_event(
        self,
        run_id: str,
        work_date: str | date,
        stage: str,
        status: Status | str,
        duration_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_code: str | None = None,
        level: str = "INFO",
        dt: datetime | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> StructuredLogEntry:
        """Mencatat satu event siklus hidup eksekusi pipeline dengan validasi privasi."""
        lvl = level.upper()

        if extra_data:
            check_privacy_guard(extra_data, level=lvl)

        w_date = work_date.isoformat() if isinstance(work_date, date) else str(work_date)
        st_val = status.value if isinstance(status, Status) else str(status)

        entry = StructuredLogEntry(
            ts=format_utc_iso(dt),
            level=lvl,
            run_id=str(run_id),
            work_date=w_date,
            stage=str(stage),
            status=st_val,
            duration_ms=max(0, int(duration_ms)),
            tokens_in=max(0, int(tokens_in)),
            tokens_out=max(0, int(tokens_out)),
            error_code=error_code,
        )

        self.emit(entry, now=dt)
        return entry

    def info(
        self,
        run_id: str,
        work_date: str | date,
        stage: str,
        status: Status | str,
        duration_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_code: str | None = None,
        dt: datetime | None = None,
    ) -> StructuredLogEntry:
        """Catat event berlevel INFO."""
        return self.log_event(
            run_id=run_id,
            work_date=work_date,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            error_code=error_code,
            level="INFO",
            dt=dt,
        )

    def warning(
        self,
        run_id: str,
        work_date: str | date,
        stage: str,
        status: Status | str,
        duration_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_code: str | None = None,
        dt: datetime | None = None,
    ) -> StructuredLogEntry:
        """Catat event berlevel WARNING."""
        return self.log_event(
            run_id=run_id,
            work_date=work_date,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            error_code=error_code,
            level="WARNING",
            dt=dt,
        )

    def error(
        self,
        run_id: str,
        work_date: str | date,
        stage: str,
        status: Status | str,
        duration_ms: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_code: str | None = None,
        dt: datetime | None = None,
    ) -> StructuredLogEntry:
        """Catat event berlevel ERROR."""
        return self.log_event(
            run_id=run_id,
            work_date=work_date,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            error_code=error_code,
            level="ERROR",
            dt=dt,
        )

    def emit(self, entry: StructuredLogEntry, now: datetime | None = None) -> None:
        """Tulis StructuredLogEntry ke file log dengan auto-rotasi mingguan bila diperlukan."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        if self.auto_rotate:
            self.rotate_weekly(now=now)

        line = entry.to_json() + "\n"
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line)

    def rotate_weekly(self, now: datetime | None = None) -> Path | None:
        """Melakukan rotasi mingguan otomatis bila catatan log berasal dari minggu kalender sebelumnya.

        Mengganti nama file log menjadi magang-log.<YYYY-Www>.jsonl.
        """
        if not self.log_file.exists() or self.log_file.stat().st_size == 0:
            return None

        current_dt = now or datetime.now(timezone.utc)
        curr_year, curr_week, _ = current_dt.isocalendar()

        # Baca baris pertama untuk mengetahui minggu dari log yang ada
        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                return None
            first_entry = json.loads(first_line)
            ts_str = first_entry.get("ts", "")
            # Ekstrak tanggal dari timestamp ISO (mis. 2026-10-20)
            log_date = date.fromisoformat(ts_str[:10])
            log_year, log_week, _ = log_date.isocalendar()
        except (json.JSONDecodeError, ValueError, OSError):
            # Fallback ke waktu modifikasi file
            mtime = datetime.fromtimestamp(self.log_file.stat().st_mtime, tz=timezone.utc)
            log_year, log_week, _ = mtime.isocalendar()

        # Bila minggu sekarang lebih baru dari minggu log pertama, rotasi file
        if (curr_year, curr_week) > (log_year, log_week):
            stem = self.log_file.stem
            suffix = self.log_file.suffix
            rotated_name = f"{stem}.{log_year}-W{log_week:02d}{suffix}"
            rotated_path = self.log_file.parent / rotated_name

            # Tangani kemungkinan tabrakan nama file rotasi
            counter = 1
            while rotated_path.exists():
                rotated_path = self.log_file.parent / f"{stem}.{log_year}-W{log_week:02d}.{counter}{suffix}"
                counter += 1

            shutil.move(str(self.log_file), str(rotated_path))
            return rotated_path

        return None

    def read_logs(self) -> list[StructuredLogEntry]:
        """Membaca dan mem-parsing seluruh entri dari file log saat ini."""
        if not self.log_file.exists():
            return []
        entries: list[StructuredLogEntry] = []
        with self.log_file.open("r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if clean:
                    try:
                        entries.append(StructuredLogEntry.from_json(clean))
                    except (json.JSONDecodeError, ValueError):
                        continue
        return entries

    def read_all_logs(self) -> list[StructuredLogEntry]:
        """Membaca seluruh entri dari file log aktif beserta semua arsip rotasi mingguan."""
        log_dir = self.log_file.parent
        if not log_dir.exists():
            return []

        entries: list[StructuredLogEntry] = []
        # Cari file yang cocok dengan magang-log*.jsonl
        pattern = re.compile(rf"^{re.escape(self.log_file.stem)}.*\.jsonl$")
        log_files = sorted(
            [p for p in log_dir.iterdir() if p.is_file() and pattern.match(p.name)],
            key=lambda p: p.name,
        )

        for p in log_files:
            try:
                with p.open("r", encoding="utf-8") as f:
                    for line in f:
                        clean = line.strip()
                        if clean:
                            try:
                                entries.append(StructuredLogEntry.from_json(clean))
                            except (json.JSONDecodeError, ValueError):
                                continue
            except OSError:
                continue

        return entries


def clean_old_run_artifacts(
    runs_dir: Path | str = "data/runs",
    max_age_days: int = 30,
    now: datetime | None = None,
) -> list[Path]:
    """Membersihkan artefak eksekusi lama yang melebihi batas retensi (default: 30 hari).

    Mengenali direktori harian berekstensi tanggal (YYYY-MM-DD) serta file/folder lainnya
    berdasarkan waktu modifikasi st_mtime.
    """
    root = Path(runs_dir)
    if not root.exists():
        return []

    curr_dt = now or datetime.now(timezone.utc)
    curr_date = curr_dt.date()
    curr_ts = curr_dt.timestamp()

    removed: list[Path] = []
    date_regex = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    for child in list(root.iterdir()):
        is_old = False

        if child.is_dir() and date_regex.match(child.name):
            try:
                folder_date = date.fromisoformat(child.name)
                age_days = (curr_date - folder_date).days
                if age_days > max_age_days:
                    is_old = True
            except ValueError:
                pass

        if not is_old:
            try:
                st = child.stat()
                age_seconds = curr_ts - st.st_mtime
                if age_seconds > (max_age_days * 86400):
                    is_old = True
            except OSError:
                continue

        if is_old:
            try:
                if child.is_dir():
                    shutil.rmtree(str(child))
                else:
                    child.unlink()
                removed.append(child)
            except OSError:
                continue

    return removed


def clean_old_logs(
    logs_dir: Path | str = "data/logs",
    max_age_days: int = 90,
    now: datetime | None = None,
) -> list[Path]:
    """Membersihkan arsip file log lama yang melebihi batas retensi."""
    root = Path(logs_dir)
    if not root.exists():
        return []

    curr_dt = now or datetime.now(timezone.utc)
    curr_ts = curr_dt.timestamp()
    removed: list[Path] = []

    for child in list(root.glob("*.jsonl")):
        # Jangan hapus file log aktif utama
        if child.name == "magang-log.jsonl":
            continue
        try:
            st = child.stat()
            if (curr_ts - st.st_mtime) > (max_age_days * 86400):
                child.unlink()
                removed.append(child)
        except OSError:
            continue

    return removed


_GLOBAL_LOGGER: StructuredLogger | None = None


def get_logger(log_file: Path | str | None = None) -> StructuredLogger:
    """Mendapatkan atau menginisialisasi singleton StructuredLogger default."""
    global _GLOBAL_LOGGER
    if log_file is not None:
        return StructuredLogger(log_file=log_file)
    if _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = StructuredLogger()
    return _GLOBAL_LOGGER


def log_run_event(
    run_id: str,
    work_date: str | date,
    stage: str,
    status: Status | str,
    duration_ms: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    error_code: str | None = None,
    level: str = "INFO",
) -> StructuredLogEntry:
    """Helper global untuk mencatat event eksekusi pipeline secara ringkas."""
    return get_logger().log_event(
        run_id=run_id,
        work_date=work_date,
        stage=stage,
        status=status,
        duration_ms=duration_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        error_code=error_code,
        level=level,
    )
