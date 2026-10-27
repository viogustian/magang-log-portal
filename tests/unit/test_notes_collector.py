"""Unit test untuk NotesCollector: pemetaan NoteRecord SQLite menjadi Evidence item."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from magang_log.collectors.base import Collector, Evidence, compute_evidence_id
from magang_log.collectors.notes import NotesCollector
from magang_log.models import NoteRecord
from magang_log.store import LedgerStore


@pytest.fixture
def store(tmp_path: Path) -> LedgerStore:
    db_file = tmp_path / "test_notes.db"
    return LedgerStore(db_path=db_file)


def test_notes_collector_protocol_conformance() -> None:
    collector = NotesCollector()
    assert isinstance(collector, Collector)


def test_notes_collector_maps_notes_to_evidence(store: LedgerStore) -> None:
    target_date = date(2026, 10, 27)
    other_date = date(2026, 10, 28)

    # Simpan catatan untuk target_date
    created_at_1 = datetime(2026, 10, 27, 10, 15, 0, tzinfo=timezone.utc)
    created_at_2 = datetime(2026, 10, 27, 14, 30, 0, tzinfo=timezone.utc)
    created_at_3 = datetime(2026, 10, 27, 16, 45, 0, tzinfo=timezone.utc)

    store.add_note(
        NoteRecord(
            work_date=target_date,
            kind="aktivitas",
            text="Mengerjakan modul pengumpul bukti.",
            created_at=created_at_1,
        )
    )
    store.add_note(
        NoteRecord(
            work_date=target_date,
            kind="pembelajaran",
            text="Memahami arsitektur pluggable collector berbasis Protocol.",
            created_at=created_at_2,
        )
    )
    store.add_note(
        NoteRecord(
            work_date=target_date,
            kind="kendala",
            text="Menyesuaikan kompatibilitas skema SQLite lama.",
            created_at=created_at_3,
        )
    )

    # Simpan catatan untuk tanggal lain yang tidak boleh ikut terambil
    store.add_note(
        NoteRecord(
            work_date=other_date,
            kind="aktivitas",
            text="Aktivitas hari esok.",
            created_at=datetime(2026, 10, 28, 9, 0, 0, tzinfo=timezone.utc),
        )
    )

    collector = NotesCollector(store=store)
    evidence_list = collector.collect(target_date)

    assert len(evidence_list) == 3

    # Verifikasi item 1 (aktivitas)
    ev1 = evidence_list[0]
    assert isinstance(ev1, Evidence)
    assert ev1.source == "note"
    assert ev1.kind == "note:aktivitas"
    assert ev1.strength == "strong"
    assert ev1.detail == "Mengerjakan modul pengumpul bukti."
    assert "Mengerjakan modul" in ev1.title
    assert len(ev1.id) == 10
    assert ev1.id == compute_evidence_id(
        source="note",
        kind="note:aktivitas",
        ts=ev1.ts,
        title=ev1.title,
    )

    # Verifikasi item 2 (pembelajaran)
    ev2 = evidence_list[1]
    assert ev2.source == "note"
    assert ev2.kind == "note:pembelajaran"
    assert ev2.strength == "strong"
    assert ev2.detail == "Memahami arsitektur pluggable collector berbasis Protocol."

    # Verifikasi item 3 (kendala)
    ev3 = evidence_list[2]
    assert ev3.source == "note"
    assert ev3.kind == "note:kendala"
    assert ev3.strength == "strong"
    assert ev3.detail == "Menyesuaikan kompatibilitas skema SQLite lama."


def test_notes_collector_empty_date(store: LedgerStore) -> None:
    collector = NotesCollector(store=store)
    empty_list = collector.collect(date(2026, 10, 1))
    assert empty_list == []
