"""Integration tests untuk self-correcting feedback retry loop dan drafting stage."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from magang_log.collectors.base import Evidence
from magang_log.drafter import (
    DraftingStage,
    EvidenceDrafter,
    LogEntryDraft,
    ModelClient,
)
from magang_log.gates import CalendarGate, HolidayProvider, PreflightGate
from magang_log.models import EvidenceItem, Status
from magang_log.pipeline import PipelineCoordinator, PipelineState
from magang_log.store import LedgerStore
from magang_log.validator import CANNED_FILLER_PHRASES


class SequenceMockModelClient(ModelClient):
    """Model client palsu yang mengembalikan urutan respon berurutan per pemanggilan."""

    def __init__(self, responses: list[LogEntryDraft]) -> None:
        self.responses = list(responses)
        self.call_history: list[dict[str, str]] = []

    def generate(
        self,
        system_prompt: str,
        user_payload: str,
        schema: type[LogEntryDraft],
    ) -> LogEntryDraft:
        self.call_history.append(
            {
                "system_prompt": system_prompt,
                "user_payload": user_payload,
            }
        )
        if not self.responses:
            raise IndexError("Tidak ada respon lagi yang tersedia dalam SequenceMockModelClient")
        return self.responses.pop(0)


def _make_evidence(id_: str = "ev1") -> Evidence:
    return Evidence(
        id=id_,
        source="git",  # type: ignore[arg-type]
        kind="commit",
        ts=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        title="feat: implementasi login portal",
        detail="detail",
        strength="strong",  # type: ignore[arg-type]
    )


def _make_valid_draft(work_date: date) -> LogEntryDraft:
    return LogEntryDraft(
        work_date=work_date,
        kehadiran="Hadir",
        aktivitas=(
            "Mengembangkan implementasi modul autentikasi sesi login portal magang industri "
            "dengan pengujian unit komprehensif dan validasi token keamanan resmi [ev1]."
        ),
        pembelajaran=(
            "Mempelajari arsitektur otorisasi berbasis token JWT serta teknik isolasi hak akses "
            "pada sistem backend pemerintahan berbasis Python [ev1]."
        ),
        kendala=(
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "mengatasinya dengan implementasi retry mechanism exponential backoff [ev1]."
        ),
        evidence_refs={"aktivitas": ["ev1"], "pembelajaran": ["ev1"], "kendala": ["ev1"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )


def _make_invalid_draft(work_date: date, reason: str = "short") -> LogEntryDraft:
    if reason == "short":
        # Terlalu pendek (< 100 karakter)
        return LogEntryDraft(
            work_date=work_date,
            kehadiran="Hadir",
            aktivitas="Teks aktivitas terlalu pendek [ev1].",
            pembelajaran="Belajar arsitektur.",
            kendala="Tidak ada kendala teknis.",
            evidence_refs={"aktivitas": ["ev1"]},
            needs_input=[],
            prompt_version="v1",
            model="gemini-2.5-flash",
        )
    if reason == "canned_filler":
        # Mengandung frasa filler klise
        return LogEntryDraft(
            work_date=work_date,
            kehadiran="Hadir",
            aktivitas=(
                "Aktivitas magang hari ini berjalan dengan lancar tanpa ada kendala sama sekali "
                "dan seluruh target modul login selesai dikerjakan sesuai arahan [ev1]."
            ),
            pembelajaran=(
                "Mempelajari sistem integrasi autentikasi portal magang secara menyeluruh "
                "serta dokumentasi terkait [ev1]."
            ),
            kendala="tidak menemui kendala yang berarti selama pelaksanaan pekerjaan harian.",
            evidence_refs={"aktivitas": ["ev1"]},
            needs_input=[],
            prompt_version="v1",
            model="gemini-2.5-flash",
        )
    # Default format violation (markdown bullet & backticks)
    return LogEntryDraft(
        work_date=work_date,
        kehadiran="Hadir",
        aktivitas=(
            "- Melakukan pengujian fitur `auth_login` secara intensif pada lingkungan staging "
            "instansi kemnaker dengan parameter keamanan ketat [ev1]."
        ),
        pembelajaran=(
            "Mempelajari arsitektur otorisasi berbasis token JWT serta teknik isolasi hak akses "
            "pada sistem backend pemerintahan berbasis Python [ev1]."
        ),
        kendala=(
            "Menghadapi inkonsistensi waktu timeout pada gateway autentikasi eksternal dan "
            "mengatasinya dengan implementasi retry mechanism exponential backoff [ev1]."
        ),
        evidence_refs={"aktivitas": ["ev1"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )


def test_initial_draft_succeeds_without_retries(tmp_path: Path) -> None:
    """Percobaan pertama langsung valid, tidak menggunakan jatah retry dan status VALIDATED."""
    target_date = date(2026, 10, 27)
    valid_draft = _make_valid_draft(target_date)
    client = SequenceMockModelClient([valid_draft])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter)

    result = stage.draft_and_validate(
        target_date=target_date,
        evidence=[_make_evidence("ev1")],
        artifacts_dir=tmp_path / "artifacts",
    )

    assert result.is_valid is True
    assert result.attempts == 1
    assert result.retries_used == 0
    assert result.status == Status.BERHASIL
    assert result.final_state == PipelineState.VALIDATED
    assert result.exit_code == 0
    assert len(client.call_history) == 1

    # Verifikasi artifak
    date_dir = tmp_path / "artifacts" / target_date.isoformat()
    assert (date_dir / "draft_attempt_1.json").exists()
    assert (date_dir / "validation_attempt_1.json").exists()
    assert (date_dir / "draft.json").exists()
    assert (date_dir / "validated.json").exists()


def test_self_correction_recovery_on_retry_1(tmp_path: Path) -> None:
    """Percobaan 1 gagal validasi (canned filler), dikoreksi pada retry 1 dengan feedback error spesifik."""
    target_date = date(2026, 10, 27)
    invalid_draft = _make_invalid_draft(target_date, reason="canned_filler")
    valid_draft = _make_valid_draft(target_date)

    client = SequenceMockModelClient([invalid_draft, valid_draft])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    result = stage.draft_and_validate(
        target_date=target_date,
        evidence=[_make_evidence("ev1")],
        artifacts_dir=tmp_path / "artifacts",
    )

    assert result.is_valid is True
    assert result.attempts == 2
    assert result.retries_used == 1
    assert result.status == Status.BERHASIL
    assert result.final_state == PipelineState.VALIDATED
    assert result.exit_code == 0
    assert len(client.call_history) == 2

    # Verifikasi feedback prompt memuat diagnostik error filler
    second_call = client.call_history[1]
    assert "CATATAN VALIDASI & PERBAIKAN" in second_call["user_payload"]
    assert "frasa filler terlarang" in second_call["user_payload"]
    assert "berjalan dengan lancar tanpa ada kendala" in second_call["user_payload"]

    # Verifikasi penyimpanan artifak intermediate
    date_dir = tmp_path / "artifacts" / target_date.isoformat()
    assert (date_dir / "draft_attempt_1.json").exists()
    assert (date_dir / "validation_attempt_1.json").exists()
    assert (date_dir / "feedback_attempt_1.txt").exists()
    assert (date_dir / "draft_attempt_2.json").exists()
    assert (date_dir / "validation_attempt_2.json").exists()
    assert (date_dir / "draft.json").exists()
    assert (date_dir / "validated.json").exists()


def test_self_correction_recovery_on_retry_2(tmp_path: Path) -> None:
    """Percobaan 1 & 2 gagal, berhasil pulih pada retry 2 (attempt 3)."""
    target_date = date(2026, 10, 27)
    attempt1 = _make_invalid_draft(target_date, reason="short")
    attempt2 = _make_invalid_draft(target_date, reason="markdown")
    attempt3 = _make_valid_draft(target_date)

    client = SequenceMockModelClient([attempt1, attempt2, attempt3])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    result = stage.draft_and_validate(
        target_date=target_date,
        evidence=[_make_evidence("ev1")],
        artifacts_dir=tmp_path / "artifacts",
    )

    assert result.is_valid is True
    assert result.attempts == 3
    assert result.retries_used == 2
    assert result.final_state == PipelineState.VALIDATED
    assert result.exit_code == 0
    assert len(client.call_history) == 3

    # Verifikasi dua file feedback prompt tersimpan
    date_dir = tmp_path / "artifacts" / target_date.isoformat()
    assert (date_dir / "feedback_attempt_1.txt").exists()
    assert (date_dir / "feedback_attempt_2.txt").exists()
    assert (date_dir / "draft.json").exists()


def test_retry_exhaustion_halts_with_perlu_review_exit_code_10(tmp_path: Path) -> None:
    """Ketika 2x retries habis dan validasi masih gagal, tahap berhenti dengan status PERLU_REVIEW (exit 10)."""
    target_date = date(2026, 10, 27)
    # Semua 3 percobaan gagal
    attempt1 = _make_invalid_draft(target_date, reason="short")
    attempt2 = _make_invalid_draft(target_date, reason="short")
    attempt3 = _make_invalid_draft(target_date, reason="short")

    client = SequenceMockModelClient([attempt1, attempt2, attempt3])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    result = stage.draft_and_validate(
        target_date=target_date,
        evidence=[_make_evidence("ev1")],
        artifacts_dir=tmp_path / "artifacts",
    )

    assert result.is_valid is False
    assert result.attempts == 3
    assert result.retries_used == 2
    assert result.status == Status.PERLU_REVIEW
    assert result.final_state == PipelineState.PERLU_REVIEW
    assert result.exit_code == 10
    assert len(client.call_history) == 3

    # Verifikasi artifak kegagalan tersimpan
    date_dir = tmp_path / "artifacts" / target_date.isoformat()
    assert (date_dir / "failed_draft.json").exists()
    assert (date_dir / "validation_report.json").exists()

    val_rep = json.loads((date_dir / "validation_report.json").read_text(encoding="utf-8"))
    assert val_rep["status"] == "PERLU_REVIEW"
    assert val_rep["exit_code"] == 10
    assert val_rep["is_valid"] is False
    assert len(val_rep["errors"]) > 0


def test_no_automatic_filler_injection_on_short_text(tmp_path: Path) -> None:
    """Sistem dilarang keras menyuntikkan atau menempelkan kalimat filler otomatis untuk mengejar kuota karakter."""
    target_date = date(2026, 10, 27)
    short_text = "Mengerjakan tugas sederhana."
    short_draft = LogEntryDraft(
        work_date=target_date,
        kehadiran="Hadir",
        aktivitas=short_text,
        pembelajaran=short_text,
        kendala=short_text,
        evidence_refs={"aktivitas": ["ev1"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )

    client = SequenceMockModelClient([short_draft, short_draft, short_draft])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    result = stage.draft_and_validate(
        target_date=target_date,
        evidence=[_make_evidence("ev1")],
        artifacts_dir=tmp_path / "artifacts",
    )

    # Teks akhir TIDAK BOLEH mengandung frasa canned filler apa pun
    for canned in CANNED_FILLER_PHRASES:
        assert canned not in result.draft.aktivitas.lower()
        assert canned not in result.draft.pembelajaran.lower()
        assert canned not in result.draft.kendala.lower()

    # Teks aktivitas harus persis sama dengan output model tanpa padding buatan
    assert result.draft.aktivitas == short_text
    assert result.status == Status.PERLU_REVIEW
    assert result.exit_code == 10


def test_pipeline_coordinator_integrated_with_drafting_stage_recovery(tmp_path: Path) -> None:
    """PipelineCoordinator terintegrasi dengan DraftingStage dan pulih lewat retry feedback loop."""
    target_date = date(2026, 10, 27)
    invalid_draft = _make_invalid_draft(target_date, reason="canned_filler")
    valid_draft = _make_valid_draft(target_date)

    client = SequenceMockModelClient([invalid_draft, valid_draft])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    # Setup pipeline coordinator
    db_path = tmp_path / "state.db"
    artifacts_dir = tmp_path / "runs"
    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)

    from unittest.mock import MagicMock

    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="ev1",
            work_date=target_date,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: implementasi login portal",
            strength="strong",
        )
    ]

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        collector=collector,
        drafter=stage,
        approval=None,
        portal=None,
        artifacts_dir=artifacts_dir,
    )

    result = coordinator.run(target_date=target_date)

    # Berhasil pulih dari kegagalan draf pertama, mencapai persetujuan/review tertunda
    assert result.status == Status.PERLU_REVIEW
    assert result.error_code == "AWAITING_APPROVAL"
    assert result.exit_code == 10
    assert len(client.call_history) == 2


def test_pipeline_coordinator_integrated_retry_exhaustion_perlu_review(tmp_path: Path) -> None:
    """PipelineCoordinator menghentikan eksekusi dengan PERLU_REVIEW (exit 10) saat retry habis."""
    target_date = date(2026, 10, 27)
    invalid_draft = _make_invalid_draft(target_date, reason="short")

    client = SequenceMockModelClient([invalid_draft, invalid_draft, invalid_draft])
    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter, max_retries=2)

    db_path = tmp_path / "state.db"
    artifacts_dir = tmp_path / "runs"
    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)

    from unittest.mock import MagicMock

    collector = MagicMock()
    collector.collect.return_value = [
        EvidenceItem(
            id="ev1",
            work_date=target_date,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: implementasi login portal",
            strength="strong",
        )
    ]

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        collector=collector,
        drafter=stage,
        approval=None,
        portal=None,
        artifacts_dir=artifacts_dir,
    )

    result = coordinator.run(target_date=target_date)

    # Karena semua retry gagal, pipeline berhenti pada PERLU_REVIEW dengan exit code 10
    assert result.final_state == PipelineState.PERLU_REVIEW
    assert result.status == Status.PERLU_REVIEW
    assert result.exit_code == 10
    assert result.error_code == "VALIDATION_FAILED"
    assert len(client.call_history) == 3
