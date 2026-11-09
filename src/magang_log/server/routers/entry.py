"""LocalDashboard API endpoints for logbook entry lifecycle: today's draft, editing, and approval."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ...store import LedgerStore
from ..services.entry_service import (
    ApproveEntryRequest,
    ApproveEntryResponse,
    DraftEntryRequest,
    DraftEntryResponse,
    EditEntryRequest,
    EditEntryResponse,
    EntryDetailResponse,
    approve_and_submit_entry,
    edit_entry,
    get_today_entry,
    regenerate_draft,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["entry"])


@router.get(
    "/entry/today",
    response_model=EntryDetailResponse,
    summary="Get today's active logbook entry with validation status",
)
def get_entry_today(
    date_str: str | None = Query(default=None, alias="date", description="Target date YYYY-MM-DD"),
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Return active logbook entry for target date or 404 if not found."""
    try:
        target_d = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Expected YYYY-MM-DD: {date_str}",
        ) from exc

    store = LedgerStore(db_path=db_path or "data/state.db")
    entry_data = get_today_entry(target_date=target_d, store=store)

    if entry_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active entry or draft found for date {target_d.isoformat()}",
        )

    return entry_data


@router.post(
    "/entry/edit",
    response_model=EditEntryResponse,
    summary="Update active draft fields and re-evaluate validation",
)
def post_entry_edit(
    req: EditEntryRequest,
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Edit draft fields and re-run deterministic multi-stage validation."""
    store = LedgerStore(db_path=db_path or "data/state.db")
    try:
        return edit_entry(req=req, store=store)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to edit draft entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Draft update error: {exc}",
        ) from exc


@router.post(
    "/entry/draft",
    response_model=DraftEntryResponse,
    summary="Regenerate AI draft for date from collected evidence",
)
def post_entry_draft(
    req: DraftEntryRequest | None = None,
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Generate or regenerate draft for target date."""
    target_d = date.fromisoformat(req.work_date) if req and req.work_date else date.today()
    store = LedgerStore(db_path=db_path or "data/state.db")
    try:
        return regenerate_draft(target_date=target_d, store=store)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to regenerate draft: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Draft generation error: {exc}",
        ) from exc


@router.post(
    "/entry/approve",
    response_model=ApproveEntryResponse,
    summary="Approve active validated draft and coordinate submission to portal",
)
def post_entry_approve(
    req: ApproveEntryRequest | None = None,
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Approve validated draft and submit to MagangHub portal."""
    target_d = date.fromisoformat(req.work_date) if req and req.work_date else date.today()
    dry_run = req.dry_run if req else False
    store = LedgerStore(db_path=db_path or "data/state.db")

    try:
        return approve_and_submit_entry(
            target_date=target_d,
            store=store,
            dry_run=dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to approve and submit entry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval submission error: {exc}",
        ) from exc
