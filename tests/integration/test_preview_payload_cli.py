"""Integration tests untuk perintah CLI preview-payload dan gatekeeper kekuatan bukti."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from magang_log.cli import main
from magang_log.models import NoteRecord, Status
from magang_log.store import LedgerStore


def test_preview_payload_empty_day_halts_exit_10(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """preview-payload pada hari tanpa bukti harus mencetak diagnostik PERLU_INPUT dan keluar dengan kode 10."""
    db_file = tmp_path / "state.db"
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: false
  notes:
    enabled: true
  browser:
    enabled: false
""",
        encoding="utf-8",
    )

    with patch("magang_log.cli.send_system_notification") as mock_notify:
        exit_code = main(
            [
                "preview-payload",
                "--date",
                "2026-10-27",
                "--config",
                str(config_file),
                "--db",
                str(db_file),
            ]
        )

    assert exit_code == 10
    mock_notify.assert_called_once()

    captured = capsys.readouterr()
    assert "DIAGNOSTIC METADATA - OFFLINE PAYLOAD PREVIEW" in captured.out
    assert "Tanggal Kerja  : 2026-10-27" in captured.out
    assert "Total Bukti    : 0" in captured.out
    assert "Bukti Kuat     : 0 (strong)" in captured.out
    assert "Keputusan Gate : PERLU_INPUT" in captured.out
    assert "FINALIZED DRAFTING PAYLOAD (JSON)" in captured.out

    # Verifikasi status PERLU_INPUT dicatat di ledger runs
    store = LedgerStore(db_path=db_file)
    runs = store.list_runs(target_date=date(2026, 10, 27))
    assert len(runs) >= 1
    assert runs[-1].status == Status.PERLU_INPUT
    assert runs[-1].error_code == "INSUFFICIENT_EVIDENCE"


def test_preview_payload_with_strong_evidence_succeeds(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """preview-payload pada hari dengan bukti kuat (catatan refleksi) harus keluar dengan kode 0."""
    db_file = tmp_path / "state.db"
    store = LedgerStore(db_path=db_file)
    # Tambah catatan manual sebagai bukti kuat
    store.add_note(
        NoteRecord(
            work_date=date(2026, 10, 27),
            kind="aktivitas",
            text="Mengimplementasikan modul privacy sanitization engine",
            created_at=datetime.now(),
        )
    )

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: false
  notes:
    enabled: true
  browser:
    enabled: false
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "preview-payload",
            "--date",
            "2026-10-27",
            "--config",
            str(config_file),
            "--db",
            str(db_file),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Keputusan Gate : PROCEED" in captured.out
    assert "Bukti Kuat     : 1 (strong)" in captured.out

    # Ekstrak bagian JSON payload
    json_start = captured.out.find("{")
    assert json_start != -1
    payload_json = json.loads(captured.out[json_start:])
    assert payload_json["work_date"] == "2026-10-27"
    assert len(payload_json["evidence"]) == 1
    assert payload_json["evidence"][0]["source"] == "note"
    assert payload_json["evidence"][0]["strength"] == "strong"
    assert "privacy sanitization" in payload_json["evidence"][0]["title"]


def test_preview_payload_send_to_llm_toggle_excludes_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifikasi send_to_llm: false mengecualikan sumber terkait dari payload JSON yang dicetak."""
    db_file = tmp_path / "state.db"
    store = LedgerStore(db_path=db_file)
    store.add_note(
        NoteRecord(
            work_date=date(2026, 10, 27),
            kind="aktivitas",
            text="Bekerja membuat sistem integrasi",
            created_at=datetime.now(),
        )
    )

    # Buat file database riwayat peramban palsu
    history_db = tmp_path / "History"
    import sqlite3

    conn = sqlite3.connect(str(history_db))
    conn.execute(
        "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INTEGER, last_visit_time INTEGER)"
    )
    from datetime import timezone

    chrome_ts = int(
        (datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc).timestamp() + 11644473600)
        * 1_000_000
    )
    conn.execute(
        "INSERT INTO urls (url, title, visit_count, last_visit_time) VALUES (?, ?, ?, ?)",
        ("https://github.com/org/repo/pull/1", "PR Review", 1, chrome_ts),
    )
    conn.commit()
    conn.close()

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
timezone: Asia/Jakarta
workdays: [mon, tue, wed, thu, fri]
sources:
  git:
    enabled: false
  notes:
    enabled: true
  browser:
    enabled: true
    allow_domains: ["github.com"]
    history_files: ["{history_db.as_posix()}"]
    send_to_llm: false
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "preview-payload",
            "--date",
            "2026-10-27",
            "--config",
            str(config_file),
            "--db",
            str(db_file),
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Sumber Dikecualikan: browser (via send_to_llm: false)" in captured.out

    json_start = captured.out.find("{")
    payload_json = json.loads(captured.out[json_start:])
    sources_in_payload = [e["source"] for e in payload_json["evidence"]]
    assert "note" in sources_in_payload
    assert "browser" not in sources_in_payload
    assert "browser" in payload_json["metadata"]["excluded_sources"]
