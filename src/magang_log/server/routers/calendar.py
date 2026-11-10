"""LocalDashboard API endpoints for monthly calendar queries."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from ...settings import load_config
from ...store import LedgerStore
from ..services.calendar_service import MonthCalendarResponse, get_month_calendar

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calendar"])


@router.get(
    "/calendar/month",
    response_model=MonthCalendarResponse,
    summary="Get logbook entry statuses for all days in a month",
)
def get_calendar_month(
    year: int = Query(ge=2000, le=2100, description="Calendar year"),
    month: int = Query(ge=1, le=12, description="Calendar month (1-12)"),
    db_path: str | None = Query(default=None, alias="db", description="SQLite database path"),
) -> dict[str, Any]:
    """Query monthly status across all days for local calendar overview."""
    store = LedgerStore(db_path=db_path or "data/state.db")
    config = load_config()

    try:
        days = get_month_calendar(year=year, month=month, store=store, config=config)
        return {"days": days}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to query calendar for %04d-%02d: %s", year, month, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calendar query error: {exc}",
        ) from exc
