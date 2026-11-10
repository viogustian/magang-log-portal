"""Unit test untuk perintah CLI magang-log note."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from magang_log.cli import main
from magang_log.store import LedgerStore


def test_cli_note_command_default_today(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "state.db"
    today = date.today()

    exit_code = main(
        [
            "note",
            "Mengerjakan fitur notes collector.",
            "--kind",
            "aktivitas",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["status"] == "BERHASIL"
    assert payload["work_date"] == today.isoformat()
    assert payload["kind"] == "aktivitas"
    assert payload["text"] == "Mengerjakan fitur notes collector."
    assert "note_id" in payload

    # Verifikasi langsung ke database SQLite
    store = LedgerStore(db_path=db_path)
    notes = store.get_notes_for_date(today)
    assert len(notes) == 1
    assert notes[0].kind == "aktivitas"
    assert notes[0].text == "Mengerjakan fitur notes collector."
    assert notes[0].work_date == today


def test_cli_note_command_explicit_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "state.db"
    target_date = date(2026, 10, 20)

    exit_code = main(
        [
            "note",
            "Terkendala koneksi timeout pada API staging.",
            "--kind",
            "kendala",
            "--date",
            "2026-10-20",
            "--db",
            str(db_path),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["status"] == "BERHASIL"
    assert payload["work_date"] == "2026-10-20"
    assert payload["kind"] == "kendala"
    assert payload["text"] == "Terkendala koneksi timeout pada API staging."

    store = LedgerStore(db_path=db_path)
    notes = store.get_notes_for_date(target_date)
    assert len(notes) == 1
    assert notes[0].kind == "kendala"
    assert notes[0].text == "Terkendala koneksi timeout pada API staging."


def test_cli_note_invalid_kind(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "note",
                "Catatan sembarang",
                "--kind",
                "invalid_kind",
                "--db",
                str(db_path),
            ]
        )

    assert exc_info.value.code != 0
