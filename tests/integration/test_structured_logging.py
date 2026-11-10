"""Integration tests untuk Structured Logging Engine terintegrasi dengan PipelineCoordinator dan CLI."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from magang_log import cli
from magang_log.gates import CalendarGate, HolidayProvider, PreflightGate
from magang_log.logger import StructuredLogger
from magang_log.models import EXIT_CODES, Status
from magang_log.pipeline import PipelineCoordinator, PipelineState
from magang_log.store import LedgerStore


def test_pipeline_coordinator_emits_structured_logs(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    runs_dir = tmp_path / "runs"
    log_file = tmp_path / "logs" / "magang-log.jsonl"

    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},  # Senin - Jumat
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)
    logger = StructuredLogger(log_file=log_file, auto_rotate=False)

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        artifacts_dir=runs_dir,
        logger=logger,
    )

    # 1. Jalankan tanggal hari Minggu (2026-10-25) -> LIBUR
    res = coordinator.run(target_date=date(2026, 10, 25))
    assert res.status == Status.LIBUR
    assert res.exit_code == 0

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["run_id"] == res.run_id
    assert entry["work_date"] == "2026-10-25"
    assert entry["stage"] == PipelineState.LIBUR.value
    assert entry["status"] == "LIBUR"
    assert entry["level"] == "INFO"
    assert entry["duration_ms"] >= 0
    assert entry["tokens_in"] == 0
    assert entry["tokens_out"] == 0
    assert entry["error_code"] is None

    # Pastikan TIDAK ADA bocoran teks logbook dalam output JSON
    for forbidden in ("aktivitas", "pembelajaran", "kendala", "draft", "password", "token"):
        assert forbidden not in entry


def test_pipeline_coordinator_logs_unexpected_exception_as_error(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    runs_dir = tmp_path / "runs"
    log_file = tmp_path / "logs" / "magang-log.jsonl"

    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)
    logger = StructuredLogger(log_file=log_file, auto_rotate=False)

    # Simulasikan collector yang melempar exception tak terduga
    failing_collector = MagicMock()
    failing_collector.collect.side_effect = RuntimeError("Koneksi git crash fatal")

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        collector=failing_collector,
        artifacts_dir=runs_dir,
        logger=logger,
    )

    # 2026-10-26 adalah Senin (workday)
    res = coordinator.run(target_date=date(2026, 10, 26))
    assert res.status == Status.GAGAL
    assert res.exit_code == 1
    assert "Koneksi git crash fatal" in (res.note or "")

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["level"] == "ERROR"
    assert entry["status"] == "GAGAL"
    assert entry["error_code"] == "RuntimeError"


def test_cli_main_exit_code_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Status string dikonversi ke kode keluar integer standar
    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=lambda args: Status.BERHASIL)
    ))
    assert cli.main([]) == 0

    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=lambda args: Status.PERLU_REVIEW)
    ))
    assert cli.main([]) == 10

    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=lambda args: Status.LOGIN_DIPERLUKAN)
    ))
    assert cli.main([]) == 20

    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=lambda args: Status.VALIDATION_ERROR)
    ))
    assert cli.main([]) == 30

    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=lambda args: Status.GAGAL)
    ))
    assert cli.main([]) == 40

    # 2. Crash tak terduga ditangkap dan menghasilkan kode keluar 1 (CRASH)
    def _crash_func(args):
        raise ValueError("Simulasi unhandled fatal crash")

    monkeypatch.setattr(cli, "build_parser", lambda: MagicMock(
        parse_args=lambda argv: MagicMock(func=_crash_func)
    ))
    assert cli.main([]) == EXIT_CODES[Status.CRASH]
    assert cli.main([]) == 1
