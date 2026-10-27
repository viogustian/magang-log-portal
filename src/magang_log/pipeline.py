"""Modul Pipeline Coordinator & State Machine Engine untuk alur kerja logbook harian."""

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from .drafter.models import LogEntryDraft
from .drafter.stage import DraftingStage
from .gates import GateDecision, PreflightGate, generate_run_id
from .models import (
    EXIT_CODES,
    ApprovedEntry,
    EntryRecord,
    EvidenceItem,
    NoteRecord,
    PortalResult,
    RunRecord,
    Status,
)
from .store import LedgerStore


class PipelineState(StrEnum):
    """Tahap status pemrosesan state machine unidirectional."""

    START = "START"
    GATED = "GATED"
    COLLECTED = "COLLECTED"
    DRAFTED = "DRAFTED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"

    # Terminal states / outcomes
    LIBUR = "LIBUR"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"
    PERLU_INPUT = "PERLU_INPUT"
    PERLU_REVIEW = "PERLU_REVIEW"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    DRYRUN = "DRYRUN"
    BERHASIL = "BERHASIL"
    GAGAL = "GAGAL"
    LOGIN_DIPERLUKAN = "LOGIN_DIPERLUKAN"
    TERKUNCI = "TERKUNCI"
    LOKASI_TIDAK_TERSEDIA = "LOKASI_TIDAK_TERSEDIA"


class InvalidTransitionError(Exception):
    """Kesalahan percobaan transisi status yang tidak valid atau non-unidirectional."""


VALID_TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.START: {PipelineState.GATED},
    PipelineState.GATED: {
        PipelineState.LIBUR,
        PipelineState.SUDAH_TERKIRIM,
        PipelineState.COLLECTED,
    },
    PipelineState.COLLECTED: {
        PipelineState.PERLU_INPUT,
        PipelineState.DRAFTED,
    },
    PipelineState.DRAFTED: {
        PipelineState.PERLU_REVIEW,
        PipelineState.VALIDATED,
        PipelineState.VALIDATION_FAILED,
    },
    PipelineState.VALIDATED: {
        PipelineState.APPROVED,
        PipelineState.PERLU_REVIEW,
    },
    PipelineState.APPROVED: {
        PipelineState.SUBMITTED,
        PipelineState.DRYRUN,
    },
    PipelineState.SUBMITTED: {
        PipelineState.BERHASIL,
        PipelineState.GAGAL,
        PipelineState.LOGIN_DIPERLUKAN,
        PipelineState.TERKUNCI,
        PipelineState.LOKASI_TIDAK_TERSEDIA,
    },
}


class StateMachine:
    """State machine unidirectional yang menegakkan alur transisi status yang sah."""

    def __init__(self, initial_state: PipelineState = PipelineState.START) -> None:
        self.current_state: PipelineState = initial_state
        self.history: list[PipelineState] = [initial_state]

    def transition_to(self, next_state: PipelineState) -> PipelineState:
        allowed = VALID_TRANSITIONS.get(self.current_state, set())
        if next_state not in allowed:
            raise InvalidTransitionError(
                f"Transisi tidak valid dari {self.current_state} ke {next_state}. "
                f"Status yang diizinkan: {sorted(s.value for s in allowed)}"
            )
        self.current_state = next_state
        self.history.append(next_state)
        return next_state


@dataclass
class DraftResult:
    """Hasil pembuatan draf aktivitas harian oleh AI."""

    draft_json: str
    prompt_version: str = "v2"
    model: str = "gemini-2.5-flash"
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class ValidationResult:
    """Hasil evaluasi validasi terhadap draf logbook."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validated_payload: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    """Hasil akhir eksekusi pipeline coordinator."""

    run_id: str
    target_date: date
    final_state: PipelineState
    status: Status
    exit_code: int
    duration_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    error_code: str | None = None
    note: str = ""
    entry: EntryRecord | None = None
    artifacts: dict[str, Path] = field(default_factory=dict)


def compute_content_hash(text: str) -> str:
    """Menghitung SHA-256 hexdigest dari teks untuk pemeriksaan idempotensi."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_text_for_ratio(val: Any) -> str:
    if isinstance(val, ApprovedEntry):
        return f"{val.aktivitas.strip()}\n{val.pembelajaran.strip()}\n{val.kendala.strip()}"
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict) and "aktivitas" in parsed:
                return f"{parsed.get('aktivitas', '').strip()}\n{parsed.get('pembelajaran', '').strip()}\n{parsed.get('kendala', '').strip()}"
        except (json.JSONDecodeError, TypeError):
            return val.strip()
    if isinstance(val, dict):
        return f"{val.get('aktivitas', '').strip()}\n{val.get('pembelajaran', '').strip()}\n{val.get('kendala', '').strip()}"
    return str(val).strip()


def calculate_edit_ratio(draft_input: Any, approved_input: Any) -> float:
    """Menghitung rasio pengeditan (1.0 - difflib.SequenceMatcher.ratio())."""
    draft_text = _normalize_text_for_ratio(draft_input)
    approved_text = _normalize_text_for_ratio(approved_input)
    if not draft_text and not approved_text:
        return 0.0
    ratio = difflib.SequenceMatcher(None, draft_text, approved_text).ratio()
    return round(1.0 - ratio, 4)


class CollectorStage(Protocol):
    """Antarmuka pengumpul bukti aktivitas."""

    def collect(self, target_date: date) -> list[EvidenceItem]: ...


class DrafterStage(Protocol):
    """Antarmuka pembuat draf AI logbook."""

    def draft(
        self,
        target_date: date,
        evidence: list[EvidenceItem],
        notes: list[NoteRecord] | None = None,
    ) -> DraftResult: ...


class ValidatorStage(Protocol):
    """Antarmuka validator aturan dan batas teks."""

    def validate(self, draft: DraftResult, target_date: date) -> ValidationResult: ...


class ApprovalStage(Protocol):
    """Antarmuka persetujuan manusia."""

    def review_and_approve(
        self,
        target_date: date,
        draft: DraftResult,
        validation: ValidationResult,
    ) -> ApprovedEntry | None: ...


class PortalStage(Protocol):
    """Antarmuka pengiriman dan verifikasi portal."""

    def submit(self, entry: ApprovedEntry, dry_run: bool = False) -> PortalResult: ...


class ArtifactStore:
    """Penyimpanan artifak sementara pada disk untuk mendukung pemulihan (--resume)."""

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def _date_dir(self, target_date: date) -> Path:
        d = self.artifacts_dir / target_date.isoformat()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_evidence(self, target_date: date, evidence: list[EvidenceItem]) -> Path:
        path = self._date_dir(target_date) / "evidence.json"
        data = [
            {
                "id": item.id,
                "work_date": item.work_date.isoformat(),
                "source": item.source,
                "kind": item.kind,
                "ts": item.ts.isoformat() if isinstance(item.ts, datetime) else str(item.ts),
                "title": item.title,
                "detail": item.detail,
                "strength": item.strength,
            }
            for item in evidence
        ]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_evidence(self, target_date: date) -> list[EvidenceItem] | None:
        path = self._date_dir(target_date) / "evidence.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                EvidenceItem(
                    id=d["id"],
                    work_date=date.fromisoformat(d["work_date"]),
                    source=d["source"],
                    kind=d["kind"],
                    ts=d["ts"],
                    title=d["title"],
                    detail=d.get("detail", ""),
                    strength=d.get("strength", "strong"),
                )
                for d in data
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def save_draft(self, target_date: date, draft: DraftResult | LogEntryDraft) -> Path:
        path = self._date_dir(target_date) / "draft.json"
        if isinstance(draft, LogEntryDraft):
            draft_json_str = draft.model_dump_json()
            prompt_ver = getattr(draft, "prompt_version", "v1")
            mod = getattr(draft, "model", "gemini-2.5-flash")
            tok_in = 0
            tok_out = 0
        else:
            draft_json_str = draft.draft_json
            prompt_ver = draft.prompt_version
            mod = draft.model
            tok_in = draft.tokens_in
            tok_out = draft.tokens_out

        data = {
            "draft_json": draft_json_str,
            "prompt_version": prompt_ver,
            "model": mod,
            "tokens_in": tok_in,
            "tokens_out": tok_out,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_draft(self, target_date: date) -> DraftResult | None:
        path = self._date_dir(target_date) / "draft.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return DraftResult(
                draft_json=data["draft_json"],
                prompt_version=data.get("prompt_version", "v2"),
                model=data.get("model", "gemini-2.5-flash"),
                tokens_in=data.get("tokens_in", 0),
                tokens_out=data.get("tokens_out", 0),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def save_validation(self, target_date: date, validation: ValidationResult) -> Path:
        path = self._date_dir(target_date) / "validated.json"
        data = {
            "is_valid": validation.is_valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "validated_payload": validation.validated_payload,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_validation(self, target_date: date) -> ValidationResult | None:
        path = self._date_dir(target_date) / "validated.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return ValidationResult(
                is_valid=data["is_valid"],
                errors=data.get("errors", []),
                warnings=data.get("warnings", []),
                validated_payload=data.get("validated_payload"),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def save_approval(self, target_date: date, entry: ApprovedEntry) -> Path:
        path = self._date_dir(target_date) / "approved.json"
        data = {
            "work_date": entry.work_date.isoformat(),
            "aktivitas": entry.aktivitas,
            "pembelajaran": entry.pembelajaran,
            "kendala": entry.kendala,
            "approved_at": entry.approved_at.isoformat() if entry.approved_at else None,
            "kehadiran": entry.kehadiran,
            "edit_ratio": entry.edit_ratio,
            "content_hash": entry.content_hash,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_approval(self, target_date: date) -> ApprovedEntry | None:
        path = self._date_dir(target_date) / "approved.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            approved_at = data.get("approved_at")
            return ApprovedEntry(
                work_date=date.fromisoformat(data["work_date"]),
                aktivitas=data["aktivitas"],
                pembelajaran=data["pembelajaran"],
                kendala=data["kendala"],
                approved_at=datetime.fromisoformat(approved_at) if approved_at else None,
                kehadiran=data.get("kehadiran", "Hadir"),
                edit_ratio=float(data.get("edit_ratio", 0.0)),
                content_hash=data.get("content_hash", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


class PipelineCoordinator:
    """Koordinator alur eksekusi logbook harian terintegrasi."""

    def __init__(
        self,
        store: LedgerStore,
        preflight_gate: PreflightGate,
        collector: CollectorStage | None = None,
        drafter: DrafterStage | None = None,
        validator: ValidatorStage | None = None,
        approval: ApprovalStage | None = None,
        portal: PortalStage | None = None,
        artifacts_dir: Path | None = None,
    ) -> None:
        self.store = store
        self.preflight_gate = preflight_gate
        self.collector = collector
        self.drafter = drafter
        self.validator = validator
        self.approval = approval
        self.portal = portal
        self.artifacts_dir = artifacts_dir or Path("data/runs")
        self.artifact_store = ArtifactStore(self.artifacts_dir)

    def _record_audit_run(
        self,
        run_id: str,
        target_date: date,
        stage: PipelineState,
        status: Status,
        started_at: datetime,
        tokens_in: int = 0,
        tokens_out: int = 0,
        error_code: str | None = None,
    ) -> int:
        finished_at = datetime.now()
        duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        self.store.record_run(
            RunRecord(
                run_id=run_id,
                work_date=target_date,
                stage=stage.value,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=duration_ms,
                error_code=error_code,
            )
        )
        return duration_ms

    def run(
        self,
        target_date: date,
        dry_run: bool = False,
        resume: bool = False,
        force: bool = False,
    ) -> PipelineResult:
        started_at = datetime.now()
        run_id = generate_run_id(target_date)
        sm = StateMachine(PipelineState.START)
        artifacts: dict[str, Path] = {}
        tokens_in = 0
        tokens_out = 0

        try:
            # 1. START -> GATED
            sm.transition_to(PipelineState.GATED)
            gate_res = self.preflight_gate.inspect(target_date, force=force, run_id=run_id)

            if gate_res.decision == GateDecision.LIBUR:
                sm.transition_to(PipelineState.LIBUR)
                dur = self._record_audit_run(
                    run_id, target_date, PipelineState.LIBUR, Status.LIBUR, started_at
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.LIBUR,
                    status=Status.LIBUR,
                    exit_code=EXIT_CODES[Status.LIBUR],
                    duration_ms=dur,
                    note=gate_res.reason,
                    artifacts=artifacts,
                )

            if gate_res.decision == GateDecision.SUDAH_TERKIRIM:
                sm.transition_to(PipelineState.SUDAH_TERKIRIM)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.SUDAH_TERKIRIM,
                    Status.SUDAH_TERKIRIM,
                    started_at,
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.SUDAH_TERKIRIM,
                    status=Status.SUDAH_TERKIRIM,
                    exit_code=EXIT_CODES[Status.SUDAH_TERKIRIM],
                    duration_ms=dur,
                    note=gate_res.reason,
                    artifacts=artifacts,
                )

            # 2. GATED -> COLLECTED
            sm.transition_to(PipelineState.COLLECTED)
            evidence: list[EvidenceItem] | None = None

            if resume:
                evidence = self.artifact_store.load_evidence(target_date)

            if evidence is None:
                if self.collector is not None:
                    evidence = self.collector.collect(target_date)
                else:
                    evidence = self.store.get_evidence(target_date)

            # Simpan bukti ke disk & ledger
            artifacts["evidence"] = self.artifact_store.save_evidence(target_date, evidence)
            if evidence:
                self.store.save_evidence(evidence)

            # Verifikasi kecukupan bukti
            has_strong = any(item.strength == "strong" for item in evidence)
            if not evidence or not has_strong:
                sm.transition_to(PipelineState.PERLU_INPUT)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.COLLECTED,
                    Status.PERLU_INPUT,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="INSUFFICIENT_EVIDENCE",
                )
                from .notify import send_system_notification

                send_system_notification(
                    title="Magang Log - Bukti Kurang",
                    message=(
                        f"Tidak ada bukti berkategori 'strong' untuk tanggal {target_date.isoformat()}. "
                        "Butuh catatan input pengguna."
                    ),
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.PERLU_INPUT,
                    status=Status.PERLU_INPUT,
                    exit_code=EXIT_CODES[Status.PERLU_INPUT],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="INSUFFICIENT_EVIDENCE",
                    note="Bukti tidak mencukupi atau tidak ada bukti berkategori 'strong'. Perlu catatan input pengguna.",
                    artifacts=artifacts,
                )

            # 3. COLLECTED -> DRAFTED
            sm.transition_to(PipelineState.DRAFTED)
            draft: DraftResult | None = None

            if resume:
                draft = self.artifact_store.load_draft(target_date)

            if draft is None:
                if self.drafter is not None and isinstance(self.drafter, DraftingStage):
                    notes = self.store.get_notes(target_date)
                    stage_res = self.drafter.draft_and_validate(
                        target_date=target_date,
                        evidence=evidence,
                        notes=notes,
                        artifacts_dir=self.artifacts_dir,
                    )
                    tokens_in += stage_res.tokens_in
                    tokens_out += stage_res.tokens_out
                    artifacts.update(stage_res.artifacts)

                    draft_json = stage_res.draft.model_dump_json(indent=2)
                    draft = DraftResult(
                        draft_json=draft_json,
                        prompt_version=stage_res.draft.prompt_version,
                        model=stage_res.draft.model,
                        tokens_in=stage_res.tokens_in,
                        tokens_out=stage_res.tokens_out,
                    )
                    artifacts["draft"] = self.artifact_store.save_draft(target_date, draft)

                    draft_hash = compute_content_hash(draft.draft_json)
                    self.store.save_entry(
                        EntryRecord(
                            work_date=target_date,
                            draft_json=draft.draft_json,
                            prompt_version=draft.prompt_version,
                            model=draft.model,
                            content_hash=draft_hash,
                        )
                    )

                    validation = ValidationResult(
                        is_valid=stage_res.validation.is_valid,
                        errors=stage_res.validation.errors,
                        warnings=stage_res.validation.warnings,
                        validated_payload=stage_res.draft.model_dump(mode="json"),
                    )
                    artifacts["validation"] = self.artifact_store.save_validation(
                        target_date, validation
                    )

                    if not stage_res.is_valid:
                        sm.transition_to(PipelineState.PERLU_REVIEW)
                        dur = self._record_audit_run(
                            run_id,
                            target_date,
                            PipelineState.DRAFTED,
                            Status.PERLU_REVIEW,
                            started_at,
                            tokens_in=tokens_in,
                            tokens_out=tokens_out,
                            error_code="VALIDATION_FAILED",
                        )
                        return PipelineResult(
                            run_id=run_id,
                            target_date=target_date,
                            final_state=PipelineState.PERLU_REVIEW,
                            status=Status.PERLU_REVIEW,
                            exit_code=EXIT_CODES[Status.PERLU_REVIEW],
                            duration_ms=dur,
                            tokens_in=tokens_in,
                            tokens_out=tokens_out,
                            error_code="VALIDATION_FAILED",
                            note=f"Validasi draf belum lolos setelah percobaan retry: {'; '.join(stage_res.validation.errors)}",
                            artifacts=artifacts,
                        )

                    sm.transition_to(PipelineState.VALIDATED)
                elif self.drafter is not None:
                    notes = self.store.get_notes(target_date)
                    draft = self.drafter.draft(target_date, evidence, notes)
                else:
                    # Draf fallback minimal jika drafter belum disuplai
                    sample_json = json.dumps(
                        {
                            "aktivitas": f"Mengerjakan aktivitas harian tanggal {target_date.isoformat()}.",
                            "pembelajaran": "Memahami arsitektur pipeline dan validasi logbook.",
                            "kendala": "Tidak ada kendala yang berarti selama pengerjaan.",
                        }
                    )
                    draft = DraftResult(draft_json=sample_json)

            if "draft" not in artifacts and draft is not None:
                tokens_in += draft.tokens_in
                tokens_out += draft.tokens_out
                artifacts["draft"] = self.artifact_store.save_draft(target_date, draft)

                # Catat draf ke ledger entri awal
                draft_hash = compute_content_hash(draft.draft_json)
                self.store.save_entry(
                    EntryRecord(
                        work_date=target_date,
                        draft_json=draft.draft_json,
                        prompt_version=draft.prompt_version,
                        model=draft.model,
                        content_hash=draft_hash,
                    )
                )

            # 4. Validasi Draf: DRAFTED -> VALIDATED / PERLU_REVIEW / VALIDATION_FAILED
            if sm.current_state != PipelineState.VALIDATED:
                validation: ValidationResult | None = None
                if resume:
                    validation = self.artifact_store.load_validation(target_date)

                if validation is None:
                    if self.validator is not None:
                        validation = self.validator.validate(draft, target_date)
                    else:
                        validation = ValidationResult(is_valid=True)

                artifacts["validation"] = self.artifact_store.save_validation(
                    target_date, validation
                )

            if not validation.is_valid:
                # Periksa apakah ini kegagalan validasi total atau perlu review manusia
                # Jika ada errors terdeteksi, transisi ke PERLU_REVIEW (exit 10) atau VALIDATION_FAILED (exit 30)
                sm.transition_to(PipelineState.PERLU_REVIEW)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.DRAFTED,
                    Status.PERLU_REVIEW,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="VALIDATION_FAILED",
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.PERLU_REVIEW,
                    status=Status.PERLU_REVIEW,
                    exit_code=EXIT_CODES[Status.PERLU_REVIEW],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="VALIDATION_FAILED",
                    note=f"Validasi draf belum lolos: {'; '.join(validation.errors)}",
                    artifacts=artifacts,
                )

            if sm.current_state != PipelineState.VALIDATED:
                sm.transition_to(PipelineState.VALIDATED)

            # 5. VALIDATED -> APPROVED / PERLU_REVIEW
            approved_entry: ApprovedEntry | None = None
            if resume:
                approved_entry = self.artifact_store.load_approval(target_date)

            if approved_entry is None:
                if self.approval is not None:
                    approved_entry = self.approval.review_and_approve(
                        target_date, draft, validation
                    )
                else:
                    approved_entry = None

            if approved_entry is None or approved_entry.approved_at is None:
                sm.transition_to(PipelineState.PERLU_REVIEW)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.VALIDATED,
                    Status.PERLU_REVIEW,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="AWAITING_APPROVAL",
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.PERLU_REVIEW,
                    status=Status.PERLU_REVIEW,
                    exit_code=EXIT_CODES[Status.PERLU_REVIEW],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="AWAITING_APPROVAL",
                    note="Draf valid menanti tinjauan dan persetujuan pengguna.",
                    artifacts=artifacts,
                )

            # Hitung edit_ratio & simpan persetujuan
            edit_ratio = calculate_edit_ratio(draft.draft_json, approved_entry)
            approved_hash = compute_content_hash(
                f"{approved_entry.aktivitas}\n{approved_entry.pembelajaran}\n{approved_entry.kendala}"
            )
            artifacts["approval"] = self.artifact_store.save_approval(target_date, approved_entry)

            approved_json_str = json.dumps(
                {
                    "aktivitas": approved_entry.aktivitas,
                    "pembelajaran": approved_entry.pembelajaran,
                    "kendala": approved_entry.kendala,
                    "kehadiran": approved_entry.kehadiran,
                    "approved_at": approved_entry.approved_at.isoformat(),
                }
            )

            self.store.set_approved(
                work_date=target_date,
                approved_json=approved_json_str,
                approved_at=approved_entry.approved_at,
                edit_ratio=edit_ratio,
            )

            # Update content_hash di entries
            current_entry = self.store.get_entry(target_date)
            if current_entry:
                current_entry.content_hash = approved_hash
                self.store.save_entry(current_entry)

            sm.transition_to(PipelineState.APPROVED)

            # 6. APPROVED -> DRYRUN / SUBMITTED
            if dry_run:
                sm.transition_to(PipelineState.DRYRUN)
                if self.portal is not None:
                    self.portal.submit(approved_entry, dry_run=True)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.APPROVED,
                    Status.DRYRUN,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.DRYRUN,
                    status=Status.DRYRUN,
                    exit_code=EXIT_CODES[Status.DRYRUN],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    note="Dry-run selesai dengan sukses tanpa pengiriman final.",
                    entry=self.store.get_entry(target_date),
                    artifacts=artifacts,
                )

            # SUBMISSION AKTIF
            sm.transition_to(PipelineState.SUBMITTED)
            if self.portal is None:
                raise RuntimeError(
                    "Komponen portal submitter belum dikonfigurasi untuk pengiriman aktif."
                )

            portal_res = self.portal.submit(approved_entry, dry_run=False)

            if portal_res.status == Status.BERHASIL:
                sm.transition_to(PipelineState.BERHASIL)
                self.store.mark_submitted(target_date, portal_status=Status.BERHASIL)
                self.store.mark_verified(target_date, portal_status=Status.SUDAH_TERKIRIM)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.SUBMITTED,
                    Status.BERHASIL,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.BERHASIL,
                    status=Status.BERHASIL,
                    exit_code=EXIT_CODES[Status.BERHASIL],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    note=portal_res.note,
                    entry=self.store.get_entry(target_date),
                    artifacts=artifacts,
                )

            if portal_res.status == Status.LOGIN_DIPERLUKAN:
                sm.transition_to(PipelineState.LOGIN_DIPERLUKAN)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.SUBMITTED,
                    Status.LOGIN_DIPERLUKAN,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="LOGIN_REQUIRED",
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.LOGIN_DIPERLUKAN,
                    status=Status.LOGIN_DIPERLUKAN,
                    exit_code=EXIT_CODES[Status.LOGIN_DIPERLUKAN],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="LOGIN_REQUIRED",
                    note=portal_res.note,
                    entry=self.store.get_entry(target_date),
                    artifacts=artifacts,
                )

            if portal_res.status == Status.TERKUNCI:
                sm.transition_to(PipelineState.TERKUNCI)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.SUBMITTED,
                    Status.TERKUNCI,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="DATE_LOCKED",
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.TERKUNCI,
                    status=Status.TERKUNCI,
                    exit_code=EXIT_CODES[Status.TERKUNCI],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="DATE_LOCKED",
                    note=portal_res.note,
                    entry=self.store.get_entry(target_date),
                    artifacts=artifacts,
                )

            if portal_res.status == Status.LOKASI_TIDAK_TERSEDIA:
                sm.transition_to(PipelineState.LOKASI_TIDAK_TERSEDIA)
                dur = self._record_audit_run(
                    run_id,
                    target_date,
                    PipelineState.SUBMITTED,
                    Status.LOKASI_TIDAK_TERSEDIA,
                    started_at,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="LOCATION_UNAVAILABLE",
                )
                return PipelineResult(
                    run_id=run_id,
                    target_date=target_date,
                    final_state=PipelineState.LOKASI_TIDAK_TERSEDIA,
                    status=Status.LOKASI_TIDAK_TERSEDIA,
                    exit_code=EXIT_CODES[Status.LOKASI_TIDAK_TERSEDIA],
                    duration_ms=dur,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    error_code="LOCATION_UNAVAILABLE",
                    note=portal_res.note,
                    entry=self.store.get_entry(target_date),
                    artifacts=artifacts,
                )

            # Kegagalan pengiriman umum
            sm.transition_to(PipelineState.GAGAL)
            dur = self._record_audit_run(
                run_id,
                target_date,
                PipelineState.SUBMITTED,
                Status.GAGAL,
                started_at,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error_code="SUBMISSION_FAILED",
            )
            return PipelineResult(
                run_id=run_id,
                target_date=target_date,
                final_state=PipelineState.GAGAL,
                status=Status.GAGAL,
                exit_code=EXIT_CODES[Status.GAGAL],
                duration_ms=dur,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error_code="SUBMISSION_FAILED",
                note=portal_res.note,
                entry=self.store.get_entry(target_date),
                artifacts=artifacts,
            )

        except Exception as exc:  # noqa: BLE001
            # Penanganan kegagalan tak terduga: catat ke audit runs dan keluar dengan kode 1
            finished_at = datetime.now()
            duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
            err_name = exc.__class__.__name__
            try:
                self.store.record_run(
                    RunRecord(
                        run_id=run_id,
                        work_date=target_date,
                        stage=sm.current_state.value,
                        status=Status.GAGAL,
                        started_at=started_at,
                        finished_at=finished_at,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        duration_ms=duration_ms,
                        error_code=err_name,
                    )
                )
            except Exception:  # noqa: BLE001, S110
                pass

            return PipelineResult(
                run_id=run_id,
                target_date=target_date,
                final_state=sm.current_state,
                status=Status.GAGAL,
                exit_code=1,
                duration_ms=duration_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                error_code=err_name,
                note=str(exc),
                artifacts=artifacts,
            )
