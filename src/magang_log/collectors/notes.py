"""Kolektor catatan refleksi manual harian dari database SQLite."""

from __future__ import annotations

from datetime import date, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Evidence, SourceConfig

if TYPE_CHECKING:
    from ..models import NoteRecord
    from ..store import LedgerStore


class NotesCollector:
    """Kolektor bukti aktivitas berbasis catatan refleksi manual harian (tabel notes)."""

    name: str = "notes"

    def __init__(
        self,
        store: LedgerStore | None = None,
        db_path: Path | str | None = None,
    ) -> None:
        self._store = store
        self._db_path = db_path

    def _resolve_store(self, config: SourceConfig = None) -> LedgerStore:
        if self._store is not None:
            return self._store
        from ..store import LedgerStore

        db_path = self._db_path or "data/state.db"
        return LedgerStore(db_path=db_path)

    def collect(self, target_date: date, config: SourceConfig = None) -> list[Evidence]:
        """Mengambil seluruh catatan untuk target_date dan memetakannya menjadi objek Evidence."""
        store = self._resolve_store(config)
        notes: list[NoteRecord] = store.get_notes_for_date(target_date)

        evidence_items: list[Evidence] = []
        for n in notes:
            # Pastikan timestamp UTC
            ts = n.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)

            text = n.text.strip()
            first_line = text.splitlines()[0].strip() if text else f"Catatan {n.kind}"

            ev = Evidence(
                source="note",
                kind=f"note:{n.kind}",
                ts=ts,
                title=first_line,
                detail=text,
                strength="strong",
                work_date=n.work_date,
            )
            evidence_items.append(ev)

        return evidence_items
