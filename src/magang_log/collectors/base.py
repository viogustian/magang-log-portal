"""Kontrak data Evidence, protokol Collector, dan eksekutor kolektor terisolasi."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)

EvidenceSource = Literal["git", "note", "browser", "activitywatch", "plugin"]
EvidenceStrength = Literal["strong", "weak"]

VALID_SOURCES: set[str] = {"git", "note", "browser", "activitywatch", "plugin"}
VALID_STRENGTHS: set[str] = {"strong", "weak"}

SourceConfig = Any


def compute_evidence_id(
    source: str,
    kind: str,
    ts: datetime | str,
    title: str,
) -> str:
    """Menghasilkan hash SHA1 10-karakter deterministik dari source, kind, timestamp ISO, dan judul."""
    iso_ts = ts.isoformat() if isinstance(ts, datetime) else str(ts)
    sanitized_title = title.strip()
    payload = f"{source}:{kind}:{iso_ts}:{sanitized_title}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


@dataclass(frozen=True)
class Evidence:
    """Struktur data bukti aktivitas yang immutable (frozen).

    Fields:
    - id: SHA1 hash 10 karakter deterministik
    - source: sumber bukti ("git", "note", "browser", "activitywatch", "plugin")
    - kind: jenis detail ("commit", "note:kendala", "note:aktivitas", "note:pembelajaran", dll)
    - ts: timestamp UTC peristiwa
    - title: ringkasan atau subjek tersanitasi
    - detail: konteks tersanitasi, berkas yang disentuh, atau catatan refleksi
    - strength: klasifikasi kekuatan bukti ("strong", "weak")
    - work_date: tanggal kerja yang diasosiasikan (diturunkan dari ts bila tidak diberikan)
    """

    source: EvidenceSource
    kind: str
    ts: datetime
    title: str
    detail: str = ""
    strength: EvidenceStrength = "strong"
    id: str = ""
    work_date: date | None = None

    def __post_init__(self) -> None:
        if self.source not in VALID_SOURCES:
            raise ValueError(
                f"Invalid source: {self.source!r}. Must be one of {sorted(VALID_SOURCES)}"
            )
        if self.strength not in VALID_STRENGTHS:
            raise ValueError(
                f"Invalid strength: {self.strength!r}. Must be one of {sorted(VALID_STRENGTHS)}"
            )

        if not self.id:
            calculated_id = compute_evidence_id(
                source=self.source,
                kind=self.kind,
                ts=self.ts,
                title=self.title,
            )
            object.__setattr__(self, "id", calculated_id)

        if self.work_date is None:
            derived_date = (
                self.ts.date()
                if isinstance(self.ts, datetime)
                else date.fromisoformat(str(self.ts)[:10])
            )
            object.__setattr__(self, "work_date", derived_date)


@runtime_checkable
class Collector(Protocol):
    """Protokol standar antarmuka untuk semua plugin pengumpul aktivitas."""

    def collect(self, target_date: date, config: SourceConfig = None) -> list[Evidence]:
        """Mengumpulkan daftar bukti aktivitas untuk tanggal target."""
        ...


@dataclass(frozen=True)
class CollectorFailure:
    """Informasi kegagalan satu kolektor dalam eksekusi terisolasi."""

    collector_name: str
    target_date: date
    error_type: str
    error_message: str


class CollectorRunner:
    """Eksekutor kolektor terisolasi: menangkap kesalahan kolektor individual tanpa membatalkan proses."""

    def __init__(
        self,
        collectors: Sequence[Collector],
        log: logging.Logger | None = None,
    ) -> None:
        self.collectors = list(collectors)
        self.logger = log or logger
        self.failures: list[CollectorFailure] = []

    def run(self, target_date: date, config: SourceConfig = None) -> list[Evidence]:
        """Menjalankan seluruh kolektor secara berurutan dan mengembalikan gabungan bukti."""
        self.failures.clear()
        aggregated: list[Evidence] = []

        for col in self.collectors:
            col_name = getattr(col, "name", col.__class__.__name__)
            try:
                items = col.collect(target_date, config)
                aggregated.extend(items)
            except Exception as exc:  # noqa: BLE001 - ditangkap untuk isolasi kegagalan sumber
                failure = CollectorFailure(
                    collector_name=col_name,
                    target_date=target_date,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
                self.failures.append(failure)
                self.logger.warning(
                    "Collector %s gagal mengumpulkan data untuk tanggal %s: [%s] %s",
                    col_name,
                    target_date.isoformat(),
                    failure.error_type,
                    failure.error_message,
                )

        return aggregated


def run_collectors(
    collectors: Sequence[Collector],
    target_date: date,
    config: SourceConfig = None,
    log: logging.Logger | None = None,
) -> list[Evidence]:
    """Helper fungsi untuk menjalankan kolektor secara terisolasi."""
    runner = CollectorRunner(collectors, log=log)
    return runner.run(target_date, config)
