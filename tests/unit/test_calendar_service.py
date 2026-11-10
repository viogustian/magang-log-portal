"""Unit tests for monthly calendar inspection service logic."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from magang_log.models import EntryRecord
from magang_log.server.services.calendar_service import get_month_calendar
from magang_log.store import LedgerStore


@pytest.fixture
def store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(db_path=tmp_path / "test_calendar.db")


def test_get_month_calendar_structure(store: LedgerStore) -> None:
    # October 2026 has 31 days
    days = get_month_calendar(year=2026, month=10, store=store)
    assert len(days) == 31
    assert days[0]["date"] == "2026-10-01"
    assert days[0]["day_name"] == "Kamis"
    # Oct 1, 2026 is Thursday (workday, no entry -> KOSONG)
    assert days[0]["status"] == "KOSONG"
    assert days[0]["entry_id"] is None

    # Oct 3, 2026 is Saturday (weekend -> LIBUR)
    assert days[2]["date"] == "2026-10-03"
    assert days[2]["day_name"] == "Sabtu"
    assert days[2]["status"] == "LIBUR"


def test_get_month_calendar_with_entries(store: LedgerStore) -> None:
    # Add a submitted entry on Thursday Oct 1
    d1 = date(2026, 10, 1)
    store.save_entry(
        EntryRecord(
            work_date=d1,
            draft_json=json.dumps({"aktivitas": "testing"}),
            portal_status="SUDAH_TERKIRIM",
        )
    )

    # Add a pending draft on Friday Oct 2
    d2 = date(2026, 10, 2)
    store.save_entry(
        EntryRecord(
            work_date=d2,
            draft_json=json.dumps({"aktivitas": "testing draft"}),
        )
    )

    days = get_month_calendar(year=2026, month=10, store=store)
    assert days[0]["status"] == "TERKIRIM"
    assert days[0]["entry_id"] == "entry-2026-10-01"

    assert days[1]["status"] == "PENDING"
    assert days[1]["entry_id"] == "entry-2026-10-02"
