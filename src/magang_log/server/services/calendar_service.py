"""Service logic for monthly logbook calendar inspection."""

from __future__ import annotations

import calendar
import logging
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from ...gates import INDONESIAN_DAY_NAMES, CalendarGate, GateDecision
from ...settings import AppConfig, load_config
from ...store import LedgerStore

logger = logging.getLogger(__name__)


class CalendarDayInfo(BaseModel):
    """Status description for a single day in the month calendar."""

    date: str
    day_name: str
    status: Literal["BERHASIL", "TERKIRIM", "PENDING", "LIBUR", "KOSONG"]
    entry_id: str | None = None


class MonthCalendarResponse(BaseModel):
    """Response containing list of day statuses for the requested month."""

    days: list[CalendarDayInfo]


def get_month_calendar(
    year: int,
    month: int,
    store: LedgerStore | None = None,
    config: AppConfig | None = None,
) -> list[dict[str, Any]]:
    """Query SQLite ledger store and holiday gates for all days in requested month."""
    st = store or LedgerStore()
    cfg = config or load_config()

    gate = CalendarGate.from_config(cfg)
    _, num_days = calendar.monthrange(year, month)

    results: list[dict[str, Any]] = []

    for day in range(1, num_days + 1):
        d = date(year, month, day)
        day_name = INDONESIAN_DAY_NAMES[d.weekday()]

        gate_res = gate.inspect(d)
        is_libur = gate_res.decision == GateDecision.LIBUR

        entry = st.get_entry(d)
        entry_id = f"entry-{d.isoformat()}" if entry else None

        if entry:
            if entry.verified_at or (
                entry.portal_status and entry.portal_status in ("SUDAH_TERKIRIM", "TERKIRIM")
            ):
                day_status = "TERKIRIM"
            elif entry.submitted_at or (entry.portal_status and entry.portal_status == "BERHASIL"):
                day_status = "BERHASIL"
            elif entry.approved_at or entry.draft_json:
                day_status = "PENDING"
            else:
                day_status = "LIBUR" if is_libur else "KOSONG"
        else:
            if is_libur:
                day_status = "LIBUR"
            else:
                day_status = "KOSONG"

        results.append(
            {
                "date": d.isoformat(),
                "day_name": day_name,
                "status": day_status,
                "entry_id": entry_id,
            }
        )

    return results
