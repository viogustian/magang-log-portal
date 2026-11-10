"""Unit test untuk protokol Collector dan eksekutor kolektor terisolasi."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pytest

from magang_log.collectors.base import (
    Collector,
    CollectorRunner,
    Evidence,
    run_collectors,
)


class DummyWorkingCollector:
    """Kolektor dummy yang mengembalikan bukti valid."""

    name = "dummy_git"

    def collect(self, target_date: date, config: object = None) -> list[Evidence]:
        return [
            Evidence(
                source="git",
                kind="commit",
                ts=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
                title="Commit 1",
                detail="files touched",
                strength="strong",
            ),
            Evidence(
                source="git",
                kind="commit",
                ts=datetime(2026, 10, 27, 11, 0, 0, tzinfo=timezone.utc),
                title="Commit 2",
                detail="more files",
                strength="strong",
            ),
        ]


class FailingCollector:
    """Kolektor dummy yang sengaja melempar exception."""

    name = "failing_browser"

    def collect(self, target_date: date, config: object = None) -> list[Evidence]:
        raise PermissionError("Browser history database locked")


class AnotherWorkingCollector:
    """Kolektor dummy kedua yang harus tetap berjalan meskipun kolektor sebelumnya gagal."""

    name = "dummy_note"

    def collect(self, target_date: date, config: object = None) -> list[Evidence]:
        return [
            Evidence(
                source="note",
                kind="note:aktivitas",
                ts=datetime(2026, 10, 27, 14, 0, 0, tzinfo=timezone.utc),
                title="Refleksi sore",
                detail="Menyelesaikan implementasi",
                strength="strong",
            )
        ]


def test_collector_protocol_conformance() -> None:
    # Verifikasi runtime checkable protocol Collector
    assert isinstance(DummyWorkingCollector(), Collector)
    assert isinstance(FailingCollector(), Collector)
    assert isinstance(AnotherWorkingCollector(), Collector)


def test_collector_runner_fault_isolation(caplog: pytest.LogCaptureFixture) -> None:
    target_date = date(2026, 10, 27)
    collectors = [
        DummyWorkingCollector(),
        FailingCollector(),
        AnotherWorkingCollector(),
    ]

    with caplog.at_level(logging.WARNING):
        runner = CollectorRunner(collectors)
        evidence_list = runner.run(target_date)

    # Bukti dari DummyWorkingCollector dan AnotherWorkingCollector berhasil dikumpulkan
    assert len(evidence_list) == 3
    assert evidence_list[0].title == "Commit 1"
    assert evidence_list[1].title == "Commit 2"
    assert evidence_list[2].title == "Refleksi sore"

    # Kegagalan FailingCollector dicatat tanpa mematikan proses
    assert len(runner.failures) == 1
    failure = runner.failures[0]
    assert failure.collector_name == "failing_browser"
    assert failure.error_type == "PermissionError"
    assert "Browser history database locked" in failure.error_message

    # Structured warning dicatat pada logger
    assert "Collector failing_browser gagal mengumpulkan data" in caplog.text
    assert "PermissionError" in caplog.text


def test_run_collectors_convenience_function() -> None:
    target_date = date(2026, 10, 27)
    results = run_collectors([DummyWorkingCollector()], target_date)
    assert len(results) == 2
