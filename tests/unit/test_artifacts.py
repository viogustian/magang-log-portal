"""Unit tests untuk ArtifactStore: penyimpanan dan pemuatan artifak intermediate."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from magang_log.models import ApprovedEntry, EvidenceItem
from magang_log.pipeline import ArtifactStore, DraftResult, ValidationResult


def test_artifact_store_evidence(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    target = date(2026, 10, 27)

    assert store.load_evidence(target) is None

    items = [
        EvidenceItem(
            id="commit-1",
            work_date=target,
            source="git",
            kind="commit",
            ts="2026-10-27T10:00:00",
            title="feat: implement feature",
            strength="strong",
        )
    ]
    saved_path = store.save_evidence(target, items)
    assert saved_path.exists()

    loaded = store.load_evidence(target)
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].id == "commit-1"
    assert loaded[0].title == "feat: implement feature"


def test_artifact_store_draft_and_validation(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    target = date(2026, 10, 27)

    draft = DraftResult(
        draft_json='{"aktivitas": "Draft aktivitas"}',
        prompt_version="v2.1",
        model="gemini-2.5-flash",
        tokens_in=150,
        tokens_out=250,
    )
    store.save_draft(target, draft)
    loaded_draft = store.load_draft(target)
    assert loaded_draft is not None
    assert loaded_draft.model == "gemini-2.5-flash"
    assert loaded_draft.tokens_in == 150

    val = ValidationResult(is_valid=True, warnings=["teks mendekati batas"])
    store.save_validation(target, val)
    loaded_val = store.load_validation(target)
    assert loaded_val is not None
    assert loaded_val.is_valid is True
    assert loaded_val.warnings == ["teks mendekati batas"]


def test_artifact_store_approval(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    target = date(2026, 10, 27)
    now = datetime(2026, 10, 27, 17, 0, 0)

    entry = ApprovedEntry(
        work_date=target,
        aktivitas="Aktivitas final yang disetujui",
        pembelajaran="Pembelajaran final",
        kendala="Tidak ada",
        approved_at=now,
    )
    store.save_approval(target, entry)

    loaded = store.load_approval(target)
    assert loaded is not None
    assert loaded.aktivitas == "Aktivitas final yang disetujui"
    assert loaded.approved_at == now
