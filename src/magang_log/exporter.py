"""Modul eksportir logbook ke format Markdown UTF-8 bersih tanpa Byte Order Mark (BOM)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .gates import INDONESIAN_DAY_NAMES
from .models import EntryRecord
from .store import LedgerStore

UTF8_BOM = b"\xef\xbb\xbf"


def parse_entry_content(entry: EntryRecord) -> dict[str, Any]:
    """Mengekstrak bidang aktivitas, pembelajaran, kendala, dan kehadiran dari entri."""
    data: dict[str, Any] = {
        "work_date": entry.work_date,
        "aktivitas": "",
        "pembelajaran": "",
        "kendala": "",
        "kehadiran": "Hadir",
    }
    source_json = entry.approved_json or entry.draft_json
    if source_json:
        try:
            parsed = json.loads(source_json)
            if isinstance(parsed, dict):
                data.update(parsed)
        except (json.JSONDecodeError, TypeError):
            data["aktivitas"] = source_json

    return data


def format_single_entry(entry: EntryRecord) -> str:
    """Memformat satu entri logbook menjadi blok markdown terstruktur."""
    content = parse_entry_content(entry)
    work_date = entry.work_date
    weekday_idx = work_date.weekday()
    day_name = INDONESIAN_DAY_NAMES[weekday_idx]
    kehadiran = content.get("kehadiran") or "Hadir"

    aktivitas = (content.get("aktivitas") or "").strip()
    pembelajaran = (content.get("pembelajaran") or "").strip()
    kendala = (content.get("kendala") or "").strip()

    lines = [
        f"## {work_date.isoformat()} ({day_name})",
        f"- **Status Kehadiran:** {kehadiran}",
        "",
        "### Aktivitas",
        aktivitas if aktivitas else "*(Tidak ada catatan aktivitas)*",
        "",
        "### Pembelajaran",
        pembelajaran if pembelajaran else "*(Tidak ada catatan pembelajaran)*",
        "",
        "### Kendala",
        kendala if kendala else "*(Tidak ada kendala)*",
    ]
    return "\n".join(lines)


def compile_logbook_markdown(entries: list[EntryRecord], title: str = "Logbook Magang") -> str:
    """Mengompilasi daftar entri yang telah disetujui menjadi dokumen Markdown terpadu."""
    header_lines = [
        f"# {title}",
        "",
    ]

    if not entries:
        header_lines.append("*(Belum ada entri logbook yang disetujui)*\n")
        return "\n".join(header_lines)

    body_blocks = [format_single_entry(entry) for entry in entries]
    body = "\n\n---\n\n".join(body_blocks)

    return "\n".join(header_lines) + body + "\n"


def export_logbook(
    store: LedgerStore,
    output_path: str | Path = "logbook.md",
    from_date: date | None = None,
    to_date: date | None = None,
    title: str = "Logbook Magang",
) -> tuple[Path, int]:
    """Mengekspor seluruh entri yang disetujui ke file Markdown dengan encoding UTF-8 bersih tanpa BOM."""
    entries = store.get_approved_entries(from_date=from_date, to_date=to_date)
    markdown_text = compile_logbook_markdown(entries, title=title).replace("\ufeff", "")

    # Enforce strictly clean UTF-8 without BOM bytes anywhere in the output
    raw_bytes = markdown_text.encode("utf-8").replace(UTF8_BOM, b"")

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(raw_bytes)

    return out_file, len(entries)
