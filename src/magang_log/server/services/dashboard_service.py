"""Dashboard service layer for today's status, reflection notes, and evidence timeline."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...collectors.factory import collect_and_sanitize_evidence
from ...gates import GateDecision, PreflightGate
from ...models import NoteRecord, RunRecord, Status
from ...settings import AppConfig, load_config
from ...store import LedgerStore

logger = logging.getLogger(__name__)


class TodayStatusResponse(BaseModel):
    """Response payload for today's pipeline status check."""

    target_date: str
    status: str
    is_workday: bool
    is_holiday: bool
    holiday_name: str | None = None
    has_submitted_entry: bool
    needs_user_action: bool


class CreateNoteRequest(BaseModel):
    """Request payload for creating a fast reflection note."""

    model_config = ConfigDict(extra="ignore")

    work_date: str = Field(..., description="Date in YYYY-MM-DD format")
    category: Literal["aktivitas", "pembelajaran", "kendala"] = Field(
        ..., description="Note category (aktivitas | pembelajaran | kendala)"
    )
    note: str = Field(..., description="Note content text")
    db: str | None = Field(default=None, description="Optional SQLite DB path for isolation")

    @field_validator("note")
    @classmethod
    def validate_note(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Note content must not be empty.")
        if len(s) > 5000:
            raise ValueError("Note content exceeds maximum limit of 5000 characters.")
        return s

    @field_validator("work_date")
    @classmethod
    def validate_work_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v.strip())
        except ValueError as exc:
            raise ValueError(f"Invalid work_date format. Expected YYYY-MM-DD: {v!r}") from exc
        return v.strip()


class CreateNoteResponse(BaseModel):
    """Response payload after creating a reflection note."""

    success: bool
    note_id: str
    created_at: str


class EvidenceItemResponse(BaseModel):
    """Sanitized evidence timeline item."""

    id: str
    source: str
    kind: str
    ts: str
    title: str
    detail: str
    strength: Literal["strong", "weak"]


class EvidenceFeedResponse(BaseModel):
    """Response payload containing list of sanitized evidence items."""

    items: list[EvidenceItemResponse]


def get_today_status(
    target_date: date | None = None,
    config: AppConfig | None = None,
    store: LedgerStore | None = None,
) -> dict[str, Any]:
    """Evaluate pipeline status for target date across gates, ledger, and collectors."""
    d = target_date or date.today()
    cfg = config or load_config()
    st = store or LedgerStore()

    gate = PreflightGate.from_config_and_store(cfg, st)
    cal_res = gate.calendar_gate.inspect(d)

    is_workday = cal_res.decision == GateDecision.WORKDAY
    is_holiday = cal_res.decision == GateDecision.LIBUR
    holiday_name = cal_res.reason if is_holiday else None

    entry = st.get_entry(d)
    runs = st.get_runs_for_date(d)

    has_submitted_entry = False
    needs_user_action = True
    final_status = "GATED"

    if entry and (
        entry.verified_at
        or entry.submitted_at
        or (
            entry.portal_status
            and entry.portal_status in ("SUDAH_TERKIRIM", "BERHASIL", "TERKIRIM")
        )
    ):
        has_submitted_entry = True
        final_status = "SUDAH_TERKIRIM"
        needs_user_action = False
    elif is_holiday:
        final_status = "LIBUR"
        needs_user_action = False
    elif entry and (entry.approved_at or entry.approved_json):
        final_status = "APPROVED"
        needs_user_action = False
    elif entry and entry.draft_json:
        final_status = "DRAFTED"
        needs_user_action = True
    elif runs:
        latest = runs[-1]
        if latest.status in (Status.SUDAH_TERKIRIM, Status.BERHASIL):
            has_submitted_entry = True
            final_status = "SUDAH_TERKIRIM"
            needs_user_action = False
        elif latest.status == Status.PERLU_REVIEW:
            final_status = "DRAFTED"
            needs_user_action = True
        elif latest.status == Status.PERLU_INPUT:
            final_status = "PERLU_INPUT"
            needs_user_action = True
        elif latest.status == Status.LIBUR:
            final_status = "LIBUR"
            needs_user_action = False
        else:
            final_status = str(latest.status)
            needs_user_action = True
    else:
        # Check if any evidence exists today
        try:
            evidence = collect_and_sanitize_evidence(d, cfg, st)
            if not evidence:
                final_status = "PERLU_INPUT"
                needs_user_action = True
            else:
                final_status = "GATED"
                needs_user_action = True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Evidence collection check encountered error: %s", exc)
            final_status = "PERLU_INPUT"
            needs_user_action = True

    return {
        "target_date": d.isoformat(),
        "status": final_status,
        "is_workday": is_workday,
        "is_holiday": is_holiday,
        "holiday_name": holiday_name,
        "has_submitted_entry": has_submitted_entry,
        "needs_user_action": needs_user_action,
    }


def create_reflection_note(
    req: CreateNoteRequest,
    store: LedgerStore | None = None,
) -> dict[str, Any]:
    """Save reflection note into SQLite store and transition state if PERLU_INPUT."""
    st = store or LedgerStore(db_path=req.db or "data/state.db")
    d = date.fromisoformat(req.work_date)

    now_utc = datetime.now(timezone.utc)
    note_rec = NoteRecord(
        work_date=d,
        kind=req.category,
        text=req.note,
        created_at=now_utc,
    )
    note_id = st.add_note(note_rec)

    # Check if latest run is PERLU_INPUT, transition forward
    runs = st.get_runs_for_date(d)
    if runs and runs[-1].status == Status.PERLU_INPUT:
        st.record_run(
            RunRecord(
                run_id=f"run-{d.strftime('%Y%m%d')}-note-transition",
                work_date=d,
                stage="DRAFTING",
                status=Status.PERLU_REVIEW,
                started_at=now_utc,
                finished_at=now_utc,
            )
        )

    return {
        "success": True,
        "note_id": str(note_id),
        "created_at": now_utc.isoformat(),
    }


def get_today_evidence(
    target_date: date | None = None,
    config: AppConfig | None = None,
    store: LedgerStore | None = None,
) -> list[dict[str, Any]]:
    """Collect and sanitize all evidence items for target date."""
    d = target_date or date.today()
    cfg = config or load_config()
    st = store or LedgerStore()

    evidence_items = collect_and_sanitize_evidence(d, cfg, st)

    results: list[dict[str, Any]] = []
    for ev in evidence_items:
        ts_iso = ev.ts.isoformat() if ev.ts else datetime.now(timezone.utc).isoformat()
        results.append(
            {
                "id": ev.id,
                "source": ev.source,
                "kind": ev.kind,
                "ts": ts_iso,
                "title": ev.title,
                "detail": ev.detail,
                "strength": ev.strength if ev.strength in ("strong", "weak") else "weak",
            }
        )

    return results
