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
from .privacy import (
    DeterministicPrivacyEngine,
    PrivacyConfig,
    PrivacyFilter,
    sanitize_evidence,
)
from .strength import (
    StrengthEvaluationResult,
    build_drafting_payload,
    evaluate_evidence_strength,
    filter_evidence_for_llm,
    is_source_enabled_for_llm,
)

__all__ = [
    "BrowserHistoryCollector",
    "Collector",
    "CollectorFailure",
    "CollectorRunner",
    "DeterministicPrivacyEngine",
    "Evidence",
    "EvidenceSource",
    "EvidenceStrength",
    "GitCollector",
    "NotesCollector",
    "PrivacyConfig",
    "PrivacyFilter",
    "SourceConfig",
    "StrengthEvaluationResult",
    "build_drafting_payload",
    "compute_evidence_id",
    "evaluate_evidence_strength",
    "filter_evidence_for_llm",
    "is_source_enabled_for_llm",
    "is_domain_allowed",
    "run_collectors",
    "sanitize_evidence",
    "sanitize_url",
]
