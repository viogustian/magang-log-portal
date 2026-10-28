"""Paket drafter logbook AI: skema LogEntryDraft, protokol ModelClient, dan EvidenceDrafter."""

from __future__ import annotations

from .client import FakeModelClient, GeminiModelClient, ModelClient
from .engine import EvidenceDrafter
from .models import LogEntryDraft
from .prompts import find_project_root, load_prompt_template
from .stage import DraftingStage, DraftingStageResult, build_feedback_prompt

__all__ = [
    "DraftingStage",
    "DraftingStageResult",
    "EvidenceDrafter",
    "FakeModelClient",
    "GeminiModelClient",
    "LogEntryDraft",
    "ModelClient",
    "build_feedback_prompt",
    "find_project_root",
    "load_prompt_template",
]
