"""Pengujian unit untuk ReviewSession, ApprovedEntry legal contract, dan perhitungan edit_ratio."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log.drafter.client import FakeModelClient
from magang_log.drafter.engine import EvidenceDrafter
from magang_log.drafter.models import LogEntryDraft
from magang_log.drafter.stage import DraftingStage
from magang_log.models import ApprovedEntry
from magang_log.pipeline import ArtifactStore
from magang_log.portal import NotApproved, assert_approved_for_submission
from magang_log.reviewer import (
    ReviewSession,
    compute_content_hash,
    compute_edit_ratio,
    format_prefill_editor,
    parse_editor_text,
)
from magang_log.store import LedgerStore


@pytest.fixture
def sample_draft() -> LogEntryDraft:
    return LogEntryDraft(
        work_date=date(2026, 10, 27),
        kehadiran="Hadir",
        aktivitas=(
            "Melaksanakan implementasi modul interaktif sesi peninjauan terminal untuk logbook "
            "harian magang sesuai spesifikasi dokumen PRD dan arsitektur sistem."
        ),
        pembelajaran=(
            "Mendalami mekanisme human-in-the-loop review, perhitungan rasio pengeditan dengan "
            "difflib, serta kontrak hukum ApprovedEntry."
        ),
        kendala=(
            "Tantangan dalam memastikan mocking proses editor eksternal tetap terisolasi "
            "dan deterministik selama pengujian otomatis."
        ),
        evidence_refs={"aktivitas": ["git-commit-1", "note-1"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )


def test_compute_edit_ratio_exact_match():
    text = "Aktivitas hari ini berjalan dengan lancar."
    ratio = compute_edit_ratio(text, text)
    assert ratio == 0.0


def test_compute_edit_ratio_complete_change():
    text_a = "Aktivitas A tentang pengembangan backend API dengan FastAPI."
    text_b = "Zzz sama sekali berbeda 1234567890."
    ratio = compute_edit_ratio(text_a, text_b)
    assert ratio > 0.7


def test_compute_edit_ratio_partial_edit(sample_draft: LogEntryDraft):
    modified = sample_draft.model_copy(
        update={
            "aktivitas": sample_draft.aktivitas.replace(
                "modul interaktif", "komponen CLI interaktif"
            )
        }
    )
    ratio = compute_edit_ratio(sample_draft, modified)
    assert 0.0 < ratio < 0.2


def test_compute_content_hash_deterministic(sample_draft: LogEntryDraft):
    hash1 = compute_content_hash(sample_draft)
    hash2 = compute_content_hash(sample_draft)
    assert hash1 == hash2
    assert len(hash1) == 64

    # Hash dari objek ApprovedEntry dengan isi yang sama menghasilkan hash yang persis sama
    entry = ApprovedEntry(
        work_date=sample_draft.work_date,
        aktivitas=sample_draft.aktivitas,
        pembelajaran=sample_draft.pembelajaran,
        kendala=sample_draft.kendala,
    )
    assert entry.content_hash == hash1


def test_approved_entry_immutability(sample_draft: LogEntryDraft):
    entry = ApprovedEntry(
        work_date=sample_draft.work_date,
        aktivitas=sample_draft.aktivitas,
        pembelajaran=sample_draft.pembelajaran,
        kendala=sample_draft.kendala,
        approved_at=datetime.now(),
        edit_ratio=0.05,
    )
    assert entry.edit_ratio == 0.05
    assert len(entry.content_hash) == 64

    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.aktivitas = "Perubahan tidak sah"  # type: ignore[misc]


def test_parse_editor_text_and_prefill(sample_draft: LogEntryDraft):
    prefill = format_prefill_editor(sample_draft)
    assert "### AKTIVITAS" in prefill
    assert "### PEMBELAJARAN" in prefill
    assert "### KENDALA" in prefill

    akt, pemb, kend = parse_editor_text(prefill)
    assert akt == sample_draft.aktivitas.strip()
    assert pemb == sample_draft.pembelajaran.strip()
    assert kend == sample_draft.kendala.strip()


def test_parse_editor_text_with_custom_edits():
    raw = """
    ### AKTIVITAS
    Menyusun skema pengujian dan validasi data.

    ### PEMBELAJARAN
    Mempelajari penggunaan subprocess dan shlex.

    ### KENDALA
    Tidak ada kendala yang signifikan.
    """
    akt, pemb, kend = parse_editor_text(raw)
    assert akt == "Menyusun skema pengujian dan validasi data."
    assert pemb == "Mempelajari penggunaan subprocess dan shlex."
    assert kend == "Tidak ada kendala yang signifikan."


def test_assert_approved_for_submission(sample_draft: LogEntryDraft):
    unapproved = ApprovedEntry(
        work_date=sample_draft.work_date,
        aktivitas=sample_draft.aktivitas,
        pembelajaran=sample_draft.pembelajaran,
        kendala=sample_draft.kendala,
        approved_at=None,
    )
    with pytest.raises(NotApproved, match="approved_at kosong"):
        assert_approved_for_submission(unapproved)

    with pytest.raises(ValueError, match="approved_at kosong"):
        unapproved.assert_approved()

    approved = ApprovedEntry(
        work_date=sample_draft.work_date,
        aktivitas=sample_draft.aktivitas,
        pembelajaran=sample_draft.pembelajaran,
        kendala=sample_draft.kendala,
        approved_at=datetime.now(),
    )
    # Tidak boleh raise
    assert_approved_for_submission(approved)
    approved.assert_approved()


def test_review_session_approve_flow(tmp_path: Path, sample_draft: LogEntryDraft):
    db_path = tmp_path / "state.db"
    store = LedgerStore(db_path=db_path)
    store.migrate()
    artifact_store = ArtifactStore(artifacts_dir=tmp_path / "runs")

    inputs = iter(["Y"])
    session = ReviewSession(
        store=store,
        artifact_store=artifact_store,
        input_func=lambda _: next(inputs),
    )

    approved = session.review(
        target_date=sample_draft.work_date,
        draft=sample_draft,
    )

    assert approved is not None
    assert approved.approved_at is not None
    assert approved.edit_ratio == 0.0
    assert len(approved.content_hash) == 64

    # Verifikasi tersimpan di SQLite entries table
    rec = store.get_entry(sample_draft.work_date)
    assert rec is not None
    assert rec.approved_at is not None
    assert rec.edit_ratio == 0.0
    assert rec.content_hash == approved.content_hash
    assert rec.approved_json is not None

    # Verifikasi tersimpan di disk approved.json
    loaded_disk = artifact_store.load_approval(sample_draft.work_date)
    assert loaded_disk is not None
    assert loaded_disk.approved_at is not None
    assert loaded_disk.content_hash == approved.content_hash


def test_review_session_skip_flow(tmp_path: Path, sample_draft: LogEntryDraft):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()

    inputs = iter(["S"])
    session = ReviewSession(
        store=store,
        input_func=lambda _: next(inputs),
    )

    approved = session.review(
        target_date=sample_draft.work_date,
        draft=sample_draft,
    )

    assert approved is None
    # Tidak tersimpan di entries
    rec = store.get_entry(sample_draft.work_date)
    assert rec is None


def test_review_session_edit_flow(tmp_path: Path, sample_draft: LogEntryDraft):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()
    artifact_store = ArtifactStore(artifacts_dir=tmp_path / "runs")

    def mock_editor(prefill: str) -> str:
        # Tambahkan teks edit pada aktivitas
        return prefill.replace("spesifikasi dokumen PRD", "spesifikasi teknis PRD v2 terbaru")

    inputs = iter(["E", "Y"])
    session = ReviewSession(
        store=store,
        artifact_store=artifact_store,
        input_func=lambda _: next(inputs),
        editor_launcher=mock_editor,
    )

    approved = session.review(
        target_date=sample_draft.work_date,
        draft=sample_draft,
    )

    assert approved is not None
    assert "spesifikasi teknis PRD v2 terbaru" in approved.aktivitas
    assert approved.edit_ratio > 0.0
    assert approved.approved_at is not None

    rec = store.get_entry(sample_draft.work_date)
    assert rec is not None
    assert rec.edit_ratio == approved.edit_ratio


def test_review_session_regenerate_flow(tmp_path: Path, sample_draft: LogEntryDraft):
    store = LedgerStore(db_path=tmp_path / "state.db")
    store.migrate()

    # Siapkan fake drafter stage
    regenerated_draft = sample_draft.model_copy(
        update={
            "aktivitas": (
                "Hasil regenerasi draf baru: mengimplementasikan seluruh antarmuka peninjauan "
                "terminal interaktif dengan pengujian menyeluruh."
            )
        }
    )
    fake_client = FakeModelClient(response=regenerated_draft)
    drafter = EvidenceDrafter(model_client=fake_client)
    stage = DraftingStage(drafter=drafter)

    inputs = iter(["R", "Y"])
    session = ReviewSession(
        store=store,
        drafter_stage=stage,
        input_func=lambda _: next(inputs),
    )

    approved = session.review(
        target_date=sample_draft.work_date,
        draft=sample_draft,
    )

    assert approved is not None
    assert "Hasil regenerasi draf baru" in approved.aktivitas
    assert approved.approved_at is not None
