from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log.gates import (
    CalendarGate,
    GateDecision,
    PreflightGate,
)
from magang_log.models import EntryRecord, Status
from magang_log.store import LedgerStore


@pytest.fixture
def store(tmp_path: Path) -> LedgerStore:
    return LedgerStore(db_path=tmp_path / "ledger.db")


@pytest.fixture
def calendar_gate() -> CalendarGate:
    return CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"])


def test_preflight_weekend_halts_as_libur(calendar_gate: CalendarGate, store: LedgerStore) -> None:
    gate = PreflightGate(calendar_gate=calendar_gate, store=store)
    d_sat = date(2026, 10, 24)

    result = gate.inspect(d_sat)
    assert result.decision == GateDecision.LIBUR
    assert result.exit_code == 0
    assert result.run_id is not None

    # Audit run terekam di database
    run = store.get_run(result.run_id)
    assert run is not None
    assert run.work_date == d_sat
    assert run.status == Status.LIBUR
    assert run.stage == "GATED"


def test_preflight_workday_proceeds(calendar_gate: CalendarGate, store: LedgerStore) -> None:
    gate = PreflightGate(calendar_gate=calendar_gate, store=store)
    d_tue = date(2026, 10, 27)

    result = gate.inspect(d_tue)
    assert result.decision == GateDecision.WORKDAY
    assert result.exit_code == 0
    assert result.run_id is not None

    run = store.get_run(result.run_id)
    assert run is not None
    assert run.work_date == d_tue
    assert run.status == Status.BERHASIL


def test_preflight_already_submitted_halts_as_sudah_terkirim(
    calendar_gate: CalendarGate, store: LedgerStore
) -> None:
    target_date = date(2026, 10, 27)
    # Simulasikan entri yang sudah disubmit ke portal
    store.save_entry(
        EntryRecord(
            work_date=target_date,
            draft_json='{"aktivitas": "Testing"}',
            approved_json='{"aktivitas": "Testing disetujui"}',
            content_hash="hash-123",
            portal_status=Status.SUDAH_TERKIRIM,
            submitted_at=datetime(2026, 10, 27, 16, 45, 0),
        )
    )

    gate = PreflightGate(calendar_gate=calendar_gate, store=store)
    result = gate.inspect(target_date, content_hash="hash-123")

    assert result.decision == GateDecision.SUDAH_TERKIRIM
    assert result.exit_code == 0
    assert "sudah berstatus" in result.reason.lower()

    # Verifikasi run record
    run = store.get_run(result.run_id)
    assert run is not None
    assert run.status == Status.SUDAH_TERKIRIM


def test_preflight_force_cannot_override_already_submitted(
    calendar_gate: CalendarGate, store: LedgerStore
) -> None:
    target_date = date(2026, 10, 27)
    store.save_entry(
        EntryRecord(
            work_date=target_date,
            draft_json='{"aktivitas": "Testing"}',
            approved_json='{"aktivitas": "Testing disetujui"}',
            content_hash="hash-123",
            portal_status=Status.SUDAH_TERKIRIM,
        )
    )

    gate = PreflightGate(calendar_gate=calendar_gate, store=store)
    # Jalankan dengan flag force=True
    result = gate.inspect(target_date, force=True)

    # Tetap harus ditolak/halted karena status sudah SUDAH_TERKIRIM
    assert result.decision == GateDecision.SUDAH_TERKIRIM
    assert result.exit_code == 0


def test_preflight_force_allows_draft_regeneration_if_not_submitted(
    calendar_gate: CalendarGate, store: LedgerStore
) -> None:
    target_date = date(2026, 10, 27)
    # Entri baru berupa draf (BELUM_DIISI)
    store.save_entry(
        EntryRecord(
            work_date=target_date,
            draft_json='{"aktivitas": "Draft lama"}',
            content_hash="hash-old",
            portal_status=Status.PERLU_TINDAKAN,
        )
    )

    gate = PreflightGate(calendar_gate=calendar_gate, store=store)
    result = gate.inspect(target_date, force=True)

    # Boleh diproses ulang
    assert result.decision == GateDecision.WORKDAY


def test_idempotent_dual_trigger_simulation(
    calendar_gate: CalendarGate, store: LedgerStore
) -> None:
    target_date = date(2026, 10, 27)
    gate = PreflightGate(calendar_gate=calendar_gate, store=store)

    # Pemicu 1 (16:30): Pertama kali berjalan
    res1 = gate.inspect(target_date)
    assert res1.decision == GateDecision.WORKDAY

    # Simulasikan pipeline menyelesaikan draf dan submit ke portal
    store.save_entry(
        EntryRecord(
            work_date=target_date,
            draft_json='{"aktivitas": "Pekerjaan hari ini"}',
            approved_json='{"aktivitas": "Pekerjaan hari ini"}',
            content_hash="hash-abc",
            portal_status=Status.SUDAH_TERKIRIM,
            submitted_at=datetime(2026, 10, 27, 16, 35, 0),
        )
    )

    # Pemicu 2 (20:00): Berjalan kembali pada tanggal yang sama
    res2 = gate.inspect(target_date, content_hash="hash-abc")
    assert res2.decision == GateDecision.SUDAH_TERKIRIM
    assert res2.exit_code == 0

    # Pastikan unique run_id untuk setiap trigger
    assert res1.run_id != res2.run_id

    # Pastikan rekam runs tersimpan untuk kedua trigger tanpa merusak entries
    all_runs = store.get_runs_for_date(target_date)
    assert len(all_runs) == 2
    assert all_runs[0].status == Status.BERHASIL
    assert all_runs[1].status == Status.SUDAH_TERKIRIM

    # Pastikan entries tidak menduplikasi baris (PK work_date terjaga)
    entry = store.get_entry(target_date)
    assert entry is not None
    assert entry.portal_status == Status.SUDAH_TERKIRIM
