"""Mesin keputusan anti-tamper untuk kalender portal MagangHub.

Mengevaluasi nama aksesibel (aria-label) dan status interaktif (disabled) tombol hari
sebelum membuka atau menyentuh formulir harian portal. Menghentikan eksekusi segera
pada status yang tidak dapat dikirim (non-submittable) tanpa menyentuh DOM form.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import EXIT_CODES, DayInfo, DayStatus, Status


@dataclass(frozen=True)
class AntiTamperDecision:
    """Hasil penilaian anti-tamper terhadap sebuah tanggal di kalender portal."""

    submittable: bool
    status: Status
    exit_code: int
    reason: str
    day: DayInfo


class AntiTamperGate:
    """Anti-tamper gatekeeper: melindungi portal dari modifikasi pada hari yang tidak diizinkan."""

    _NON_SUBMITTABLE_MAP: dict[DayStatus, tuple[Status, str]] = {
        DayStatus.SUDAH_TERKIRIM: (
            Status.SUDAH_TERKIRIM,
            "Hari sudah terkirim atau disetujui ('Menunggu Persetujuan' / 'Hadir disetujui' / "
            "'Menunggu Tindakan Mentor')",
        ),
        DayStatus.LIBUR: (
            Status.LIBUR,
            "Hari libur posisi atau hari libur resmi ('Jadwal libur posisi' / 'Hari Libur')",
        ),
        DayStatus.TERKUNCI: (
            Status.TERKUNCI,
            "Hari terkunci untuk pengisian ('Belum Diisi' dengan tombol disabled=True)",
        ),
        DayStatus.PERLU_TINDAKAN: (
            Status.PERLU_TINDAKAN,
            "Hari membutuhkan tindakan manual pengguna ('Perlu Tindakan Anda' / 'Kehadiran Ditolak')",
        ),
        DayStatus.TIDAK_DIKENAL: (
            Status.TIDAK_DIKENAL,
            "Label status kalender tidak dikenal (fail-closed untuk mencegah salah modifikasi)",
        ),
    }

    @classmethod
    def inspect(cls, day: DayInfo) -> AntiTamperDecision:
        """Menilai apakah tanggal kalender aman untuk dibuka dan diisi.

        Jika status non-submittable, eksekusi WAJIB berhenti tanpa menyentuh formulir.
        """
        # 1. Hari aktif siap diisi
        if day.status == DayStatus.BELUM_DIISI:
            if day.disabled:
                status = Status.TERKUNCI
                return AntiTamperDecision(
                    submittable=False,
                    status=status,
                    exit_code=EXIT_CODES[status],
                    reason="Hari 'Belum Diisi' tetapi tombol nonaktif (disabled=True)",
                    day=day,
                )
            return AntiTamperDecision(
                submittable=True,
                status=Status.BERHASIL,
                exit_code=0,
                reason="Hari siap diisi (Belum Diisi dan tombol aktif)",
                day=day,
            )

        # 2. Status non-submittable terdaftar
        if day.status in cls._NON_SUBMITTABLE_MAP:
            status, reason = cls._NON_SUBMITTABLE_MAP[day.status]
            return AntiTamperDecision(
                submittable=False,
                status=status,
                exit_code=EXIT_CODES[status],
                reason=f"{reason}; aria-label={day.label!r}",
                day=day,
            )

        # 3. Fail-closed cadangan jika status di luar dugaan
        status = Status.TIDAK_DIKENAL
        return AntiTamperDecision(
            submittable=False,
            status=status,
            exit_code=EXIT_CODES[status],
            reason=f"Status hari tidak dikenal ({day.status!r}); fail-closed",
            day=day,
        )
