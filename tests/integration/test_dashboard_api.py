"""Integration tests for LocalDashboard status, notes, and evidence feed API."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from magang_log.models import EntryRecord, NoteRecord
from magang_log.server.app import create_app
from magang_log.store import LedgerStore


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "state.db"
    LedgerStore(db_path=db_file)
    return db_file


def test_get_status_today_workday_no_entries(client: TestClient, test_db: Path) -> None:
    # Set today as Monday
    today_iso = "2026-11-09"  # Monday
    response = client.get(f"/api/status/today?date={today_iso}&db={test_db}")
    assert response.status_code == 200
    data = response.json()
    assert data["target_date"] == today_iso
    assert data["is_workday"] is True
    assert data["is_holiday"] is False
    assert data["has_submitted_entry"] is False
    assert data["status"] in ("PERLU_INPUT", "GATED")


def test_get_status_today_holiday(client: TestClient, test_db: Path) -> None:
    # Weekend / Sunday
    sunday_iso = "2026-11-08"
    response = client.get(f"/api/status/today?date={sunday_iso}&db={test_db}")
    assert response.status_code == 200
    data = response.json()
    assert data["target_date"] == sunday_iso
    assert data["is_holiday"] is True
    assert data["status"] == "LIBUR"
    assert data["needs_user_action"] is False


def test_get_status_today_already_submitted(client: TestClient, test_db: Path) -> None:
    target = date(2026, 11, 9)
    store = LedgerStore(db_path=test_db)
    store.save_entry(
        EntryRecord(
            work_date=target,
            draft_json="{}",
            portal_status="SUDAH_TERKIRIM",
            submitted_at=datetime.now(timezone.utc),
        )
    )

    response = client.get(f"/api/status/today?date={target.isoformat()}&db={test_db}")
    assert response.status_code == 200
    data = response.json()
    assert data["has_submitted_entry"] is True
    assert data["status"] == "SUDAH_TERKIRIM"
    assert data["needs_user_action"] is False


def test_post_notes_success(client: TestClient, test_db: Path) -> None:
    payload = {
        "work_date": "2026-11-09",
        "category": "aktivitas",
        "note": "Mengerjakan integrasi REST API backend untuk dashboard lokal.",
        "db": str(test_db),
    }
    response = client.post("/api/notes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "note_id" in data
    assert "created_at" in data

    # Verify stored in SQLite
    store = LedgerStore(db_path=test_db)
    notes = store.get_notes_for_date(date(2026, 11, 9))
    assert len(notes) == 1
    assert notes[0].kind == "aktivitas"
    assert "Mengerjakan integrasi" in notes[0].text


def test_post_notes_invalid_category(client: TestClient, test_db: Path) -> None:
    payload = {
        "work_date": "2026-11-09",
        "category": "invalid_category",
        "note": "Catatan tanpa kategori valid",
        "db": str(test_db),
    }
    response = client.post("/api/notes", json=payload)
    assert response.status_code == 422


def test_post_notes_empty_note(client: TestClient, test_db: Path) -> None:
    payload = {
        "work_date": "2026-11-09",
        "category": "aktivitas",
        "note": "   ",
        "db": str(test_db),
    }
    response = client.post("/api/notes", json=payload)
    assert response.status_code == 422


def test_get_evidence_today_returns_items(client: TestClient, test_db: Path) -> None:
    # Seed a note so evidence items are populated
    store = LedgerStore(db_path=test_db)
    store.add_note(
        NoteRecord(
            work_date=date(2026, 11, 9),
            kind="aktivitas",
            text="Implementasi dashboard controller dan middleware loopback.",
            created_at=datetime.now(timezone.utc),
        )
    )

    response = client.get(f"/api/evidence/today?date=2026-11-09&db={test_db}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1

    first = data["items"][0]
    assert "id" in first
    assert "source" in first
    assert "kind" in first
    assert "ts" in first
    assert "title" in first
    assert "detail" in first
    assert first["strength"] in ("strong", "weak")
