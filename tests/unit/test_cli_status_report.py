"""Unit test untuk perintah CLI magang-log status, report, submit, dan CliRunner."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from magang_log.cli import (
    CliRunner,
    calculate_median,
    calculate_percentile,
    main,
)
from magang_log.models import EntryRecord, RunRecord, Status
from magang_log.store import LedgerStore


def test_calculate_percentile_and_median() -> None:
    # Kasus daftar kosong
    assert calculate_percentile([], 95.0) == 0.0
    assert calculate_median([]) == 0.0

    # Kasus nilai tunggal
    assert calculate_percentile([100.0], 95.0) == 100.0
    assert calculate_median([100.0]) == 100.0

    # Kasus nilai banyak
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert calculate_median(values) == 55.0
    assert calculate_percentile(values, 50.0) == 55.0
    assert calculate_percentile(values, 95.0) == 95.5


def test_cli_runner_invoke_help() -> None:
    runner = CliRunner()
    result = runner.invoke(["--help"])

    assert result.exit_code == 0
    assert "magang-log" in result.output or "magang-portal" in result.output
    assert "status" in result.output
    assert "report" in result.output
    assert "note" in result.output
    assert "submit" in result.output
    assert "export" in result.output


def test_cli_runner_invoke_with_app_callable() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "usage:" in result.stdout.lower()


def test_cli_status_command_json_and_badges(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    base_date = date(2026, 10, 28)  # Rabu

    # 1. Hari dengan entri disetujui & terkirim -> [TERKIRIM]
    d_terkirim = base_date - timedelta(days=1)  # 2026-10-27 (Selasa)
    store.save_entry(
        EntryRecord(
            work_date=d_terkirim,
            draft_json=json.dumps({"aktivitas": "Coding portal"}),
            approved_json=json.dumps({"aktivitas": "Coding portal disetujui"}),
            portal_status="SUDAH_TERKIRIM",
            submitted_at=datetime.now(),
            verified_at=datetime.now(),
        )
    )

    # 2. Hari dengan draf belum disetujui -> [REVIEW]
    d_review = base_date - timedelta(days=2)  # 2026-10-26 (Senin)
    store.save_entry(
        EntryRecord(
            work_date=d_review,
            draft_json=json.dumps({"aktivitas": "Review draf"}),
        )
    )

    # 3. Hari akhir pekan -> [LIBUR]
    # 2026-10-25 adalah Minggu

    # 4. Hari dengan run status PERLU_INPUT -> [INPUT]
    d_input = base_date - timedelta(days=5)
    store.record_run(
        RunRecord(
            run_id="run-input",
            work_date=d_input,
            stage="COLLECTED",
            status=Status.PERLU_INPUT,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
    )

    # 5. Hari dengan run status GAGAL -> [GAGAL]
    d_gagal = base_date - timedelta(days=6)
    store.record_run(
        RunRecord(
            run_id="run-gagal",
            work_date=d_gagal,
            stage="SUBMIT",
            status=Status.GAGAL,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            error_code="NETWORK_ERROR",
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        [
            "status",
            "--days",
            "7",
            "--date",
            base_date.isoformat(),
            "--db",
            str(db_path),
            "--json",
        ]
    )

    assert result.exit_code == 0
    items = json.loads(result.stdout)
    assert len(items) == 7

    badge_map = {item["date"]: item["badge"] for item in items}
    assert badge_map[d_terkirim.isoformat()] == "[TERKIRIM]"
    assert badge_map[d_review.isoformat()] == "[REVIEW]"
    assert badge_map[(base_date - timedelta(days=3)).isoformat()] == "[LIBUR]"  # Minggu
    assert badge_map[d_input.isoformat()] == "[INPUT]"
    assert badge_map[d_gagal.isoformat()] == "[GAGAL]"


def test_cli_status_terminal_table_output(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    base_date = date(2026, 10, 28)

    runner = CliRunner()
    result = runner.invoke(
        [
            "status",
            "--days",
            "5",
            "--date",
            base_date.isoformat(),
            "--db",
            str(db_path),
        ]
    )

    assert result.exit_code == 0
    assert "AUDIT STATUS KALENDER LOGBOOK (5 HARI TERAKHIR)" in result.stdout
    assert "TANGGAL" in result.stdout
    assert "STATUS BADGE" in result.stdout
    assert "Ringkasan:" in result.stdout


def test_cli_report_command_json_and_aggregations(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    base_date = date(2026, 10, 28)

    # Tambah beberapa run record
    store.record_run(
        RunRecord(
            run_id="run-01",
            work_date=base_date - timedelta(days=1),
            stage="FINISHED",
            status=Status.BERHASIL,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            tokens_in=1500,
            tokens_out=400,
            duration_ms=1200,
        )
    )
    store.record_run(
        RunRecord(
            run_id="run-02",
            work_date=base_date - timedelta(days=2),
            stage="FINISHED",
            status=Status.SUDAH_TERKIRIM,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            tokens_in=2000,
            tokens_out=500,
            duration_ms=1800,
        )
    )
    store.record_run(
        RunRecord(
            run_id="run-03",
            work_date=base_date - timedelta(days=3),
            stage="FAILED",
            status=Status.GAGAL,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            tokens_in=500,
            tokens_out=0,
            duration_ms=800,
            error_code="TIMEOUT",
        )
    )

    # Tambah entri dengan rasio edit
    store.save_entry(
        EntryRecord(
            work_date=base_date - timedelta(days=1),
            draft_json=json.dumps({"aktivitas": "Draft 1"}),
            approved_json=json.dumps({"aktivitas": "Draft 1 approved"}),
            edit_ratio=0.10,
        )
    )
    store.save_entry(
        EntryRecord(
            work_date=base_date - timedelta(days=2),
            draft_json=json.dumps({"aktivitas": "Draft 2"}),
            approved_json=json.dumps({"aktivitas": "Draft 2 approved"}),
            edit_ratio=0.20,
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        [
            "report",
            "--days",
            "10",
            "--date",
            base_date.isoformat(),
            "--db",
            str(db_path),
            "--json",
        ]
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["total_runs"] == 3
    assert data["successful_runs"] == 2
    assert data["failed_runs"] == 1
    assert data["success_rate_pct"] == 66.7
    assert data["tokens"]["tokens_in"] == 4000
    assert data["tokens"]["tokens_out"] == 900
    assert data["tokens"]["total"] == 4900
    assert data["durations_ms"]["p50"] == 1200.0
    assert data["edit_ratio"]["median"] == 0.15


def test_cli_report_terminal_output(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    base_date = date(2026, 10, 28)

    runner = CliRunner()
    result = runner.invoke(
        [
            "report",
            "--days",
            "20",
            "--date",
            base_date.isoformat(),
            "--db",
            str(db_path),
        ]
    )

    assert result.exit_code == 0
    assert "OPERATIONAL RELIABILITY REPORT (20 HARI TERAKHIR)" in result.stdout
    assert "METRIK EKSEKUSI PIPELINE:" in result.stdout
    assert "KONSUMSI TOKEN LLM:" in result.stdout
    assert "KUALITAS DRAF (EDIT RATIO):" in result.stdout


def test_cli_note_with_type_flag(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    runner = CliRunner()

    result = runner.invoke(
        [
            "note",
            "Refleksi menggunakan alias --type",
            "--type",
            "pembelajaran",
            "--date",
            "2026-10-28",
            "--db",
            str(db_path),
        ]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "BERHASIL"
    assert payload["kind"] == "pembelajaran"
    assert payload["text"] == "Refleksi menggunakan alias --type"

    store = LedgerStore(db_path=db_path)
    notes = store.get_notes_for_date(date(2026, 10, 28))
    assert len(notes) == 1
    assert notes[0].kind == "pembelajaran"


def test_cli_submit_loads_from_ledger_when_entry_not_specified(tmp_path: Path) -> None:
    from unittest.mock import MagicMock, patch

    from magang_log.portal.playwright_portal import PortalResult

    db_path = tmp_path / "state.db"
    target_date = date(2026, 10, 28)
    store = LedgerStore(db_path=db_path)

    runner = CliRunner()

    # 1. Ketika tidak ada entri disetujui di ledger -> kode keluar 10 (PERLU_TINDAKAN)
    res_missing = runner.invoke(
        [
            "submit",
            "--date",
            target_date.isoformat(),
            "--db",
            str(db_path),
            "--dry-run",
        ]
    )
    assert res_missing.exit_code == 10
    assert "Tidak ditemukan entri yang disetujui" in res_missing.stderr

    # 2. Ketika ada entri yang disetujui di ledger -> berhasil dimuat dan diproses dry-run
    store.save_entry(
        EntryRecord(
            work_date=target_date,
            draft_json=json.dumps({"aktivitas": "Draft aktivitas"}),
            approved_json=json.dumps(
                {
                    "aktivitas": "Aktivitas disetujui dari database",
                    "pembelajaran": "Pembelajaran dari database",
                    "kendala": "Tidak ada kendala",
                    "kehadiran": "Hadir",
                }
            ),
            approved_at=datetime.now(),
        )
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        mock_portal = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = mock_portal
        mock_portal.submit.return_value = PortalResult(
            status=Status.DRYRUN,
            note="Simulasi dry-run sukses",
            screenshots=[],
            traces=[],
        )

        res_ok = runner.invoke(
            [
                "submit",
                "--date",
                target_date.isoformat(),
                "--db",
                str(db_path),
                "--dry-run",
            ]
        )
        assert res_ok.exit_code == 0
        assert mock_portal.submit.called
        called_entry = mock_portal.submit.call_args[0][0]
        assert called_entry.work_date == target_date
        assert called_entry.aktivitas == "Aktivitas disetujui dari database"
