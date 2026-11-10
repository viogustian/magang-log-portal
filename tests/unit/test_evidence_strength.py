"""Unit tests untuk evaluator kekuatan bukti aktivitas dan penyaringan payload LLM."""

from __future__ import annotations

from datetime import datetime, timezone

from magang_log.collectors.base import Evidence
from magang_log.collectors.strength import (
    build_drafting_payload,
    evaluate_evidence_strength,
    is_source_enabled_for_llm,
)
from magang_log.settings import AppConfig


def _make_evidence(
    source: str = "git",
    kind: str = "commit",
    strength: str = "strong",
    title: str = "Commit test",
) -> Evidence:
    return Evidence(
        source=source,  # type: ignore[arg-type]
        kind=kind,
        ts=datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc),
        title=title,
        strength=strength,  # type: ignore[arg-type]
    )


def test_strength_evaluator_empty_collection() -> None:
    """Koleksi bukti kosong harus gagal evaluasi dengan PERLU_INPUT dan exit code 10."""
    result = evaluate_evidence_strength([])
    assert result.passed is False
    assert result.total_count == 0
    assert result.strong_count == 0
    assert result.weak_count == 0
    assert result.decision == "PERLU_INPUT"
    assert result.exit_code == 10
    assert "Tidak ada bukti" in result.reason


def test_strength_evaluator_weak_only_collection() -> None:
    """Koleksi berisi hanya bukti lemah (browser) harus gagal dengan PERLU_INPUT dan exit code 10."""
    raw = [
        _make_evidence(source="browser", kind="visit", strength="weak", title="Read docs"),
        _make_evidence(source="browser", kind="visit", strength="weak", title="GitHub explore"),
    ]
    result = evaluate_evidence_strength(raw)
    assert result.passed is False
    assert result.total_count == 2
    assert result.strong_count == 0
    assert result.weak_count == 2
    assert result.decision == "PERLU_INPUT"
    assert result.exit_code == 10


def test_strength_evaluator_with_strong_evidence() -> None:
    """Koleksi berisi setidaknya 1 bukti kuat (commit atau note) harus lolos dengan PROCEED."""
    raw = [
        _make_evidence(source="git", kind="commit", strength="strong", title="feat: login portal"),
        _make_evidence(source="browser", kind="visit", strength="weak", title="Read API docs"),
    ]
    result = evaluate_evidence_strength(raw)
    assert result.passed is True
    assert result.total_count == 2
    assert result.strong_count == 1
    assert result.weak_count == 1
    assert result.decision == "PROCEED"
    assert result.exit_code == 0


def test_send_to_llm_toggle_evaluation() -> None:
    """Memeriksa apakah toggle send_to_llm diidentifikasi dengan benar untuk boolean dan list."""
    cfg = AppConfig()
    # Default: git dan notes aktif, browser default send_to_llm list
    assert is_source_enabled_for_llm("git", cfg) is True
    assert is_source_enabled_for_llm("note", cfg) is True

    # Jika browser send_to_llm dimatikan (False)
    cfg.sources.browser.send_to_llm = False  # type: ignore[assignment]
    assert is_source_enabled_for_llm("browser", cfg) is False


def test_build_drafting_payload_excludes_disabled_sources() -> None:
    """Drafting payload mengecualikan output sumber yang toggle send_to_llm nya false."""
    cfg = AppConfig()
    cfg.sources.browser.send_to_llm = False  # type: ignore[assignment]

    items = [
        _make_evidence(source="git", kind="commit", title="feat: git item"),
        _make_evidence(source="note", kind="note:aktivitas", title="note item"),
        _make_evidence(source="browser", kind="visit", strength="weak", title="browser item"),
    ]

    from datetime import date

    payload = build_drafting_payload(date(2026, 10, 27), items, cfg)

    assert payload["work_date"] == "2026-10-27"
    payload_titles = [e["title"] for e in payload["evidence"]]
    assert "feat: git item" in payload_titles
    assert "note item" in payload_titles
    assert "browser item" not in payload_titles

    assert payload["metadata"]["total_collected"] == 3
    assert payload["metadata"]["included_count"] == 2
    assert "browser" in payload["metadata"]["excluded_sources"]
