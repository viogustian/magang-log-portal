"""Integration test untuk Unified CLI `magang-log`."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from magang_log.cli import CliRunner
from magang_log.models import EntryRecord, RunRecord, Status
from magang_log.portal.session import LoginRequired
from magang_log.store import LedgerStore


def test_unified_cli_help_discovery_all_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(["--help"])

    assert result.exit_code == 0
    # Pastikan seluruh 10 subcommand PRD/Issue terdaftar di help
    expected_subcommands = [
        "note",
        "run",
        "review",
        "submit",
        "login",
        "doctor",
        "preview-payload",
        "status",
        "export",
        "report",
    ]
    for cmd in expected_subcommands:
        assert cmd in result.output, f"Subcommand '{cmd}' tidak ditemukan di help output"


def test_unified_cli_subcommand_individual_help() -> None:
    runner = CliRunner()
    subcommands = [
        ("note", ["--type", "--kind"]),
        ("run", ["--mode", "--dry-run", "--resume"]),
        ("review", ["--date"]),
        ("submit", ["--dry-run", "--entry", "--date"]),
        ("login", ["--channel"]),
        ("doctor", ["--portal", "--json"]),
        ("preview-payload", ["--date"]),
        ("status", ["--days", "--json"]),
        ("export", ["--output", "--from", "--to"]),
        ("report", ["--days", "--json"]),
    ]

    for subcmd, flags in subcommands:
        res = runner.invoke([subcmd, "--help"])
        assert res.exit_code == 0
        for flag in flags:
            assert flag in res.output, f"Flag '{flag}' tidak ditemukan di '{subcmd} --help'"


def test_unified_cli_exit_code_contract(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "state.db"

    # 1. Exit code 0: status / report / export
    res_status = runner.invoke(["status", "--days", "3", "--db", str(db_path)])
    assert res_status.exit_code == 0

    res_report = runner.invoke(["report", "--days", "5", "--db", str(db_path)])
    assert res_report.exit_code == 0

    res_export = runner.invoke(
        ["export", "-o", str(tmp_path / "out.md"), "--db", str(db_path)]
    )
    assert res_export.exit_code == 0

    # 2. Exit code 10: PERLU_TINDAKAN / PERLU_INPUT
    res_submit = runner.invoke(
        ["submit", "--date", "2026-10-28", "--db", str(db_path), "--dry-run"]
    )
    assert res_submit.exit_code == 10

    # 3. Exit code 20: LOGIN_DIPERLUKAN
    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        mock_portal = mock_portal_cls.return_value.__enter__.return_value
        mock_portal.check.side_effect = LoginRequired("Sesi portal habis.")
        res_check = runner.invoke(
            ["check", "--date", "2026-10-28", "--auth-state", str(tmp_path / "missing.json")]
        )
        assert res_check.exit_code == 20

    # 4. Exit code 40: GAGAL
    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        mock_portal = mock_portal_cls.return_value.__enter__.return_value
        mock_portal.check.return_value = {
            "date": "2026-10-28",
            "login": True,
            "error": "GAGAL (Element not found)",
            "all_selectors_healthy": False,
        }
        res_check_fail = runner.invoke(["check", "--date", "2026-10-28"])
        assert res_check_fail.exit_code == 40


def test_unified_cli_error_handling_without_verbose(tmp_path: Path) -> None:
    runner = CliRunner()

    with patch("magang_log.cli.cmd_status") as mock_status:
        mock_status.side_effect = RuntimeError("Database file corrupt or inaccessible")

        # Tanpa --verbose: pesan error bersih, tanpa stack trace
        result = runner.invoke(["status"])
        assert result.exit_code == 1
        assert "Error: Database file corrupt or inaccessible" in result.stderr
        assert "Traceback (most recent call last):" not in result.stderr


def test_unified_cli_error_handling_with_verbose(tmp_path: Path) -> None:
    runner = CliRunner()

    with patch("magang_log.cli.cmd_status") as mock_status:
        mock_status.side_effect = RuntimeError("Database file corrupt or inaccessible")

        # Dengan --verbose: menampilkan stack trace penuh
        result = runner.invoke(["--verbose", "status"])
        assert result.exit_code == 1
        assert "Traceback (most recent call last):" in result.stderr
        assert "Database file corrupt or inaccessible" in result.stderr


def test_unified_cli_export_command_generates_markdown(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    # Simpan entri yang telah disetujui
    work_date = date(2026, 10, 20)
    store.save_entry(
        EntryRecord(
            work_date=work_date,
            draft_json=json.dumps({"aktivitas": "Draft aktivitas"}),
            approved_json=json.dumps(
                {
                    "aktivitas": "Implementasi endpoint GraphQL untuk portal.",
                    "pembelajaran": "Memahami schema stitching dan caching di backend.",
                    "kendala": "Tidak ada kendala yang menghambat.",
                    "kehadiran": "Hadir",
                }
            ),
            approved_at=datetime(2026, 10, 20, 17, 30),
            portal_status="SUDAH_TERKIRIM",
        )
    )

    output_file = tmp_path / "logbook_export.md"
    runner = CliRunner()
    result = runner.invoke(
        [
            "export",
            "--output",
            str(output_file),
            "--from",
            "2026-10-01",
            "--to",
            "2026-10-31",
            "--db",
            str(db_path),
        ]
    )

    assert result.exit_code == 0
    assert output_file.exists()

    content = output_file.read_text(encoding="utf-8")
    assert "Logbook Magang" in content
    assert "2026-10-20" in content
    assert "Implementasi endpoint GraphQL" in content
    assert "Memahami schema stitching" in content


def test_unified_cli_status_and_report_integration(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)
    today = date(2026, 10, 28)

    # Isi ledger dengan data historis
    for i in range(5):
        d = today - timedelta(days=i)
        store.record_run(
            RunRecord(
                run_id=f"run-{d.strftime('%Y%m%d')}",
                work_date=d,
                stage="FINISHED",
                status=Status.BERHASIL,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                tokens_in=1000,
                tokens_out=250,
                duration_ms=1500,
            )
        )
        store.save_entry(
            EntryRecord(
                work_date=d,
                draft_json=json.dumps({"aktivitas": f"Pekerjaan hari {i}"}),
                approved_json=json.dumps({"aktivitas": f"Pekerjaan hari {i} disetujui"}),
                approved_at=datetime.now(),
                portal_status="SUDAH_TERKIRIM",
                edit_ratio=0.05 * i,
            )
        )

    runner = CliRunner()

    # 1. Jalankan audit status
    status_res = runner.invoke(
        ["status", "--days", "5", "--date", today.isoformat(), "--db", str(db_path)]
    )
    assert status_res.exit_code == 0
    assert "[TERKIRIM]" in status_res.stdout
    assert "5 Terkirim" in status_res.stdout

    # 2. Jalankan laporan keandalan operasional
    report_res = runner.invoke(
        ["report", "--days", "5", "--date", today.isoformat(), "--db", str(db_path), "--json"]
    )
    assert report_res.exit_code == 0
    rep_data = json.loads(report_res.stdout)
    assert rep_data["total_runs"] == 5
    assert rep_data["successful_runs"] == 5
    assert rep_data["success_rate_pct"] == 100.0
    assert rep_data["tokens"]["tokens_in"] == 5000
    assert rep_data["tokens"]["tokens_out"] == 1250
