"""Integration tests for LocalDashboard entry editing, drafting, and approval API."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from magang_log.drafter.models import LogEntryDraft
from magang_log.models import EntryRecord
from magang_log.server.app import create_app
from magang_log.store import LedgerStore


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_api_entry.db"


@pytest.fixture
def client(temp_db: Path) -> TestClient:
    app = create_app()
    return TestClient(app)


def test_get_entry_today_not_found(client: TestClient, temp_db: Path) -> None:
    # No entry in DB
    response = client.get(f"/api/entry/today?db={temp_db}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_get_entry_today_success(client: TestClient, temp_db: Path) -> None:
    store = LedgerStore(db_path=temp_db)
    today = date.today()
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
            work_date=today,
            draft_json=json.dumps(draft_data),
            prompt_version="v1",
            model="gemini-2.5-flash",
        )
    )

    response = client.get(f"/api/entry/today?db={temp_db}")
    assert response.status_code == 200
    data = response.json()
    assert data["entry_id"] == f"entry-{today.isoformat()}"
    assert data["work_date"] == today.isoformat()
    assert data["kehadiran"] == "Hadir"
    assert data["validation_passed"] is True
    assert data["validation_errors"] == []


def test_post_entry_edit_success(client: TestClient, temp_db: Path) -> None:
    today = date.today()
    payload = {
        "work_date": today.isoformat(),
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
    }

    response = client.post(f"/api/entry/edit?db={temp_db}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["validation_passed"] is True
    assert data["updated_entry"]["work_date"] == today.isoformat()


def test_post_entry_edit_validation_failure(client: TestClient, temp_db: Path) -> None:
    today = date.today()
    # Missing required field
    payload = {
        "work_date": today.isoformat(),
        "kehadiran": "Hadir",
        "aktivitas": "",
        "pembelajaran": "pendek",
        "kendala": "pendek",
    }
    response = client.post(f"/api/entry/edit?db={temp_db}", json=payload)
    assert response.status_code == 422


def test_post_entry_draft_success(client: TestClient, temp_db: Path) -> None:
    today = date.today()
    mock_client = MagicMock()
    mock_draft = LogEntryDraft(
        work_date=today,
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
    mock_client.generate.return_value = mock_draft

    with patch(
        "magang_log.server.services.entry_service.GeminiModelClient",
        return_value=mock_client,
    ):
        payload = {"work_date": today.isoformat()}
        response = client.post(f"/api/entry/draft?db={temp_db}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "draft" in data
        assert data["draft"]["work_date"] == today.isoformat()
        assert len(data["draft"]["aktivitas"]) >= 100
        assert data["validation_passed"] is True


def test_post_entry_approve_no_draft(client: TestClient, temp_db: Path) -> None:
    today = date.today()
    payload = {"work_date": today.isoformat()}
    response = client.post(f"/api/entry/approve?db={temp_db}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "error_message" in data


def test_post_entry_approve_success(client: TestClient, temp_db: Path) -> None:
    store = LedgerStore(db_path=temp_db)
    today = date.today()
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
    store.save_entry(
        EntryRecord(
            work_date=today,
            draft_json=json.dumps(valid_draft),
            prompt_version="v1",
            model="gemini-2.5-flash",
        )
    )

    payload = {"work_date": today.isoformat()}
    response = client.post(f"/api/entry/approve?db={temp_db}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["final_status"] == "BERHASIL"
    assert data["error_message"] is None

    # Check ledger verified
    saved = store.get_entry(today)
    assert saved is not None
    assert saved.portal_status == "SUDAH_TERKIRIM"
