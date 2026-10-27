"""Skema data terstruktur untuk draf logbook harian (LogEntryDraft)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LogEntryDraft(BaseModel):
    """Skema draf entri logbook harian yang dihasilkan oleh AI Drafter."""

    model_config = ConfigDict(extra="ignore")

    work_date: date
    kehadiran: Literal["Hadir"] = "Hadir"
    aktivitas: str
    pembelajaran: str
    kendala: str
    evidence_refs: dict[str, list[str]] = Field(default_factory=dict)
    needs_input: list[str] = Field(default_factory=list)
    prompt_version: str = "v1"
    model: str = "gemini-2.5-flash"
