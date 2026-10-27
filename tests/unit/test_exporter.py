"""Unit & Integration tests untuk Clean UTF-8 Markdown Logbook Exporter."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log.cli import main
from magang_log.exporter import (
    UTF8_BOM,
    compile_logbook_markdown,
    export_logbook,
    parse_entry_content,
)
from magang_log.models import EntryRecord
from magang_log.store import LedgerStore


def test_parse_entry_content_json() -> None:
    entry = EntryRecord(
        work_date=date(2026, 10, 27),
        draft_json='{"aktivitas": "Draft aktivitas", "pembelajaran": "Draft belajar", "kendala": "Nihil"}',
        approved_json='{"aktivitas": "Final aktivitas", "pembelajaran": "Final belajar", "kendala": "Tidak ada", "kehadiran": "Hadir"}',
    )
    data = parse_entry_content(entry)
    assert data["aktivitas"] == "Final aktivitas"
    assert data["pembelajaran"] == "Final belajar"
    assert data["kendala"] == "Tidak ada"
    assert data["kehadiran"] == "Hadir"


def test_compile_empty_logbook() -> None:
    md = compile_logbook_markdown([])
    assert "# Logbook Magang" in md
    assert "Belum ada entri logbook yang disetujui" in md


def test_compile_logbook_markdown_structure() -> None:
    entries = [
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json="",
            approved_json=json.dumps(
                {
                    "aktivitas": "Membangun modul exporter UTF-8.",
                    "pembelajaran": "Memahami deteksi dan penghindaran Byte Order Mark (BOM).",
                    "kendala": "Tidak ada kendala.",
                    "kehadiran": "Hadir",
                }
            ),
        ),
        EntryRecord(
            work_date=date(2026, 10, 28),
            draft_json="",
            approved_json=json.dumps(
                {
                    "aktivitas": "Integrasi CLI export dengan SQLite ledger.",
                    "pembelajaran": "Penyusunan filter rentang tanggal.",
                    "kendala": "Nihil.",
                    "kehadiran": "Hadir",
                }
            ),
        ),
    ]

    md = compile_logbook_markdown(entries)

    # Date headers with Indonesian day names
    assert "## 2026-10-27 (Selasa)" in md
    assert "## 2026-10-28 (Rabu)" in md

    # Attendance status
    assert "- **Status Kehadiran:** Hadir" in md

    # Structured sections
    assert "### Aktivitas" in md
    assert "Membangun modul exporter UTF-8." in md
    assert "### Pembelajaran" in md
    assert "Memahami deteksi dan penghindaran Byte Order Mark (BOM)." in md
    assert "### Kendala" in md
    assert "Tidak ada kendala." in md

    # Separator between entries
    assert "---" in md

    # Chronological ordering (27 comes before 28)
    idx_27 = md.find("2026-10-27")
    idx_28 = md.find("2026-10-28")
    assert idx_27 < idx_28


def test_export_logbook_strictly_no_bom(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    # Simpan entri terverifikasi
    store.save_entry(
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json="{}",
            approved_json=json.dumps(
                {
                    "aktivitas": "Menulis pengujian UTF-8 tanpa BOM.",
                    "pembelajaran": "Byte Order Mark \ufeff dapat mengacaukan git diff.",
                    "kendala": "Nihil",
                    "kehadiran": "Hadir",
                }
            ),
            approved_at=datetime.now(),
        )
    )

    out_file = tmp_path / "logbook.md"
    exported_path, count = export_logbook(store=store, output_path=out_file)

    assert exported_path == out_file.resolve()
    assert count == 1
    assert out_file.exists()

    # Validasi biner mentah: sama sekali tidak boleh mengandung BOM bytes (\xef\xbb\xbf)
    raw_bytes = out_file.read_bytes()
    assert not raw_bytes.startswith(UTF8_BOM), (
        "File tidak boleh diawali dengan BOM bytes (\\xef\\xbb\\xbf)!"
    )
    assert UTF8_BOM not in raw_bytes, "BOM bytes tidak boleh muncul di mana pun dalam dokumen!"

    # Validasi decoding UTF-8 bersih
    text = raw_bytes.decode("utf-8")
    assert "Menulis pengujian UTF-8 tanpa BOM." in text


def test_export_logbook_overwrite_existing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    store.save_entry(
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json="{}",
            approved_json=json.dumps(
                {"aktivitas": "Konten Baru", "pembelajaran": "Baru", "kendala": "Nihil"}
            ),
            approved_at=datetime.now(),
        )
    )

    out_file = tmp_path / "logbook.md"
    out_file.write_text("KONTEN_LAMA_YANG_HARUS_TERTIMPA", encoding="utf-8")

    export_logbook(store=store, output_path=out_file)
    content = out_file.read_text(encoding="utf-8")
    assert "KONTEN_LAMA_YANG_HARUS_TERTIMPA" not in content
    assert "Konten Baru" in content


def test_export_logbook_date_range_filtering(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    # Simpan entri tanggal 25, 26, 27, 28 Oktober
    for d, act in [
        (date(2026, 10, 25), "Aktivitas 25"),
        (date(2026, 10, 26), "Aktivitas 26"),
        (date(2026, 10, 27), "Aktivitas 27"),
        (date(2026, 10, 28), "Aktivitas 28"),
    ]:
        store.save_entry(
            EntryRecord(
                work_date=d,
                draft_json="{}",
                approved_json=json.dumps({"aktivitas": act, "pembelajaran": "P", "kendala": "K"}),
                approved_at=datetime.now(),
            )
        )

    # 1. Tanpa filter: harus mengambil semua 4 entri
    _, count_all = export_logbook(store, tmp_path / "all.md")
    assert count_all == 4

    # 2. Filter --from 2026-10-26
    out_from = tmp_path / "from.md"
    _, count_from = export_logbook(store, out_from, from_date=date(2026, 10, 26))
    assert count_from == 3
    content_from = out_from.read_text(encoding="utf-8")
    assert "Aktivitas 25" not in content_from
    assert "Aktivitas 26" in content_from
    assert "Aktivitas 28" in content_from

    # 3. Filter --to 2026-10-27
    out_to = tmp_path / "to.md"
    _, count_to = export_logbook(store, out_to, to_date=date(2026, 10, 27))
    assert count_to == 3
    content_to = out_to.read_text(encoding="utf-8")
    assert "Aktivitas 25" in content_to
    assert "Aktivitas 27" in content_to
    assert "Aktivitas 28" not in content_to

    # 4. Filter rentang --from 2026-10-26 --to 2026-10-27
    out_range = tmp_path / "range.md"
    _, count_range = export_logbook(
        store, out_range, from_date=date(2026, 10, 26), to_date=date(2026, 10, 27)
    )
    assert count_range == 2
    content_range = out_range.read_text(encoding="utf-8")
    assert "Aktivitas 26" in content_range
    assert "Aktivitas 27" in content_range
    assert "Aktivitas 25" not in content_range
    assert "Aktivitas 28" not in content_range


def test_cli_export_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)

    store.save_entry(
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json="{}",
            approved_json=json.dumps(
                {
                    "aktivitas": "Eksekusi CLI export.",
                    "pembelajaran": "Memastikan output JSON dan exit code 0.",
                    "kendala": "Nihil",
                    "kehadiran": "Hadir",
                }
            ),
            approved_at=datetime.now(),
        )
    )

    out_file = tmp_path / "exported_logbook.md"

    # Jalankan CLI export
    exit_code = main(
        [
            "export",
            "--db",
            str(db_path),
            "--output",
            str(out_file),
            "--from",
            "2026-10-01",
            "--to",
            "2026-10-31",
        ]
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["status"] == "BERHASIL"
    assert payload["entries_count"] == 1
    assert payload["from_date"] == "2026-10-01"
    assert payload["to_date"] == "2026-10-31"

    assert out_file.exists()
    raw = out_file.read_bytes()
    assert not raw.startswith(UTF8_BOM)
    assert "Eksekusi CLI export." in raw.decode("utf-8")
