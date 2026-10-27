"""Fungsi helper untuk instansiasi kolektor dan sanitasi privasi bukti harian."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ..settings import AppConfig, find_repo_root
from ..store import LedgerStore
from .base import Collector, Evidence, run_collectors
from .browser import BrowserHistoryCollector
from .git import GitCollector
from .notes import NotesCollector
from .privacy import PrivacyConfig, sanitize_evidence

logger = logging.getLogger(__name__)


def create_collectors(config: AppConfig, store: LedgerStore) -> list[Collector]:
    """Menginisialisasi kolektor yang aktif sesuai konfigurasi aplikasi."""
    collectors: list[Collector] = []

    # 1. Git Collector
    if config.sources.git.enabled:
        repos = config.sources.git.get_repositories()
        collectors.append(
            GitCollector(
                repos=repos,
                author_email=config.sources.git.author_email,
                include_diff=config.sources.git.include_diff,
            )
        )

    # 2. Notes Collector
    if config.sources.notes.enabled:
        collectors.append(NotesCollector(store=store))

    # 3. Browser History Collector
    browser_cfg = config.sources.get_browser()
    if browser_cfg.enabled:
        history_files = (
            [Path(f) for f in browser_cfg.history_files] if browser_cfg.history_files else None
        )
        collectors.append(
            BrowserHistoryCollector(
                history_files=history_files,
                allowlist=browser_cfg.get_allowlist(),
            )
        )

    return collectors


def collect_and_sanitize_evidence(
    target_date: date,
    config: AppConfig,
    store: LedgerStore,
) -> list[Evidence]:
    """Mengumpulkan bukti dari seluruh kolektor aktif dan menyaringnya melalui PrivacyFilter."""
    collectors = create_collectors(config, store)
    raw_evidence = run_collectors(collectors, target_date)

    # Susun repo_roots untuk konversi path Windows/Unix
    repo_roots = [find_repo_root()]
    for r in config.sources.git.get_repositories():
        try:
            repo_roots.append(Path(r))
        except (ValueError, TypeError):
            pass

    privacy_cfg = PrivacyConfig(repo_roots=repo_roots)
    return sanitize_evidence(raw_evidence, rules=privacy_cfg)
