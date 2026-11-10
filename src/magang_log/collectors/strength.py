"""Evaluator kekuatan bukti aktivitas dan penyaringan payload LLM (send_to_llm)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from ..models import EvidenceItem
    from ..settings import AppConfig
    from .base import Evidence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrengthEvaluationResult:
    """Hasil evaluasi kelayakan kualitas bukti aktivitas untuk pemanggilan LLM.

    Fields:
    - passed: True jika memiliki minimal 1 bukti 'strong'
    - total_count: jumlah total bukti
    - strong_count: jumlah bukti 'strong' (komit git, catatan refleksi)
    - weak_count: jumlah bukti 'weak' (riwayat peramban)
    - decision: keputusan gate ("PROCEED" | "PERLU_INPUT")
    - reason: penjelasan manusiawi hasil evaluasi
    - exit_code: 0 jika lolos, 10 jika gagal (PERLU_INPUT)
    """

    passed: bool
    total_count: int
    strong_count: int
    weak_count: int
    decision: str
    reason: str
    exit_code: int = 0


def evaluate_evidence_strength(
    evidence: Sequence[Evidence | EvidenceItem],
) -> StrengthEvaluationResult:
    """Mengevaluasi bukti harian terhadap ambang batas kualitas (minimal satu bukti 'strong')."""
    total = len(evidence)
    strong = sum(1 for e in evidence if getattr(e, "strength", "") == "strong")
    weak = sum(1 for e in evidence if getattr(e, "strength", "") == "weak")

    if strong == 0:
        return StrengthEvaluationResult(
            passed=False,
            total_count=total,
            strong_count=0,
            weak_count=weak,
            decision="PERLU_INPUT",
            reason=(
                "Tidak ada bukti aktivitas berkategori 'strong' (komit git atau catatan manual). "
                "Pipeline dihentikan agar tidak memanggil LLM tanpa bukti yang memadai."
            ),
            exit_code=10,
        )

    return StrengthEvaluationResult(
        passed=True,
        total_count=total,
        strong_count=strong,
        weak_count=weak,
        decision="PROCEED",
        reason=(
            f"Ditemukan {strong} bukti kuat dari total {total} bukti aktivitas. "
            "Kualitas bukti memadai untuk melanjutkan ke tahap penyusunan draf LLM."
        ),
        exit_code=0,
    )


def is_source_enabled_for_llm(source_name: str, config: AppConfig) -> bool:
    """Memeriksa apakah sumber aktivitas diizinkan dikirim ke LLM berdasarkan konfigurasi send_to_llm."""
    sources = config.sources
    norm = source_name.lower().strip()

    if norm == "git":
        val = sources.git.send_to_llm
    elif norm in ("note", "notes"):
        val = getattr(sources.notes, "send_to_llm", True)
    elif norm in ("browser", "browser_history"):
        val = sources.get_browser().send_to_llm
    else:
        val = True

    if isinstance(val, bool):
        return val
    if isinstance(val, (list, tuple, set)):
        return len(val) > 0
    return bool(val)


def filter_evidence_for_llm(
    evidence: Sequence[Evidence | EvidenceItem],
    config: AppConfig,
) -> list[dict[str, Any]]:
    """Menyaring butir bukti aktivitas yang diizinkan untuk dikirimkan ke model bahasa (LLM)."""
    filtered_items: list[dict[str, Any]] = []

    for item in evidence:
        source = getattr(item, "source", "")
        if not is_source_enabled_for_llm(source, config):
            continue

        raw_ts = getattr(item, "ts", None)
        if isinstance(raw_ts, (datetime, date)):
            ts_str = raw_ts.isoformat()
        else:
            ts_str = str(raw_ts or "")

        item_dict = {
            "id": getattr(item, "id", ""),
            "source": getattr(item, "source", ""),
            "kind": getattr(item, "kind", ""),
            "ts": ts_str,
            "title": getattr(item, "title", ""),
            "detail": getattr(item, "detail", ""),
            "strength": getattr(item, "strength", "strong"),
        }
        filtered_items.append(item_dict)

    return filtered_items


def build_drafting_payload(
    target_date: date,
    evidence: Sequence[Evidence | EvidenceItem],
    config: AppConfig,
) -> dict[str, Any]:
    """Menyusun struktur payload final yang siap dikonsumsi oleh AI drafter."""
    filtered = filter_evidence_for_llm(evidence, config)
    all_sources = {getattr(e, "source", "") for e in evidence if getattr(e, "source", "")}
    included_sources = {item["source"] for item in filtered}
    excluded_sources = sorted(list(all_sources - included_sources))

    return {
        "work_date": target_date.isoformat(),
        "evidence": filtered,
        "metadata": {
            "total_collected": len(evidence),
            "included_count": len(filtered),
            "excluded_sources": excluded_sources,
        },
    }
