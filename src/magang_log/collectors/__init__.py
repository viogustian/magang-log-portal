"""Paket kolektor aktivitas dan privasi: Evidence, protokol Collector, dan implementasi kolektor."""

from __future__ import annotations

from .base import (
    Collector,
    CollectorFailure,
    CollectorRunner,
    Evidence,
    EvidenceSource,
    EvidenceStrength,
    SourceConfig,
    compute_evidence_id,
    run_collectors,
)
from .browser import BrowserHistoryCollector, is_domain_allowed, sanitize_url
from .git import GitCollector
from .notes import NotesCollector

__all__ = [
    "BrowserHistoryCollector",
    "Collector",
    "CollectorFailure",
    "CollectorRunner",
    "Evidence",
    "EvidenceSource",
    "EvidenceStrength",
    "GitCollector",
    "NotesCollector",
    "SourceConfig",
    "compute_evidence_id",
    "is_domain_allowed",
    "run_collectors",
    "sanitize_url",
]
