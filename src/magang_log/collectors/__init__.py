"""Paket kolektor aktivitas dan privasi: Evidence, protokol Collector, dan implementasi kolektor."""

from __future__ import annotations

from .app import AppActivityCollector, merge_app_evidence
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
from .recent import RecentItemsScanner, parse_lnk, sanitize_path
from .session_log import (
    ApplicationSessionLogParser,
    SessionLogCollector,
    SessionLogParser,
    parse_log_content,
    resolve_log_files,
    sanitize_log_detail,
)
from .strength import (
    StrengthEvaluationResult,
    build_drafting_payload,
    evaluate_evidence_strength,
    filter_evidence_for_llm,
    is_source_enabled_for_llm,
)

__all__ = [
    "AppActivityCollector",
    "ApplicationSessionLogParser",
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
    "RecentItemsScanner",
    "SessionLogCollector",
    "SessionLogParser",
    "SourceConfig",
    "StrengthEvaluationResult",
    "build_drafting_payload",
    "compute_evidence_id",
    "evaluate_evidence_strength",
    "filter_evidence_for_llm",
    "is_source_enabled_for_llm",
    "is_domain_allowed",
    "merge_app_evidence",
    "parse_lnk",
    "parse_log_content",
    "resolve_log_files",
    "run_collectors",
    "sanitize_evidence",
    "sanitize_log_detail",
    "sanitize_path",
    "sanitize_url",
]
