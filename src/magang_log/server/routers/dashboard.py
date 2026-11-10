"""LocalDashboard API endpoints for status, reflection notes, and evidence feed."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ...settings import load_config
from ...store import LedgerStore
from ..services.dashboard_service import (
    CreateNoteRequest,
    CreateNoteResponse,
    EvidenceFeedResponse,
    TodayStatusResponse,
    create_reflection_note,
    get_today_evidence,
    get_today_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get(
    "/status/today",
    response_model=TodayStatusResponse,
    summary="Evaluate pipeline, gate, and ledger status for today",
)
def check_status_today(
    date_str: str | None = Query(default=None, alias="date", description="Target date YYYY-MM-DD"),
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Return pipeline status evaluation across calendar gates and ledger."""
    try:
        target_d = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected YYYY-MM-DD: {date_str}",
        ) from exc

    store = LedgerStore(db_path=db_path or "data/state.db")
    config = load_config()

    try:
        return get_today_status(target_date=target_d, config=config, store=store)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to evaluate today's status: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status evaluation error: {exc}",
        ) from exc


@router.post(
    "/notes",
    response_model=CreateNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit manual reflection note fallback (ADR-0003)",
)
def add_note(req: CreateNoteRequest) -> dict[str, Any]:
    """Store manual reflection note and transition pipeline state if needed."""
    try:
        return create_reflection_note(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to store reflection note: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save note: {exc}",
        ) from exc


@router.get(
    "/evidence/today",
    response_model=EvidenceFeedResponse,
    summary="Fetch sanitized evidence timeline items for today",
)
def get_evidence(
    date_str: str | None = Query(default=None, alias="date", description="Target date YYYY-MM-DD"),
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Collect evidence from all active collectors and return sanitized items."""
    try:
        target_d = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected YYYY-MM-DD: {date_str}",
        ) from exc

    store = LedgerStore(db_path=db_path or "data/state.db")
    config = load_config()

    try:
        items = get_today_evidence(target_date=target_d, config=config, store=store)
        return {"items": items}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to collect evidence feed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence collection error: {exc}",
        ) from exc
