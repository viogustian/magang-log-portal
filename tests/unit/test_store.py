import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log.models import (
    EntryRecord,
    EvidenceItem,
    NoteRecord,
    RunRecord,
    Status,
)
from magang_log.store import LedgerStore


@pytest.fixture
def store(tmp_path: Path) -> LedgerStore:
    db_file = tmp_path / "test_state.db"
    return LedgerStore(db_path=db_file)


def test_schema_migrations_initialization(store: LedgerStore) -> None:
    # Verifikasi tabel dan indeks dibuat saat inisialisasi
    with store.connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "schema_migrations" in tables
        assert "runs" in tables
        assert "entries" in tables
        assert "evidence" in tables
        assert "notes" in tables

        # Verifikasi migrasi tercatat
        migrated = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert len(migrated) >= 1
        assert migrated[0][0] == 1

        # Idempotensi: menjalankan migrate() kembali tidak merusak schema
        store.migrate()


def test_runs_crud(store: LedgerStore) -> None:
    now = datetime(2026, 10, 27, 16, 30, 0)
    run = RunRecord(
        run_id="run-20261027-001",
        work_date=date(2026, 10, 27),
        stage="GATED",
        status=Status.BERHASIL,
        started_at=now,
        finished_at=datetime(2026, 10, 27, 16, 30, 15),
        tokens_in=1500,
        tokens_out=300,
        duration_ms=15000,
        error_code=None,
    )
    store.record_run(run)

    fetched = store.get_run("run-20261027-001")
    assert fetched is not None
    assert fetched.run_id == "run-20261027-001"
    assert fetched.work_date == date(2026, 10, 27)
    assert fetched.status == Status.BERHASIL
    assert fetched.tokens_in == 1500
    assert fetched.tokens_out == 300
    assert fetched.duration_ms == 15000

    runs_for_date = store.get_runs_for_date(date(2026, 10, 27))
    assert len(runs_for_date) == 1
    assert runs_for_date[0].run_id == "run-20261027-001"


def test_entries_crud_and_unique_constraint(store: LedgerStore) -> None:
    target_date = date(2026, 10, 27)
    entry = EntryRecord(
        work_date=target_date,
        draft_json='{"aktivitas": "Coding backend SQLite"}',
        approved_json=None,
        prompt_version="v1",
        model="gemini-2.5-flash",
        edit_ratio=None,
        content_hash="abc123hash",
        portal_status="BELUM_DIISI",
    )
    store.save_entry(entry)

    fetched = store.get_entry(target_date)
    assert fetched is not None
    assert fetched.work_date == target_date
    assert fetched.draft_json == '{"aktivitas": "Coding backend SQLite"}'
    assert fetched.content_hash == "abc123hash"
    assert fetched.portal_status == "BELUM_DIISI"

    # Update approval
    approved_time = datetime(2026, 10, 27, 17, 0, 0)
    store.update_entry_approval(
        work_date=target_date,
        approved_json='{"aktivitas": "Coding backend SQLite terverifikasi"}',
        approved_at=approved_time,
        edit_ratio=0.15,
    )
    updated = store.get_entry(target_date)
    assert updated is not None
    assert updated.approved_json == '{"aktivitas": "Coding backend SQLite terverifikasi"}'
    assert updated.approved_at == approved_time
    assert updated.edit_ratio == 0.15

    # Update submission
    submitted_time = datetime(2026, 10, 27, 17, 5, 0)
    store.update_entry_submission(
        work_date=target_date,
        portal_status="SUDAH_TERKIRIM",
        submitted_at=submitted_time,
        verified_at=submitted_time,
    )
    final_entry = store.get_entry(target_date)
    assert final_entry is not None
    assert final_entry.portal_status == "SUDAH_TERKIRIM"
    assert final_entry.submitted_at == submitted_time
    assert final_entry.verified_at == submitted_time

    # Constraint: Insert duplicate tanpa replace harus gagal
    duplicate = EntryRecord(
        work_date=target_date,
        draft_json='{"aktivitas": "Duplicate"}',
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_entry_strict(duplicate)


def test_evidence_storage(store: LedgerStore) -> None:
    target_date = date(2026, 10, 27)
    items = [
        EvidenceItem(
            id="git-commit-1",
            work_date=target_date,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: implement sqlite store",
            detail="Added store.py and migrations",
            strength="strong",
        ),
        EvidenceItem(
            id="git-commit-2",
            work_date=target_date,
            source="git",
            kind="commit",
            ts="2026-10-27T14:00:00",
            title="test: add tests for store",
            detail="Added test_store.py",
            strength="strong",
        ),
    ]
    store.save_evidence(items)

    fetched = store.get_evidence_for_date(target_date)
    assert len(fetched) == 2
    assert {e.id for e in fetched} == {"git-commit-1", "git-commit-2"}
    assert fetched[0].source == "git"


def test_notes_storage_and_kind_constraint(store: LedgerStore) -> None:
    target_date = date(2026, 10, 27)
    now = datetime(2026, 10, 27, 15, 0, 0)

    # Valid kinds: 'aktivitas', 'pembelajaran', 'kendala'
    note_id = store.add_note(
        NoteRecord(
            id=None,
            work_date=target_date,
            kind="aktivitas",
            text="Diskusi arsitektur database",
            created_at=now,
        )
    )
    assert note_id > 0

    notes = store.get_notes_for_date(target_date)
    assert len(notes) == 1
    assert notes[0].id == note_id
    assert notes[0].kind == "aktivitas"
    assert notes[0].text == "Diskusi arsitektur database"

    # Invalid kind must fail CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        store.add_note(
            NoteRecord(
                id=None,
                work_date=target_date,
                kind="invalid_kind",
                text="Should fail",
                created_at=now,
            )
        )


def test_transaction_rollback_on_exception(store: LedgerStore) -> None:
    target_date = date(2026, 10, 28)

    with pytest.raises(RuntimeError, match="Simulated failure"):
        with store.transaction():
            store.add_note(
                NoteRecord(
                    id=None,
                    work_date=target_date,
                    kind="aktivitas",
                    text="Catatan yang harus dibatalkan",
                    created_at=datetime.now(),
                )
            )
            # Sengaja menimbulkan exception di tengah transaksi
            raise RuntimeError("Simulated failure")

    # Pastikan catatan tidak tersimpan (di-rollback)
    assert store.get_notes_for_date(target_date) == []
