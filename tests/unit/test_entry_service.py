"""Unit tests for logbook entry service logic."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from magang_log.drafter.client import FakeModelClient
from magang_log.drafter.models import LogEntryDraft
from magang_log.models import EntryRecord, EvidenceItem, PortalResult, Status
from magang_log.server.services.entry_service import (
    EditEntryRequest,
    approve_and_submit_entry,
    edit_entry,
    get_today_entry,
    regenerate_draft,
)
from magang_log.store import LedgerStore


@pytest.fixture
def store(tmp_path: Path) -> LedgerStore:
    db_file = tmp_path / "test_entry.db"
    return LedgerStore(db_path=db_file)


def test_get_today_entry_not_found(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    result = get_today_entry(target_date=target, store=store)
    assert result is None


def test_get_today_entry_success(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    draft_data = {
        "kehadiran": "Hadir",
        "aktivitas": (
            "Mengembangkan implementasi modul autentikasi portal magang dengan pengujian unit "
            "komprehensif untuk memastikan kepatuhan standar keamanan instansi pemerintah terkait [ev1]."
        ),
        "pembelajaran": (
            "Memahami arsitektur penanganan sesi login portal berbasis token serta penerapan "
            "isolasi hak akses yang aman pada lingkungan produksi instansi pemerintah [ev1]."
        ),
        "kendala": (
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "menyelesaikannya melalui konfigurasi mekanisme exponential backoff retry [ev1]."
        ),
        "evidence_refs": {"aktivitas": ["ev1"]},
        "prompt_version": "v1",
        "model": "gemini-2.5-flash",
    }
    store.save_entry(
        EntryRecord(
            work_date=target,
            draft_json=json.dumps(draft_data),
            prompt_version="v1",
            model="gemini-2.5-flash",
        )
    )

    result = get_today_entry(target_date=target, store=store)
    assert result is not None
    assert result["entry_id"] == "entry-2026-11-09"
    assert result["work_date"] == "2026-11-09"
    assert result["kehadiran"] == "Hadir"
    assert "Mengembangkan implementasi" in result["aktivitas"]
    assert result["validation_passed"] is True
    assert result["validation_errors"] == []
    assert result["status"] == "VALIDATED"


def test_edit_entry_updates_draft(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    req = EditEntryRequest(
        work_date=str(target),
        kehadiran="Hadir",
        aktivitas=(
            "Mengembangkan implementasi modul autentikasi portal magang dengan pengujian unit "
            "komprehensif untuk memastikan kepatuhan standar keamanan instansi pemerintah terkait [ev1]."
        ),
        pembelajaran=(
            "Memahami arsitektur penanganan sesi login portal berbasis token serta penerapan "
            "isolasi hak akses yang aman pada lingkungan produksi instansi pemerintah [ev1]."
        ),
        kendala=(
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "menyelesaikannya melalui konfigurasi mekanisme exponential backoff retry [ev1]."
        ),
    )

    res = edit_entry(req=req, store=store)
    assert res["success"] is True
    assert res["validation_passed"] is True
    assert res["validation_errors"] == []
    assert res["updated_entry"]["kehadiran"] == "Hadir"

    # Verify ledger was updated
    entry_in_db = store.get_entry(target)
    assert entry_in_db is not None
    assert "Mengembangkan implementasi" in entry_in_db.draft_json


def test_regenerate_draft_with_client(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    # Add evidence item
    store.save_evidence(
        [
            EvidenceItem(
                id="ev1",
                work_date=target,
                source="git",
                kind="commit",
                ts="2026-11-09T10:00:00Z",
                title="feat: implement backend API",
                detail="Added FastAPI endpoints",
                strength="strong",
            )
        ]
    )

    fake_draft = LogEntryDraft(
        work_date=target,
        kehadiran="Hadir",
        aktivitas=(
            "Mengembangkan implementasi modul autentikasi portal magang dengan pengujian unit "
            "komprehensif untuk memastikan kepatuhan standar keamanan instansi pemerintah terkait [ev1]."
        ),
        pembelajaran=(
            "Memahami arsitektur penanganan sesi login portal berbasis token serta penerapan "
            "isolasi hak akses yang aman pada lingkungan produksi instansi pemerintah [ev1]."
        ),
        kendala=(
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "menyelesaikannya melalui konfigurasi mekanisme exponential backoff retry [ev1]."
        ),
        evidence_refs={"aktivitas": ["ev1"]},
        prompt_version="v1",
        model="gemini-2.5-flash",
    )
    client = FakeModelClient(response=fake_draft)

    res = regenerate_draft(target_date=target, store=store, drafter_client=client)
    assert res["success"] is True
    assert res["validation_passed"] is True
    assert res["draft"]["work_date"] == "2026-11-09"
    assert "Mengembangkan implementasi" in res["draft"]["aktivitas"]

    # Verify saved in ledger
    saved = store.get_entry(target)
    assert saved is not None
    assert "Mengembangkan implementasi" in saved.draft_json


def test_approve_entry_invalid_draft_fails(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    # Save a draft that violates minimum character count
    invalid_draft = {
        "kehadiran": "Hadir",
        "aktivitas": "pendek",
        "pembelajaran": "pendek",
        "kendala": "pendek",
    }
    store.save_entry(EntryRecord(work_date=target, draft_json=json.dumps(invalid_draft)))

    res = approve_and_submit_entry(target_date=target, store=store)
    assert res["success"] is False
    assert res["final_status"] == "VALIDATION_FAILED"
    assert "error_message" in res


def test_approve_and_submit_success_with_coordinator(store: LedgerStore) -> None:
    target = date(2026, 11, 9)
    valid_draft = {
        "kehadiran": "Hadir",
        "aktivitas": (
            "Mengembangkan implementasi modul autentikasi portal magang dengan pengujian unit "
            "komprehensif untuk memastikan kepatuhan standar keamanan instansi pemerintah terkait [ev1]."
        ),
        "pembelajaran": (
            "Memahami arsitektur penanganan sesi login portal berbasis token serta penerapan "
            "isolasi hak akses yang aman pada lingkungan produksi instansi pemerintah [ev1]."
        ),
        "kendala": (
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "menyelesaikannya melalui konfigurasi mekanisme exponential backoff retry [ev1]."
        ),
        "evidence_refs": {"aktivitas": ["ev1"]},
        "prompt_version": "v1",
        "model": "gemini-2.5-flash",
    }
    store.save_entry(EntryRecord(work_date=target, draft_json=json.dumps(valid_draft)))

    mock_coordinator = MagicMock()
    mock_portal = MagicMock()
    mock_portal.submit.return_value = PortalResult(
        status=Status.BERHASIL,
        note="Entry successfully submitted to MagangHub portal",
    )
    mock_coordinator.portal = mock_portal

    res = approve_and_submit_entry(target_date=target, store=store, coordinator=mock_coordinator)
    assert res["success"] is True
    assert res["final_status"] == "BERHASIL"
    assert res["error_message"] is None

    # Check ledger was updated
    entry = store.get_entry(target)
    assert entry is not None
    assert entry.portal_status == "SUDAH_TERKIRIM"
    assert entry.approved_at is not None
