"""Integration tests for monthly calendar endpoint."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from magang_log.models import EntryRecord
from magang_log.server.app import create_app
from magang_log.store import LedgerStore


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_api_calendar.db"


@pytest.fixture
def client(temp_db: Path) -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_calendar_month_success(client: TestClient, temp_db: Path) -> None:
    response = client.get(f"/api/calendar/month?year=2026&month=10&db={temp_db}")
    assert response.status_code == 200
    data = response.json()
    assert "days" in data
    assert len(data["days"]) == 31
    day1 = data["days"][0]
    assert day1["date"] == "2026-10-01"
    assert day1["day_name"] == "Kamis"
    assert day1["status"] in ("KOSONG", "LIBUR")


def test_get_calendar_month_invalid_params(client: TestClient) -> None:
    # Invalid month 13
    response = client.get("/api/calendar/month?year=2026&month=13")
    assert response.status_code == 422


def test_get_calendar_month_with_persisted_entries(client: TestClient, temp_db: Path) -> None:
    store = LedgerStore(db_path=temp_db)
    d = date(2026, 10, 5)  # Monday
    store.save_entry(
        EntryRecord(
            work_date=d,
            draft_json=json.dumps({"aktivitas": "testing"}),
            portal_status="BERHASIL",
            submitted_at=None,
        )
    )

    response = client.get(f"/api/calendar/month?year=2026&month=10&db={temp_db}")
    assert response.status_code == 200
    data = response.json()
    oct5 = next(day for day in data["days"] if day["date"] == "2026-10-05")
    assert oct5["status"] == "BERHASIL"
    assert oct5["entry_id"] == "entry-2026-10-05"
