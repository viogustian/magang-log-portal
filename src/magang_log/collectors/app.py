"""Kolektor gabungan aktivitas desktop (AppActivityCollector) berbasis Recent Items dan log sesi."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .base import Evidence, SourceConfig
from .recent import RecentItemsScanner
from .session_log import ApplicationSessionLogParser

if TYPE_CHECKING:
    from ..workprofile import WorkProfile

logger = logging.getLogger(__name__)


def _extract_project_identifier(title: str) -> tuple[str, str]:
    """Mengekstrak (app_name, project_name) dari judul bukti aktivitas."""
    if " - " in title:
        app_name, _, project_name = title.partition(" - ")
        return app_name.strip().lower(), project_name.strip().lower()
    return title.strip().lower(), ""


def merge_app_evidence(
    recent_evidence: Sequence[Evidence],
    session_evidence: Sequence[Evidence],
) -> list[Evidence]:
    """Menggabungkan bukti sentuhan berkas (weak) dan log sesi (strong).

    Jika sebuah proyek memiliki bukti log sesi aktif (strong) pada tanggal target,
    bukti sentuhan berkas (weak) untuk proyek yang sama disupresi demi menghindari redundansi.
    """
    strong_projects: set[tuple[str, str]] = set()

    for ev in session_evidence:
        app_key, proj_key = _extract_project_identifier(ev.title)
        if proj_key and proj_key not in {"session", "session activity"}:
            strong_projects.add((app_key, proj_key))

    merged: list[Evidence] = list(session_evidence)

    for ev in recent_evidence:
        app_key, proj_key = _extract_project_identifier(ev.title)
        # Jika proyek sudah memiliki bukti log sesi aktif, lewati bukti sentuhan lemah
        if (app_key, proj_key) in strong_projects:
            continue
        merged.append(ev)

    # Deduplikasi deterministik berdasarkan ID bukti
    seen_ids: set[str] = set()
    deduped: list[Evidence] = []
    for ev in merged:
        if ev.id not in seen_ids:
            seen_ids.add(ev.id)
            deduped.append(ev)

    # Urutkan secara deterministik berdasarkan timestamp lalu title
    deduped.sort(key=lambda x: (x.ts, x.title))
    return deduped


class AppActivityCollector:
    """Kolektor terpadu aktivitas aplikasi desktop yang mengorkestrasi RecentItemsScanner dan SessionLogParser."""

    name: str = "app"

    def __init__(
        self,
        work_profile: WorkProfile | None = None,
        recent_scanner: RecentItemsScanner | None = None,
        session_parser: ApplicationSessionLogParser | None = None,
        recent_dir: Path | str | None = None,
        log_base_dirs: Sequence[Path | str] | None = None,
        env_overrides: dict[str, Path | str] | None = None,
    ) -> None:
        self.work_profile = work_profile
        self.recent_scanner = recent_scanner or RecentItemsScanner(
            recent_dir=recent_dir,
            work_profile=work_profile,
        )
        self.session_parser = session_parser or ApplicationSessionLogParser(
            base_dirs=log_base_dirs,
            env_overrides=env_overrides,
            work_profile=work_profile,
        )

    def scan(
        self,
        target_date: date,
        profile: WorkProfile | None = None,
    ) -> list[Evidence]:
        """Menjalankan pemindaian sub-scanner dan menggabungkan bukti aktivitas aplikasi desktop."""
        active_profile = profile if profile is not None else self.work_profile
        if active_profile is None:
            logger.debug(
                "Tidak ada WorkProfile aktif pada AppActivityCollector (zero surveillance boundary)."
            )
            return []

        recent_items = self.recent_scanner.scan(target_date, profile=active_profile)
        session_items = self.session_parser.scan(target_date, profile=active_profile)

        return merge_app_evidence(recent_evidence=recent_items, session_evidence=session_items)

    def collect(
        self,
        target_date: date,
        config: SourceConfig | None = None,
    ) -> list[Evidence]:
        """Mengumpulkan seluruh bukti aktivitas aplikasi desktop (protokol Collector)."""
        profile = self.work_profile
        from ..workprofile import WorkProfile

        if isinstance(config, WorkProfile):
            profile = config
        elif isinstance(config, dict) and "profile" in config:
            profile = config["profile"]
        elif hasattr(config, "profile") and isinstance(config.profile, WorkProfile):
            profile = config.profile
        elif (
            hasattr(config, "sources")
            and hasattr(config.sources, "app")
            and config.sources.app.work_profile is not None
        ):
            profile = config.sources.app.work_profile

        return self.scan(target_date, profile=profile)
