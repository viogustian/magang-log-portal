"""Pengujian integrasi untuk ConditionalAutoApprovalEngine dan PipelineCoordinator."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from magang_log.drafter.models import LogEntryDraft
from magang_log.gates import GateDecision, PreflightGate
from magang_log.models import EntryRecord, EvidenceItem, Status
from magang_log.pipeline import (
    ArtifactStore,
    DraftResult,
    PipelineCoordinator,
    PipelineState,
)
from magang_log.reviewer import ConditionalAutoApprovalEngine
from magang_log.settings import AppConfig, ReviewSettings
from magang_log.store import LedgerStore
from magang_log.validator.models import ValidationReport


@pytest.fixture
def sample_draft() -> LogEntryDraft:
    return LogEntryDraft(
        work_date=date(2026, 10, 27),
        kehadiran="Hadir",
        aktivitas=(
            "Melaksanakan implementasi ConditionalAutoApprovalEngine dengan verifikasi metrik historis "
            "dan pengujian otomatis menyeluruh sesuai dokumen spesifikasi PRD v2."
        ),
        pembelajaran=(
            "Mendalami kriteria kelayakan auto-approval ketat, median rasio pengeditan, serta "
            "mekanisme fallback aman ke peninjauan manual."
        ),
        kendala=(
            "Tantangan dalam memastikan perhitungan median edit_ratio pada 10 entri historis "
            "tercatat akurat di ledger SQLite."
        ),
        evidence_refs={"aktivitas": ["git-01", "note-01"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )


@pytest.fixture
def perfect_validation() -> ValidationReport:
    return ValidationReport(
        is_valid=True,
        errors=[],
        warnings=[],
        grounding_score=0.95,
        detected_filler=[],
    )


def _seed_historical_entries(
    store: LedgerStore,
    count: int = 10,
    edit_ratios: list[float] | None = None,
    base_date: date = date(2026, 10, 26),
) -> None:
    """Menyemai sejumlah entri historis yang disetujui ke dalam database SQLite."""
    ratios = edit_ratios or [0.05] * count
    for i in range(count):
        entry_date = base_date - timedelta(days=i + 1)
        ratio = ratios[i] if i < len(ratios) else 0.05
        rec = EntryRecord(
            work_date=entry_date,
            draft_json=json.dumps(
                {"aktivitas": f"Kegiatan {i}", "pembelajaran": "P", "kendala": "K"}
            ),
            approved_json=json.dumps(
                {"aktivitas": f"Kegiatan {i}", "pembelajaran": "P", "kendala": "K"}
            ),
            prompt_version="v1",
            model="gemini-2.5-flash",
            edit_ratio=ratio,
            content_hash=f"hash-{i}",
            portal_status=Status.SUDAH_TERKIRIM.value,
            approved_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc),
        )
        store.save_entry(rec)


def test_default_disabled_behavior(
    tmp_path: Path, sample_draft: LogEntryDraft, perfect_validation: ValidationReport
):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    _seed_historical_entries(store, count=12, edit_ratios=[0.02] * 12)

    cfg = AppConfig()  # review.auto_if_confident bernilai False secara default
    assert cfg.review.auto_if_confident is False

    engine = ConditionalAutoApprovalEngine(store=store, config=cfg)
    decision = engine.evaluate(sample_draft.work_date, sample_draft, perfect_validation)

    assert decision.eligible is False
    assert "dinonaktifkan" in decision.reason.lower()


def test_disqualification_fewer_than_10_historical_entries(
    tmp_path: Path, sample_draft: LogEntryDraft, perfect_validation: ValidationReport
):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    # Hanya 9 entri historis disemai (kurang dari syarat minimal 10)
    _seed_historical_entries(store, count=9, edit_ratios=[0.01] * 9)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    engine = ConditionalAutoApprovalEngine(store=store, config=cfg)
    decision = engine.evaluate(sample_draft.work_date, sample_draft, perfect_validation)

    assert decision.eligible is False
    assert decision.history_count == 9
    assert "kurang dari 10" in decision.reason


def test_disqualification_when_warnings_exist(tmp_path: Path, sample_draft: LogEntryDraft):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    _seed_historical_entries(store, count=10, edit_ratios=[0.05] * 10)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    engine = ConditionalAutoApprovalEngine(store=store, config=cfg)

    validation_with_warnings = ValidationReport(
        is_valid=True,
        errors=[],
        warnings=["Paragraf aktivitas mendekati batas minimum"],
        grounding_score=0.95,
    )

    decision = engine.evaluate(sample_draft.work_date, sample_draft, validation_with_warnings)
    assert decision.eligible is False
    assert decision.warnings_count == 1
    assert "peringatan" in decision.reason.lower()


def test_disqualification_when_grounding_score_below_threshold(
    tmp_path: Path, sample_draft: LogEntryDraft
):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    _seed_historical_entries(store, count=10, edit_ratios=[0.05] * 10)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    engine = ConditionalAutoApprovalEngine(store=store, config=cfg)

    low_grounding_validation = ValidationReport(
        is_valid=True,
        errors=[],
        warnings=[],
        grounding_score=0.75,  # Kurang dari 0.80
    )

    decision = engine.evaluate(sample_draft.work_date, sample_draft, low_grounding_validation)
    assert decision.eligible is False
    assert decision.grounding_score == 0.75
    assert "di bawah ambang batas minimal" in decision.reason


def test_disqualification_when_median_edit_ratio_exceeds_threshold(
    tmp_path: Path, sample_draft: LogEntryDraft, perfect_validation: ValidationReport
):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    # 10 entri dengan median > 0.15 (mis. rata-rata 0.20)
    high_ratios = [0.20, 0.18, 0.22, 0.16, 0.25, 0.19, 0.21, 0.17, 0.23, 0.19]
    _seed_historical_entries(store, count=10, edit_ratios=high_ratios)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    engine = ConditionalAutoApprovalEngine(store=store, config=cfg)
    decision = engine.evaluate(sample_draft.work_date, sample_draft, perfect_validation)

    assert decision.eligible is False
    assert decision.median_edit_ratio is not None
    assert decision.median_edit_ratio > 0.15
    assert "melebihi batas maksimal 0.15" in decision.reason


def test_successful_auto_approval_and_notification(
    tmp_path: Path, sample_draft: LogEntryDraft, perfect_validation: ValidationReport
):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    artifact_store = ArtifactStore(artifacts_dir=tmp_path / "runs")

    # 10 entri dengan median rendah (mis. 0.05 <= 0.15)
    good_ratios = [0.02, 0.04, 0.05, 0.01, 0.08, 0.03, 0.06, 0.05, 0.07, 0.04]
    _seed_historical_entries(store, count=10, edit_ratios=good_ratios)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    engine = ConditionalAutoApprovalEngine(
        store=store,
        config=cfg,
        artifact_store=artifact_store,
    )

    with patch("magang_log.reviewer.auto_approval.send_system_notification") as mock_notify:
        decision = engine.evaluate(sample_draft.work_date, sample_draft, perfect_validation)

        assert decision.eligible is True
        assert decision.entry is not None
        assert decision.entry.approved_at is not None
        assert decision.entry.edit_ratio == 0.0
        assert len(decision.entry.content_hash) == 64

        # Notifikasi sistem terpanggil
        mock_notify.assert_called_once()
        call_kwargs = mock_notify.call_args[1]
        assert "Auto-Approved" in call_kwargs["title"]

    # Verifikasi tersimpan di SQLite entries
    rec = store.get_entry(sample_draft.work_date)
    assert rec is not None
    assert rec.approved_at is not None
    assert rec.edit_ratio == 0.0

    # Verifikasi tersimpan di SQLite runs
    runs = store.get_runs_for_date(sample_draft.work_date)
    assert any(r.stage == "APPROVED" and r.status == Status.BERHASIL for r in runs)

    # Verifikasi tersimpan di disk approved.json
    disk_approved = artifact_store.load_approval(sample_draft.work_date)
    assert disk_approved is not None
    assert disk_approved.content_hash == decision.entry.content_hash


def test_pipeline_coordinator_auto_approval_integration(
    tmp_path: Path, sample_draft: LogEntryDraft, perfect_validation: ValidationReport
):
    target_date = sample_draft.work_date
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)
    store.migrate()
    _seed_historical_entries(store, count=10, edit_ratios=[0.03] * 10)

    cfg = AppConfig(review=ReviewSettings(auto_if_confident=True))
    artifact_store = ArtifactStore(artifacts_dir=tmp_path / "runs")
    engine = ConditionalAutoApprovalEngine(store=store, config=cfg, artifact_store=artifact_store)

    from magang_log.gates import GateResult

    gate = MagicMock(spec=PreflightGate)
    gate.inspect.return_value = GateResult(
        decision=GateDecision.WORKDAY, reason="Hari kerja", target_date=target_date
    )

    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="e-01",
            work_date=target_date,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: test commit",
            strength="strong",
        )
    ]

    drafter = MagicMock()
    drafter.draft.return_value = DraftResult(draft_json=sample_draft.model_dump_json())

    validator = MagicMock()
    validator.validate.return_value = perfect_validation

    approval = MagicMock()
    portal = MagicMock()

    coord = PipelineCoordinator(
        store=store,
        preflight_gate=gate,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal,
        artifacts_dir=tmp_path / "runs",
        auto_approval_engine=engine,
    )

    with patch("magang_log.reviewer.auto_approval.send_system_notification"):
        res = coord.run(target_date=target_date, dry_run=True)

    assert res.final_state == PipelineState.DRYRUN
    assert res.status == Status.DRYRUN
    # Approval manual tidak pernah dipanggil karena langsung auto-approved
    approval.review_and_approve.assert_not_called()
    # Portal submit dipanggil dengan ApprovedEntry
    portal.submit.assert_called_once()
    submitted_entry = portal.submit.call_args[0][0]
    assert submitted_entry.approved_at is not None
    assert submitted_entry.edit_ratio == 0.0
