"""Integration tests untuk PipelineCoordinator dan state machine engine."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from magang_log.gates import CalendarGate, HolidayProvider, PreflightGate
from magang_log.models import (
    ApprovedEntry,
    EntryRecord,
    EvidenceItem,
    PortalResult,
    Status,
)
from magang_log.pipeline import (
    DraftResult,
    PipelineCoordinator,
    PipelineState,
    ValidationResult,
)
from magang_log.store import LedgerStore


def _setup_coordinator(
    tmp_path: Path,
    collector=None,
    drafter=None,
    validator=None,
    approval=None,
    portal=None,
) -> tuple[PipelineCoordinator, LedgerStore, Path]:
    db_path = tmp_path / "state.db"
    artifacts_dir = tmp_path / "runs"
    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},  # Senin - Jumat
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal,
        artifacts_dir=artifacts_dir,
    )
    return coordinator, store, artifacts_dir


def test_pipeline_weekend_halts_as_libur(tmp_path: Path) -> None:
    # 2026-10-25 adalah hari Minggu
    coord, store, _ = _setup_coordinator(tmp_path)
    res = coord.run(target_date=date(2026, 10, 25))

    assert res.final_state == PipelineState.LIBUR
    assert res.status == Status.LIBUR
    assert res.exit_code == 0

    runs = store.list_runs(target_date=date(2026, 10, 25))
    assert len(runs) >= 1
    assert runs[-1].status == Status.LIBUR


def test_pipeline_already_submitted_halts(tmp_path: Path) -> None:
    # 2026-10-27 adalah hari Selasa
    coord, store, _ = _setup_coordinator(tmp_path)
    store.save_entry(
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json='{"aktivitas": "Sudah kirim"}',
            approved_json='{"aktivitas": "Sudah kirim"}',
            portal_status=Status.SUDAH_TERKIRIM,
        )
    )

    res = coord.run(target_date=date(2026, 10, 27))
    assert res.final_state == PipelineState.SUDAH_TERKIRIM
    assert res.status == Status.SUDAH_TERKIRIM
    assert res.exit_code == 0


def test_pipeline_insufficient_evidence_halts_perlu_input(tmp_path: Path) -> None:
    collector = MagicMock()
    # Hanya bukti berkategori 'weak' atau kosong
    collector.collect.return_value = [
        EvidenceItem(
            id="weak-1",
            work_date=date(2026, 10, 27),
            source="browser",
            kind="visit",
            ts="2026-10-27T10:00:00",
            title="Search python docs",
            strength="weak",
        )
    ]

    coord, store, artifacts_dir = _setup_coordinator(tmp_path, collector=collector)
    res = coord.run(target_date=date(2026, 10, 27))

    assert res.final_state == PipelineState.PERLU_INPUT
    assert res.status == Status.PERLU_INPUT
    assert res.exit_code == 10
    assert res.error_code == "INSUFFICIENT_EVIDENCE"

    # Verifikasi artifak disimpan
    evidence_file = artifacts_dir / "2026-10-27" / "evidence.json"
    assert evidence_file.exists()


def test_pipeline_validation_failure_halts_perlu_review(tmp_path: Path) -> None:
    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=date(2026, 10, 27),
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: portal integration",
            strength="strong",
        )
    ]

    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(
        draft_json='{"aktivitas": "Draf yang tidak valid"}',
        tokens_in=100,
        tokens_out=200,
    )

    validator = MagicMock()
    validator.validate.return_value = ValidationResult(
        is_valid=False, errors=["Teks aktivitas kurang dari 100 karakter"]
    )

    coord, store, artifacts_dir = _setup_coordinator(
        tmp_path, collector=collector, drafter=drafter, validator=validator
    )
    res = coord.run(target_date=date(2026, 10, 27))

    assert res.final_state == PipelineState.PERLU_REVIEW
    assert res.status == Status.PERLU_REVIEW
    assert res.exit_code == 10
    assert res.tokens_in == 100
    assert res.tokens_out == 200

    # Artifak draft dan validation disimpan
    assert (artifacts_dir / "2026-10-27" / "draft.json").exists()
    assert (artifacts_dir / "2026-10-27" / "validated.json").exists()


def test_pipeline_awaiting_approval_halts_perlu_review(tmp_path: Path) -> None:
    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=date(2026, 10, 27),
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: portal integration",
            strength="strong",
        )
    ]

    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(
        draft_json='{"aktivitas": "Draf aktivitas yang valid dan lengkap memenuhi batas karakter."}',
    )

    validator = MagicMock()
    validator.validate.return_value = ValidationResult(is_valid=True)

    approval = MagicMock()
    # Pengguna menolak / menunda persetujuan (mengembalikan None)
    approval.review_and_approve.return_value = None

    coord, store, artifacts_dir = _setup_coordinator(
        tmp_path, collector=collector, drafter=drafter, validator=validator, approval=approval
    )
    res = coord.run(target_date=date(2026, 10, 27))

    assert res.final_state == PipelineState.PERLU_REVIEW
    assert res.status == Status.PERLU_REVIEW
    assert res.exit_code == 10
    assert res.error_code == "AWAITING_APPROVAL"


def test_pipeline_dry_run_success(tmp_path: Path) -> None:
    target = date(2026, 10, 27)
    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=target,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: strong commit",
            strength="strong",
        )
    ]
    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(
        draft_json='{"aktivitas": "Draf aktivitas", "pembelajaran": "Belajar", "kendala": "Nihil"}'
    )
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(is_valid=True)

    approval = MagicMock()
    approval.review_and_approve.return_value = ApprovedEntry(
        work_date=target,
        aktivitas="Draf aktivitas teredit oleh pengguna",
        pembelajaran="Belajar",
        kendala="Nihil",
        approved_at=datetime.now(),
    )

    portal = MagicMock()

    coord, store, artifacts_dir = _setup_coordinator(
        tmp_path,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal,
    )

    res = coord.run(target_date=target, dry_run=True)

    assert res.final_state == PipelineState.DRYRUN
    assert res.status == Status.DRYRUN
    assert res.exit_code == 0
    portal.submit.assert_called_once_with(approval.review_and_approve.return_value, dry_run=True)

    # Verifikasi audit di database
    entry = store.get_entry(target)
    assert entry is not None
    assert entry.approved_json is not None
    assert entry.edit_ratio is not None
    assert 0.0 < entry.edit_ratio < 1.0


def test_pipeline_portal_outcomes(tmp_path: Path) -> None:
    target = date(2026, 10, 27)
    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=target,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="commit",
            strength="strong",
        )
    ]
    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(draft_json='{"aktivitas": "Draft"}')
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(is_valid=True)
    approval = MagicMock()
    approved_obj = ApprovedEntry(
        work_date=target,
        aktivitas="Draft",
        pembelajaran="Belajar",
        kendala="Nihil",
        approved_at=datetime.now(),
    )
    approval.review_and_approve.return_value = approved_obj

    # 1. LOGIN_DIPERLUKAN (exits 20)
    portal1 = MagicMock()
    portal1.submit.return_value = PortalResult(
        status=Status.LOGIN_DIPERLUKAN, note="Session expired"
    )
    coord1, _, _ = _setup_coordinator(
        tmp_path / "t1",
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal1,
    )
    res1 = coord1.run(target_date=target)
    assert res1.final_state == PipelineState.LOGIN_DIPERLUKAN
    assert res1.exit_code == 20

    # 2. TERKUNCI (exits 40)
    portal2 = MagicMock()
    portal2.submit.return_value = PortalResult(status=Status.TERKUNCI, note="Date is locked")
    coord2, _, _ = _setup_coordinator(
        tmp_path / "t2",
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal2,
    )
    res2 = coord2.run(target_date=target)
    assert res2.final_state == PipelineState.TERKUNCI
    assert res2.exit_code == 40

    # 3. LOKASI_TIDAK_TERSEDIA (exits 40)
    portal3 = MagicMock()
    portal3.submit.return_value = PortalResult(
        status=Status.LOKASI_TIDAK_TERSEDIA, note="No location"
    )
    coord3, _, _ = _setup_coordinator(
        tmp_path / "t3",
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal3,
    )
    res3 = coord3.run(target_date=target)
    assert res3.final_state == PipelineState.LOKASI_TIDAK_TERSEDIA
    assert res3.exit_code == 40

    # 4. GAGAL (exits 40)
    portal4 = MagicMock()
    portal4.submit.return_value = PortalResult(status=Status.GAGAL, note="Unknown failure")
    coord4, _, _ = _setup_coordinator(
        tmp_path / "t4",
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal4,
    )
    res4 = coord4.run(target_date=target)
    assert res4.final_state == PipelineState.GAGAL
    assert res4.exit_code == 40


def test_pipeline_happy_path_success(tmp_path: Path) -> None:
    target = date(2026, 10, 27)
    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=target,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: full implementation",
            strength="strong",
        )
    ]
    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(
        draft_json=json.dumps(
            {
                "aktivitas": "Mengembangkan fitur state machine dan pipeline coordinator.",
                "pembelajaran": "Menerapkan prinsip deterministik dan idempotensi.",
                "kendala": "Tidak ada kendala yang menghambat.",
            }
        ),
        prompt_version="v2",
        model="gemini-2.5-flash",
        tokens_in=350,
        tokens_out=420,
    )
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(is_valid=True)

    approval = MagicMock()
    approval.review_and_approve.return_value = ApprovedEntry(
        work_date=target,
        aktivitas="Mengembangkan fitur state machine dan pipeline coordinator terintegrasi.",
        pembelajaran="Menerapkan prinsip deterministik dan idempotensi.",
        kendala="Tidak ada kendala yang menghambat.",
        approved_at=datetime(2026, 10, 27, 16, 45, 0),
    )

    portal = MagicMock()
    portal.submit.return_value = PortalResult(
        status=Status.BERHASIL, note="Terkirim dan terverifikasi"
    )

    coord, store, artifacts_dir = _setup_coordinator(
        tmp_path,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal,
    )

    res = coord.run(target_date=target)

    assert res.final_state == PipelineState.BERHASIL
    assert res.status == Status.BERHASIL
    assert res.exit_code == 0
    assert res.tokens_in == 350
    assert res.tokens_out == 420

    # Verifikasi audit di database
    entry = store.get_entry(target)
    assert entry is not None
    assert entry.portal_status == Status.SUDAH_TERKIRIM
    assert entry.approved_json is not None
    assert entry.edit_ratio is not None
    assert entry.verified_at is not None

    runs = store.list_runs(target_date=target)
    assert len(runs) >= 1
    assert runs[-1].status == Status.BERHASIL
    assert runs[-1].tokens_in == 350
    assert runs[-1].tokens_out == 420


def test_pipeline_resume_skips_upstream_stages(tmp_path: Path) -> None:
    target = date(2026, 10, 27)

    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="c1",
            work_date=target,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: resume test",
            strength="strong",
        )
    ]
    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(
        draft_json='{"aktivitas": "Draft", "pembelajaran": "Belajar", "kendala": "Nihil"}'
    )
    validator = MagicMock()
    validator.validate.return_value = ValidationResult(is_valid=True)

    approval = MagicMock()
    # Kali pertama: user pending review (mengembalikan None)
    approval.review_and_approve.return_value = None

    coord, store, artifacts_dir = _setup_coordinator(
        tmp_path,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
    )

    res1 = coord.run(target_date=target)
    assert res1.final_state == PipelineState.PERLU_REVIEW
    assert res1.exit_code == 10
    assert collector.collect.call_count == 1
    assert drafter.draft.call_count == 1

    # Kali kedua dengan --resume:
    # User sekarang menyetujui
    approval.review_and_approve.return_value = ApprovedEntry(
        work_date=target,
        aktivitas="Draft disetujui",
        pembelajaran="Belajar",
        kendala="Nihil",
        approved_at=datetime.now(),
    )
    portal = MagicMock()
    portal.submit.return_value = PortalResult(status=Status.BERHASIL, note="Terkirim")
    coord.portal = portal

    res2 = coord.run(target_date=target, resume=True)
    assert res2.final_state == PipelineState.BERHASIL
    assert res2.exit_code == 0

    # Collector dan drafter TIDAK dipanggil ulang karena artifak sudah dimuat!
    assert collector.collect.call_count == 1
    assert drafter.draft.call_count == 1
