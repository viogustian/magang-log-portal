"""Unit tests untuk StateMachine unidirectional dan fungsi utilitas pipeline."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from magang_log.models import ApprovedEntry
from magang_log.pipeline import (
    InvalidTransitionError,
    PipelineState,
    StateMachine,
    calculate_edit_ratio,
    compute_content_hash,
)


def test_state_machine_happy_path() -> None:
    sm = StateMachine()
    assert sm.current_state == PipelineState.START

    sm.transition_to(PipelineState.GATED)
    sm.transition_to(PipelineState.COLLECTED)
    sm.transition_to(PipelineState.DRAFTED)
    sm.transition_to(PipelineState.VALIDATED)
    sm.transition_to(PipelineState.APPROVED)
    sm.transition_to(PipelineState.SUBMITTED)
    final = sm.transition_to(PipelineState.BERHASIL)

    assert final == PipelineState.BERHASIL
    assert sm.history == [
        PipelineState.START,
        PipelineState.GATED,
        PipelineState.COLLECTED,
        PipelineState.DRAFTED,
        PipelineState.VALIDATED,
        PipelineState.APPROVED,
        PipelineState.SUBMITTED,
        PipelineState.BERHASIL,
    ]


def test_state_machine_early_halts() -> None:
    # GATED -> LIBUR
    sm1 = StateMachine()
    sm1.transition_to(PipelineState.GATED)
    sm1.transition_to(PipelineState.LIBUR)
    assert sm1.current_state == PipelineState.LIBUR

    # GATED -> SUDAH_TERKIRIM
    sm2 = StateMachine()
    sm2.transition_to(PipelineState.GATED)
    sm2.transition_to(PipelineState.SUDAH_TERKIRIM)
    assert sm2.current_state == PipelineState.SUDAH_TERKIRIM

    # COLLECTED -> PERLU_INPUT
    sm3 = StateMachine()
    sm3.transition_to(PipelineState.GATED)
    sm3.transition_to(PipelineState.COLLECTED)
    sm3.transition_to(PipelineState.PERLU_INPUT)
    assert sm3.current_state == PipelineState.PERLU_INPUT

    # DRAFTED -> PERLU_REVIEW
    sm4 = StateMachine()
    sm4.transition_to(PipelineState.GATED)
    sm4.transition_to(PipelineState.COLLECTED)
    sm4.transition_to(PipelineState.DRAFTED)
    sm4.transition_to(PipelineState.PERLU_REVIEW)
    assert sm4.current_state == PipelineState.PERLU_REVIEW

    # APPROVED -> DRYRUN
    sm5 = StateMachine()
    sm5.transition_to(PipelineState.GATED)
    sm5.transition_to(PipelineState.COLLECTED)
    sm5.transition_to(PipelineState.DRAFTED)
    sm5.transition_to(PipelineState.VALIDATED)
    sm5.transition_to(PipelineState.APPROVED)
    sm5.transition_to(PipelineState.DRYRUN)
    assert sm5.current_state == PipelineState.DRYRUN


def test_state_machine_portal_outcomes() -> None:
    for terminal in (
        PipelineState.BERHASIL,
        PipelineState.GAGAL,
        PipelineState.LOGIN_DIPERLUKAN,
        PipelineState.TERKUNCI,
        PipelineState.LOKASI_TIDAK_TERSEDIA,
    ):
        sm = StateMachine()
        sm.transition_to(PipelineState.GATED)
        sm.transition_to(PipelineState.COLLECTED)
        sm.transition_to(PipelineState.DRAFTED)
        sm.transition_to(PipelineState.VALIDATED)
        sm.transition_to(PipelineState.APPROVED)
        sm.transition_to(PipelineState.SUBMITTED)
        sm.transition_to(terminal)
        assert sm.current_state == terminal


def test_state_machine_rejects_invalid_transitions() -> None:
    sm = StateMachine()
    # Cannot jump from START to COLLECTED or SUBMITTED
    with pytest.raises(
        InvalidTransitionError, match="Transisi tidak valid dari START ke SUBMITTED"
    ):
        sm.transition_to(PipelineState.SUBMITTED)

    sm.transition_to(PipelineState.GATED)
    # Cannot jump backwards or skip
    with pytest.raises(InvalidTransitionError, match="Transisi tidak valid dari GATED ke START"):
        sm.transition_to(PipelineState.START)

    with pytest.raises(InvalidTransitionError, match="Transisi tidak valid dari GATED ke DRAFTED"):
        sm.transition_to(PipelineState.DRAFTED)


def test_calculate_edit_ratio_identical() -> None:
    draft = "Aktivitas harian mengerjakan modul portal.\nPembelajaran tentang Playwright.\nKendala nihil."
    approved = "Aktivitas harian mengerjakan modul portal.\nPembelajaran tentang Playwright.\nKendala nihil."
    ratio = calculate_edit_ratio(draft, approved)
    assert ratio == 0.0


def test_calculate_edit_ratio_modified() -> None:
    draft = "Aktivitas harian mengerjakan modul portal."
    approved = "Aktivitas harian mengerjakan modul portal dan integrasi SQLite."
    ratio = calculate_edit_ratio(draft, approved)
    assert 0.0 < ratio < 0.5


def test_calculate_edit_ratio_with_models() -> None:
    entry = ApprovedEntry(
        work_date=date(2026, 10, 27),
        aktivitas="Aktivitas harian baru yang ditulis ulang.",
        pembelajaran="Pembelajaran baru.",
        kendala="Kendala baru.",
        approved_at=datetime.now(),
    )
    draft_json = '{"aktivitas": "Aktivitas lama.", "pembelajaran": "Pembelajaran lama.", "kendala": "Kendala lama."}'
    ratio = calculate_edit_ratio(draft_json, entry)
    assert 0.0 < ratio <= 1.0


def test_compute_content_hash() -> None:
    text = "Logbook harian 2026-10-27"
    h1 = compute_content_hash(text)
    h2 = compute_content_hash(text)
    assert len(h1) == 64
    assert h1 == h2
    assert h1 != compute_content_hash("Lain")
