"""Unit tests for dashboard service logic."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from magang_log.models import EntryRecord, RunRecord, Status
from magang_log.server.services.dashboard_service import (
    CreateNoteRequest,
    create_reflection_note,
    get_today_status,
)
from magang_log.store import LedgerStore


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "state.db"
    LedgerStore(db_path=db_file)
    return db_file


def test_get_today_status_evaluated_with_draft(test_db: Path) -> None:
    store = LedgerStore(db_path=test_db)
    target = date(2026, 11, 9)
    store.save_entry(
        EntryRecord(
            work_date=target,
            draft_json='{"kehadiran": "Hadir", "aktivitas": "Testing"}',
        )
    )

    res = get_today_status(target_date=target, store=store)
    assert res["status"] == "DRAFTED"
    assert res["needs_user_action"] is True
    assert res["has_submitted_entry"] is False


def test_get_today_status_evaluated_with_approved(test_db: Path) -> None:
    store = LedgerStore(db_path=test_db)
    target = date(2026, 11, 9)
    store.save_entry(
        EntryRecord(
            work_date=target,
            draft_json='{"kehadiran": "Hadir"}',
            approved_json='{"kehadiran": "Hadir"}',
            approved_at=datetime.now(timezone.utc),
        )
    )

    res = get_today_status(target_date=target, store=store)
    assert res["status"] == "APPROVED"
    assert res["needs_user_action"] is False


def test_create_reflection_note_validation() -> None:
    with pytest.raises(ValueError, match="Note content must not be empty"):
        CreateNoteRequest(work_date="2026-11-09", category="aktivitas", note="   ")

    with pytest.raises(ValueError, match="Invalid work_date format"):
        CreateNoteRequest(work_date="invalid-date", category="aktivitas", note="Valid text")


def test_create_reflection_note_transitions_perlu_input(test_db: Path) -> None:
    store = LedgerStore(db_path=test_db)
    target = date(2026, 11, 9)

    # Seed PERLU_INPUT run
    store.record_run(
        RunRecord(
            run_id="run-1",
            work_date=target,
            stage="EVIDENCE",
            status=Status.PERLU_INPUT,
            started_at=datetime.now(timezone.utc),
        )
    )

    req = CreateNoteRequest(
        work_date="2026-11-09",
        category="kendala",
        note="Jaringan kantor sempat terputus pada pukul 14:00.",
        db=str(test_db),
    )
    result = create_reflection_note(req, store=store)
    assert result["success"] is True

    # Latest run should be transitioned from PERLU_INPUT
    runs = store.get_runs_for_date(target)
    assert len(runs) == 2
    assert runs[-1].status == Status.PERLU_REVIEW
