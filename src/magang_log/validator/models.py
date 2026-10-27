"""Model data untuk hasil validasi logbook (ValidationReport)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    """Hasil evaluasi multi-tahap deterministik terhadap draf logbook.

    Attributes:
        is_valid: Bernilai True jika tidak ada error (len(errors) == 0).
        errors: Daftar pesan error yang menggagalkan validasi (hard failure).
        warnings: Daftar pesan peringatan kualitas (soft failure).
        grounding_score: Proporsi kalimat pada aktivitas yang didukung bukti terverifikasi (0.0 - 1.0).
        detected_filler: Daftar frasa template klise/canned filler yang ditemukan.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    grounding_score: float = 1.0
    detected_filler: list[str] = field(default_factory=list)
