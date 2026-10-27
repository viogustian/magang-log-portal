"""Model data untuk modul portal: status hari, status hasil, entri yang sudah disetujui."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path


class DayStatus(StrEnum):
    """Status sebuah hari di kalender portal (dibaca dari aria-label tombol hari)."""

    BELUM_DIISI = "BELUM_DIISI"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"  # menunggu persetujuan / disetujui / izin disetujui
    LIBUR = "LIBUR"
    TERKUNCI = "TERKUNCI"  # tombol hari nonaktif (mis. sudah lewat batas, atau belum waktunya)
    PERLU_TINDAKAN = "PERLU_TINDAKAN"  # ditolak / tidak hadir / perlu tindakan: jangan disentuh
    TIDAK_DIKENAL = "TIDAK_DIKENAL"  # label status yang belum dikenal: fail-closed


class Status(StrEnum):
    """Hasil satu eksekusi. Kosakata sama dengan proyek lama + dua status baru."""

    BERHASIL = "BERHASIL"
    GAGAL = "GAGAL"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"
    LIBUR = "LIBUR"
    LOGIN_DIPERLUKAN = "LOGIN_DIPERLUKAN"
    TERKUNCI = "TERKUNCI"
    DRYRUN = "DRYRUN"
    LOKASI_TIDAK_TERSEDIA = "LOKASI_TIDAK_TERSEDIA"  # baru: form portal meminta lokasi
    PERLU_TINDAKAN = "PERLU_TINDAKAN"  # baru: status hari tidak boleh diubah otomatis


# Kode keluar CLI (lihat PRD bagian 11.3)
EXIT_CODES: dict[Status, int] = {
    Status.BERHASIL: 0,
    Status.SUDAH_TERKIRIM: 0,
    Status.LIBUR: 0,
    Status.DRYRUN: 0,
    Status.PERLU_TINDAKAN: 10,
    Status.LOGIN_DIPERLUKAN: 20,
    Status.GAGAL: 40,
    Status.TERKUNCI: 40,
    Status.LOKASI_TIDAK_TERSEDIA: 40,
}


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
