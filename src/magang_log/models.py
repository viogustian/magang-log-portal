"""Model data untuk modul portal: status hari, status hasil, entri yang sudah disetujui."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from .collectors.base import Evidence as Evidence


class DayStatus(StrEnum):
    """Status sebuah hari di kalender portal (dibaca dari aria-label tombol hari)."""

    BELUM_DIISI = "BELUM_DIISI"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"  # menunggu persetujuan / disetujui / izin disetujui
    LIBUR = "LIBUR"
    TERKUNCI = "TERKUNCI"  # tombol hari nonaktif (mis. sudah lewat batas, atau belum waktunya)
    PERLU_TINDAKAN = "PERLU_TINDAKAN"  # ditolak / tidak hadir / perlu tindakan: jangan disentuh
    TIDAK_DIKENAL = "TIDAK_DIKENAL"  # label status yang belum dikenal: fail-closed


class Status(StrEnum):
    """Hasil satu eksekusi. Kosakata status domain pipeline."""

    BERHASIL = "BERHASIL"
    GAGAL = "GAGAL"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"
    LIBUR = "LIBUR"
    LOGIN_DIPERLUKAN = "LOGIN_DIPERLUKAN"
    TERKUNCI = "TERKUNCI"
    DRYRUN = "DRYRUN"
    LOKASI_TIDAK_TERSEDIA = "LOKASI_TIDAK_TERSEDIA"  # baru: form portal meminta lokasi
    PERLU_TINDAKAN = "PERLU_TINDAKAN"  # baru: status hari tidak boleh diubah otomatis
    PERLU_INPUT = "PERLU_INPUT"  # bukti tidak mencukupi, butuh catatan manual
    PERLU_REVIEW = "PERLU_REVIEW"  # validasi butuh tinjauan manusia atau tertunda
    VALIDATION_FAILED = "VALIDATION_FAILED"  # validasi draf gagal
    VALIDATION_ERROR = "VALIDATION_ERROR"  # alias standar untuk kesalahan validasi draf
    TIDAK_DIKENAL = "TIDAK_DIKENAL"  # label status kalender tidak dikenal: fail-closed
    CRASH = "CRASH"  # crash fatal atau kegagalan tak terduga


# Kode keluar CLI (lihat PRD bagian 11.3 & issue 05-01)
EXIT_CODES: dict[Status | str, int] = {
    Status.BERHASIL: 0,
    Status.SUDAH_TERKIRIM: 0,
    Status.LIBUR: 0,
    Status.DRYRUN: 0,
    Status.PERLU_TINDAKAN: 10,
    Status.PERLU_INPUT: 10,
    Status.PERLU_REVIEW: 10,
    Status.LOGIN_DIPERLUKAN: 20,
    Status.VALIDATION_FAILED: 30,
    Status.VALIDATION_ERROR: 30,
    Status.GAGAL: 40,
    Status.TERKUNCI: 40,
    Status.LOKASI_TIDAK_TERSEDIA: 40,
    Status.TIDAK_DIKENAL: 40,
    Status.CRASH: 1,
    # String key compatibility
    "BERHASIL": 0,
    "SUDAH_TERKIRIM": 0,
    "LIBUR": 0,
    "DRYRUN": 0,
    "PERLU_TINDAKAN": 10,
    "PERLU_INPUT": 10,
    "PERLU_REVIEW": 10,
    "LOGIN_DIPERLUKAN": 20,
    "VALIDATION_FAILED": 30,
    "VALIDATION_ERROR": 30,
    "GAGAL": 40,
    "TERKUNCI": 40,
    "LOKASI_TIDAK_TERSEDIA": 40,
    "TIDAK_DIKENAL": 40,
    "CRASH": 1,
}


def get_exit_code(status: Status | str | None) -> int:
    """Mengembalikan kode keluar proses standar untuk status yang diberikan."""
    if status is None:
        return 1
    if isinstance(status, Status):
        return EXIT_CODES.get(status, 1)
    status_str = str(status).strip()
    try:
        enum_val = Status(status_str)
        return EXIT_CODES.get(enum_val, EXIT_CODES.get(status_str, 1))
    except ValueError:
        return EXIT_CODES.get(status_str, 1)


@dataclass(frozen=True)
class DayInfo:
    work_date: date
    status: DayStatus
    label: str  # aria-label asli tombol hari, mis. "Selasa, 27 Oktober 2026, Belum Diisi"
    disabled: bool
    is_today: bool  # tombol memuat aria-current="date"


@dataclass(frozen=True)
class ApprovedEntry:
    """Isi logbook yang SUDAH ditinjau manusia. Satu-satunya input untuk pengiriman."""

    work_date: date
    aktivitas: str
    pembelajaran: str
    kendala: str
    approved_at: datetime | None = None  # None = belum disetujui => tidak boleh dikirim
    kehadiran: str = "Hadir"
    edit_ratio: float = 0.0
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            combined = (
                f"{self.aktivitas.strip()}\n{self.pembelajaran.strip()}\n{self.kendala.strip()}"
            )
            computed = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            object.__setattr__(self, "content_hash", computed)

    def assert_approved(self) -> None:
        """Memastikan entri sudah disetujui manusia (approved_at tidak kosong)."""
        if self.approved_at is None:
            raise ValueError("entri belum disetujui manusia (approved_at kosong)")

    def problems(self, min_chars: int, max_chars: int) -> list[str]:
        """Pelanggaran aturan form portal (min/maks karakter, kehadiran)."""
        found: list[str] = []
        if self.kehadiran != "Hadir":
            found.append(f"kehadiran harus 'Hadir' (diterima: {self.kehadiran!r})")
        for name in ("aktivitas", "pembelajaran", "kendala"):
            n = len(getattr(self, name).strip())
            if n < min_chars:
                found.append(f"{name}: {n} karakter (minimal {min_chars})")
            elif n > max_chars:
                found.append(f"{name}: {n} karakter (maksimal {max_chars})")
        return found


@dataclass
class PortalResult:
    status: Status
    note: str
    day: DayInfo | None = None
    screenshots: list[Path] = field(default_factory=list)
    traces: list[Path] = field(default_factory=list)


@dataclass
class RunRecord:
    """Catatan audit satu eksekusi pipeline (tabel runs)."""

    run_id: str
    work_date: date
    stage: str
    status: Status | str
    started_at: datetime
    finished_at: datetime | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    error_code: str | None = None


@dataclass
class EntryRecord:
    """Entri logbook harian beserta status siklus hidupnya (tabel entries)."""

    work_date: date
    draft_json: str
    approved_json: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    edit_ratio: float | None = None
    content_hash: str | None = None
    portal_status: str | None = None
    approved_at: datetime | None = None
    submitted_at: datetime | None = None
    verified_at: datetime | None = None


@dataclass
class EvidenceItem:
    """Butir bukti aktivitas yang dikumpulkan dari sumber (tabel evidence)."""

    id: str
    work_date: date
    source: str
    kind: str
    ts: str | datetime
    title: str
    detail: str = ""
    strength: str = "strong"


@dataclass
class NoteRecord:
    """Catatan refleksi manual harian (tabel notes)."""

    work_date: date
    kind: str  # 'aktivitas', 'pembelajaran', 'kendala'
    text: str
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
