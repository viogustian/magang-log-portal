"""Integration test untuk BrowserHistoryCollector: snapshot isolation, domain allowlist, dan sanitasi URL."""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from magang_log.collectors.base import Collector, Evidence
from magang_log.collectors.browser import BrowserHistoryCollector
from magang_log.settings import AppConfig, BrowserSourceSettings, SourcesSettings


def _create_synthetic_history_db(db_path: Path) -> None:
    """Membuat database SQLite riwayat browser Chromium tiruan dengan tabel urls dan visits."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                visit_count INTEGER DEFAULT 1,
                typed_count INTEGER DEFAULT 0,
                last_visit_time INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url INTEGER NOT NULL,
                visit_time INTEGER NOT NULL,
                from_visit INTEGER DEFAULT 0,
                transition INTEGER DEFAULT 0
            );
            """
        )

        # Konversi datetime ke format WebKit/Chromium microseconds sejak 1601-01-01 UTC
        # Epoch offset: 11,644,473,600 detik
        def _to_webkit_time(dt: datetime) -> int:
            unix_sec = dt.timestamp()
            return int((unix_sec + 11644473600) * 1_000_000)

        # 1. Kunjungan pada tanggal target (2026-10-27) - domain diperbolehkan (github.com) dengan query & hash
        dt1 = datetime(2026, 10, 27, 10, 15, 0, tzinfo=timezone.utc)
        cur = conn.execute(
            "INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?);",
            (
                "https://github.com/project/issues?token=SECRET_KEY&tab=open#issue-10",
                "Project Issue 10 - GitHub",
                _to_webkit_time(dt1),
            ),
        )
        u1_id = cur.lastrowid
        conn.execute(
            "INSERT INTO visits (url, visit_time) VALUES (?, ?);",
            (u1_id, _to_webkit_time(dt1)),
        )

        # 2. Kunjungan pada tanggal target (2026-10-27) - subdomain yang diperbolehkan (docs.github.com)
        dt2 = datetime(2026, 10, 27, 11, 30, 0, tzinfo=timezone.utc)
        cur = conn.execute(
            "INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?);",
            (
                "https://docs.github.com/en/rest/quickstart?query=123",
                "Quickstart REST API - GitHub Docs",
                _to_webkit_time(dt2),
            ),
        )
        u2_id = cur.lastrowid
        conn.execute(
            "INSERT INTO visits (url, visit_time) VALUES (?, ?);",
            (u2_id, _to_webkit_time(dt2)),
        )

        # 3. Kunjungan pada tanggal target (2026-10-27) - domain TIDAK diperbolehkan (personal-mail.com)
        dt3 = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)
        cur = conn.execute(
            "INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?);",
            (
                "https://personal-mail.com/inbox?user=test#msg",
                "Personal Inbox",
                _to_webkit_time(dt3),
            ),
        )
        u3_id = cur.lastrowid
        conn.execute(
            "INSERT INTO visits (url, visit_time) VALUES (?, ?);",
            (u3_id, _to_webkit_time(dt3)),
        )

        # 4. Kunjungan pada tanggal LAIN (2026-10-26) - domain diperbolehkan (harus diabaikan)
        dt4 = datetime(2026, 10, 26, 15, 0, 0, tzinfo=timezone.utc)
        cur = conn.execute(
            "INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?);",
            (
                "https://github.com/yesterday/commit",
                "Yesterday Commit",
                _to_webkit_time(dt4),
            ),
        )
        u4_id = cur.lastrowid
        conn.execute(
            "INSERT INTO visits (url, visit_time) VALUES (?, ?);",
            (u4_id, _to_webkit_time(dt4)),
        )

        conn.commit()
    finally:
        conn.close()


def test_browser_collector_protocol_conformance() -> None:
    collector = BrowserHistoryCollector()
    assert isinstance(collector, Collector)


def test_browser_collector_snapshot_allowlist_and_url_sanitization(tmp_path: Path) -> None:
    db_file = tmp_path / "History"
    _create_synthetic_history_db(db_file)

    target_date = date(2026, 10, 27)
    allowlist = ["github.com", "stackoverflow.com"]

    collector = BrowserHistoryCollector(
        history_files=[db_file],
        allowlist=allowlist,
    )
    evidence_list = collector.collect(target_date)

    # Hanya 2 entri github.com pada tanggal 2026-10-27 yang boleh lolos
    assert len(evidence_list) == 2

    for ev in evidence_list:
        assert isinstance(ev, Evidence)
        assert ev.source == "browser"
        assert ev.kind == "browser:visit"
        # Harus diklasifikasikan sebagai weak evidence
        assert ev.strength == "weak"
        assert len(ev.id) == 10
        assert ev.work_date == target_date

        # Query strings (?...) dan hash fragments (#...) harus bersih terpotong
        assert "SECRET_KEY" not in ev.detail
        assert "token=" not in ev.detail
        assert "#issue-10" not in ev.detail
        assert "?query=123" not in ev.detail

    # Pastikan URL bersih dan judul tersimpan
    titles = [ev.title for ev in evidence_list]
    assert "Project Issue 10 - GitHub" in titles
    assert "Quickstart REST API - GitHub Docs" in titles

    # Detail berisi URL bersih tanpa query string
    details = [ev.detail for ev in evidence_list]
    assert any("https://github.com/project/issues" in d for d in details)
    assert any("https://docs.github.com/en/rest/quickstart" in d for d in details)

    # Domain tidak allowlisted (personal-mail.com) dan tanggal kemarin tidak boleh ada
    assert not any("personal-mail.com" in d for d in details)
    assert not any("Yesterday Commit" in t for t in titles)


def test_temporary_snapshot_unlinked_after_execution(tmp_path: Path) -> None:
    db_file = tmp_path / "History"
    _create_synthetic_history_db(db_file)

    collector = BrowserHistoryCollector(
        history_files=[db_file],
        allowlist=["github.com"],
    )

    # Catat daftar file sebelum koleksi
    before_files = set(tmp_path.glob("*"))

    collector.collect(date(2026, 10, 27))

    # Pastikan tidak ada file sementara (.tmp atau snapshot) yang tertinggal di folder
    after_files = set(tmp_path.glob("*"))
    assert before_files == after_files


def test_locked_database_tolerance(tmp_path: Path) -> None:
    db_file = tmp_path / "History"
    _create_synthetic_history_db(db_file)

    # Buka koneksi aktif dengan transaksi eksklusif untuk mensimulasikan browser yang sedang berjalan
    locking_conn = sqlite3.connect(str(db_file))
    locking_conn.execute("BEGIN EXCLUSIVE;")

    try:
        collector = BrowserHistoryCollector(
            history_files=[db_file],
            allowlist=["github.com"],
        )
        # Snapshot isolation harus mampu menyalin atau membaca tanpa crash
        evidence_list = collector.collect(date(2026, 10, 27))
        # Jika file berhasil disalin dari snapshot filesystem, data tetap terbaca
        assert isinstance(evidence_list, list)
    finally:
        locking_conn.rollback()
        locking_conn.close()


def test_missing_or_corrupt_database_logs_warning_without_failing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    missing_file = tmp_path / "NonExistentHistory"
    corrupt_file = tmp_path / "CorruptHistory"
    corrupt_file.write_text("BUKAN DATABASE SQLITE", encoding="utf-8")

    collector = BrowserHistoryCollector(
        history_files=[missing_file, corrupt_file],
        allowlist=["github.com"],
    )

    with caplog.at_level(logging.WARNING):
        results = collector.collect(date(2026, 10, 27))

    # Mengembalikan list kosong tanpa exception tak tertangani
    assert results == []
    # Structured warning tercatat
    assert "NonExistentHistory" in caplog.text or "CorruptHistory" in caplog.text


def test_browser_collector_with_app_config(tmp_path: Path) -> None:
    db_file = tmp_path / "History"
    _create_synthetic_history_db(db_file)

    config = AppConfig(
        sources=SourcesSettings(
            browser=BrowserSourceSettings(
                enabled=True,
                allow_domains=["github.com"],
            )
        )
    )

    collector = BrowserHistoryCollector(history_files=[db_file])
    evidence_list = collector.collect(date(2026, 10, 27), config=config)

    assert len(evidence_list) == 2
