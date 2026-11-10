"""Kolektor aktivitas peramban (Chromium) dengan isolasi snapshot SQLite dan allowlist domain."""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse, urlunparse

from .base import Evidence, SourceConfig

logger = logging.getLogger(__name__)

# Selisih mikrodetik antara WebKit Epoch (1601-01-01) dan Unix Epoch (1970-01-01)
WEBKIT_EPOCH_OFFSET_SECONDS = 11_644_473_600


def sanitize_url(raw_url: str) -> tuple[str, str]:
    """Membersihkan URL dengan menghapus query parameters (?...) dan hash fragments (#...).

    Mengembalikan tuple: (domain_bersih, url_bersih).
    """
    parsed = urlparse(raw_url)
    domain = parsed.netloc.lower()
    host = domain.split(":")[0] if ":" in domain else domain
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return host, clean_url


def is_domain_allowed(host: str, allowlist: Sequence[str]) -> bool:
    """Memeriksa apakah host cocok dengan allowlist domain (termasuk subdomain)."""
    if not allowlist:
        return False

    host_lower = host.lower()
    for allowed in allowlist:
        allowed_clean = allowed.strip().lower()
        if not allowed_clean:
            continue
        if host_lower == allowed_clean or host_lower.endswith("." + allowed_clean):
            return True
    return False


def _convert_browser_timestamp(ts: int | float) -> datetime | None:
    """Mengonversi timestamp browser (Chromium WebKit microseconds atau Unix timestamp) ke datetime UTC."""
    try:
        # Jika nilai besar (>= 10^13), merupakan format Chromium/WebKit microseconds
        if ts > 10_000_000_000_000:
            unix_sec = (ts / 1_000_000) - WEBKIT_EPOCH_OFFSET_SECONDS
            return datetime.fromtimestamp(unix_sec, tz=timezone.utc)
        # Jika nilai dalam milidetik Unix (>= 10^10)
        if ts > 10_000_000_000:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        # Nilai dalam detik Unix standar
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError, OverflowError) as exc:
        logger.debug("Gagal mengonversi timestamp %s: %s", ts, exc)
        return None


def get_default_browser_history_paths(
    browsers: Sequence[str] = ("chrome", "edge", "brave"),
) -> list[Path]:
    """Mendeteksi lokasi file riwayat peramban default berdasarkan sistem operasi."""
    paths: list[Path] = []
    browser_names = {b.lower() for b in browsers}

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data)
            if "chrome" in browser_names:
                paths.append(base / "Google" / "Chrome" / "User Data" / "Default" / "History")
            if "edge" in browser_names:
                paths.append(base / "Microsoft" / "Edge" / "User Data" / "Default" / "History")
            if "brave" in browser_names:
                paths.append(
                    base / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "History"
                )
    elif sys.platform == "darwin":
        home = Path.home()
        base = home / "Library" / "Application Support"
        if "chrome" in browser_names:
            paths.append(base / "Google" / "Chrome" / "Default" / "History")
        if "edge" in browser_names:
            paths.append(base / "Microsoft Edge" / "Default" / "History")
        if "brave" in browser_names:
            paths.append(base / "BraveSoftware" / "Brave-Browser" / "Default" / "History")
    else:
        home = Path.home()
        config_dir = home / ".config"
        if "chrome" in browser_names:
            paths.append(config_dir / "google-chrome" / "Default" / "History")
        if "edge" in browser_names:
            paths.append(config_dir / "microsoft-edge" / "Default" / "History")
        if "brave" in browser_names:
            paths.append(config_dir / "BraveSoftware" / "Brave-Browser" / "Default" / "History")

    return paths


class BrowserHistoryCollector:
    """Kolektor aktivitas peramban Chromium dengan isolasi snapshot dan filter allowlist."""

    name: str = "browser"

    def __init__(
        self,
        history_files: Sequence[Path | str] | None = None,
        allowlist: Sequence[str] | None = None,
        browsers: Sequence[str] = ("chrome", "edge", "brave"),
    ) -> None:
        self.history_files = [Path(p) for p in history_files] if history_files is not None else None
        self.allowlist = list(allowlist) if allowlist is not None else None
        self.browsers = list(browsers)

    def _resolve_settings(
        self,
        config: SourceConfig = None,
    ) -> tuple[list[Path], list[str]]:
        """Mengevaluasi file riwayat dan allowlist dari config atau parameter konstruktor."""
        history_paths: list[Path] = []
        allowlist: list[str] = []

        browser_cfg: Any = None
        if config is not None:
            if hasattr(config, "sources") and hasattr(config.sources, "get_browser"):
                browser_cfg = config.sources.get_browser()
            elif hasattr(config, "sources") and hasattr(config.sources, "browser"):
                browser_cfg = config.sources.browser
            elif hasattr(config, "get_allowlist"):
                browser_cfg = config

        if browser_cfg is not None:
            if hasattr(browser_cfg, "enabled") and not browser_cfg.enabled:
                return [], []
            if hasattr(browser_cfg, "get_allowlist"):
                allowlist = list(browser_cfg.get_allowlist())
            elif hasattr(browser_cfg, "allowlist") and browser_cfg.allowlist:
                allowlist = list(browser_cfg.allowlist)
            elif hasattr(browser_cfg, "allow_domains"):
                allowlist = list(browser_cfg.allow_domains)

            if hasattr(browser_cfg, "history_files") and browser_cfg.history_files:
                history_paths = [Path(p) for p in browser_cfg.history_files]
            elif self.history_files is not None:
                history_paths = list(self.history_files)
            elif hasattr(browser_cfg, "browsers") and browser_cfg.browsers:
                history_paths = get_default_browser_history_paths(browser_cfg.browsers)

        if not allowlist and self.allowlist is not None:
            allowlist = list(self.allowlist)

        if not history_paths:
            if self.history_files is not None:
                history_paths = list(self.history_files)
            else:
                history_paths = get_default_browser_history_paths(self.browsers)

        return history_paths, allowlist

    def _read_history_snapshot(
        self,
        target_path: Path,
        target_date: date,
        allowlist: Sequence[str],
    ) -> list[Evidence]:
        """Menyalin database history ke file snapshot sementara, membacanya, dan menghapus snapshot."""
        if not target_path.exists():
            logger.warning(
                "File riwayat peramban tidak ditemukan: %s, melewati...",
                target_path,
            )
            return []

        # Isolasi Snapshot: Buat file sementara terisolasi
        fd, temp_file_str = tempfile.mkstemp(prefix="browser_hist_snap_", suffix=".db")
        os.close(fd)
        temp_path = Path(temp_file_str)

        try:
            try:
                shutil.copy2(target_path, temp_path)
            except (OSError, PermissionError) as exc:
                logger.warning(
                    "Gagal membuat salinan snapshot database riwayat %s: [%s] %s",
                    target_path,
                    exc.__class__.__name__,
                    exc,
                )
                return []

            return self._query_database(temp_path, target_date, allowlist)
        finally:
            # Pastikan file snapshot sementara selalu dihapus/di-unlink
            try:
                temp_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.debug("Gagal menghapus file snapshot sementara %s: %s", temp_path, exc)

    def _query_database(
        self,
        db_path: Path,
        target_date: date,
        allowlist: Sequence[str],
    ) -> list[Evidence]:
        """Membaca rekaman riwayat dari file database SQLite."""
        conn: sqlite3.Connection | None = None
        results: list[Evidence] = []
        try:
            conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?immutable=1", uri=True)
            conn.row_factory = sqlite3.Row

            rows: list[Any] = []
            try:
                # Query gabungan standar Chromium: tabel visits + urls
                query_visits = """
                SELECT urls.url, urls.title, visits.visit_time
                FROM visits
                JOIN urls ON visits.url = urls.id
                ORDER BY visits.visit_time ASC;
                """
                rows = conn.execute(query_visits).fetchall()
            except sqlite3.OperationalError:
                # Fallback bila tabel visits tidak tersedia pada database tiruan minimal
                try:
                    query_urls = """
                    SELECT url, title, last_visit_time AS visit_time
                    FROM urls
                    ORDER BY last_visit_time ASC;
                    """
                    rows = conn.execute(query_urls).fetchall()
                except sqlite3.OperationalError as exc:
                    logger.warning(
                        "Skema database riwayat tidak dikenali pada %s: %s", db_path, exc
                    )
                    return []

            seen_keys: set[tuple[str, str]] = set()

            for row in rows:
                raw_url = str(row["url"] or "")
                raw_title = str(row["title"] or "")
                visit_time_val = row["visit_time"]

                if not raw_url or visit_time_val is None:
                    continue

                visit_dt = _convert_browser_timestamp(visit_time_val)
                if visit_dt is None:
                    continue

                # Batasan kalender: hanya ambil kunjungan pada target_date
                if visit_dt.date() != target_date:
                    continue

                host, clean_url = sanitize_url(raw_url)

                # Evaluasi domain terhadap allowlist
                if not is_domain_allowed(host, allowlist):
                    continue

                title = raw_title.strip() if raw_title.strip() else clean_url

                # Hindari duplikasi berlebih pada URL bersih dan judul yang sama
                dedup_key = (clean_url, title)
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                ev = Evidence(
                    source="browser",
                    kind="browser:visit",
                    ts=visit_dt,
                    title=title,
                    detail=clean_url,
                    strength="weak",
                    work_date=target_date,
                )
                results.append(ev)

        except (sqlite3.DatabaseError, OSError) as exc:
            logger.warning(
                "Kesalahan saat membaca database SQLite snapshot %s: [%s] %s",
                db_path,
                exc.__class__.__name__,
                exc,
            )
            return []
        finally:
            if conn is not None:
                conn.close()

        return results

    def collect(self, target_date: date, config: SourceConfig = None) -> list[Evidence]:
        """Mengumpulkan seluruh rekaman kunjungan browser yang telah disanitasi untuk target_date."""
        history_files, allowlist = self._resolve_settings(config)
        if not history_files:
            return []

        evidence_items: list[Evidence] = []
        for file_path in history_files:
            items = self._read_history_snapshot(file_path, target_date, allowlist)
            evidence_items.extend(items)

        return evidence_items
