"""Pengujian integrasi untuk CLI command magang-log review."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from magang_log.cli import main
from magang_log.drafter.models import LogEntryDraft
from magang_log.models import ApprovedEntry, EntryRecord, EvidenceItem, Status
from magang_log.pipeline import ArtifactStore
from magang_log.portal import NotApproved, assert_approved_for_submission
from magang_log.store import LedgerStore


@pytest.fixture
def test_setup(tmp_path: Path):
    db_path = tmp_path / "state.db"
    runs_dir = tmp_path / "runs"
    store = LedgerStore(db_path=db_path)
    store.migrate()
    artifact_store = ArtifactStore(artifacts_dir=runs_dir)

    target_date = date(2026, 10, 27)
    draft = LogEntryDraft(
        work_date=target_date,
        kehadiran="Hadir",
        aktivitas=(
            "Melakukan integrasi terminal review interface dan validasi kontrak ApprovedEntry "
            "dengan pengujian end-to-end pada database SQLite."
        ),
        pembelajaran=(
            "Mendalami pentingnya human-in-the-loop review interface untuk menjamin integritas "
            "konten sebelum pengiriman ke portal."
        ),
        kendala=(
            "Perlu memastikan kompatibilitas stdin dan parsing markdown header saat diedit "
            "menggunakan editor teks eksternal."
        ),
        evidence_refs={"aktivitas": ["git-01"]},
        needs_input=[],
        prompt_version="v1",
        model="gemini-2.5-flash",
    )

    # Simpan draf ke store
    entry_rec = EntryRecord(
        work_date=target_date,
        draft_json=draft.model_dump_json(),
        approved_json=None,
        prompt_version="v1",
        model="gemini-2.5-flash",
        portal_status=Status.PERLU_REVIEW.value,
    )
    store.save_entry(entry_rec)

    # Simpan bukti dan draf ke disk
    artifact_store.save_draft(target_date, draft)
    artifact_store.save_evidence(
        target_date,
        [
            EvidenceItem(
                id="git-01",
                work_date=target_date,
                source="git",
                kind="commit",
                ts=datetime.now(),
                title="feat(review): implement review command",
            )
        ],
    )

    return db_path, runs_dir, target_date, draft


def test_cli_review_approve_as_is(test_setup):
    db_path, runs_dir, target_date, _ = test_setup

    with patch("builtins.input", return_value="Y"):
        exit_code = main(
            [
                "review",
                "--date",
                target_date.isoformat(),
                "--db",
                str(db_path),
                "--artifacts-dir",
                str(runs_dir),
            ]
        )

    assert exit_code == 0

    store = LedgerStore(db_path=db_path)
    rec = store.get_entry(target_date)
    assert rec is not None
    assert rec.approved_at is not None
    assert rec.edit_ratio == 0.0
    assert rec.content_hash is not None

    artifact_store = ArtifactStore(artifacts_dir=runs_dir)
    approved_disk = artifact_store.load_approval(target_date)
    assert approved_disk is not None
    assert approved_disk.approved_at is not None
    assert approved_disk.content_hash == rec.content_hash


def test_cli_review_skip_returns_code_10(test_setup):
    db_path, runs_dir, target_date, _ = test_setup

    with patch("builtins.input", return_value="S"):
        exit_code = main(
            [
                "review",
                "--date",
                target_date.isoformat(),
                "--db",
                str(db_path),
                "--artifacts-dir",
                str(runs_dir),
            ]
        )

    assert exit_code == 10

    store = LedgerStore(db_path=db_path)
    rec = store.get_entry(target_date)
    assert rec is not None
    assert rec.approved_at is None


def test_cli_review_no_draft_returns_code_10(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    store = LedgerStore(db_path=db_path)
    store.migrate()

    exit_code = main(
        [
            "review",
            "--date",
            "2026-10-27",
            "--db",
            str(db_path),
            "--artifacts-dir",
            str(tmp_path / "runs"),
        ]
    )
    assert exit_code == 10


def test_cli_review_editor_flow(test_setup):
    db_path, runs_dir, target_date, _ = test_setup

    def fake_editor_launcher(text: str) -> str:
        return text.replace(
            "validasi kontrak ApprovedEntry",
            "validasi kontrak ApprovedEntry dan penambahan checksum",
        )

    with (
        patch(
            "magang_log.reviewer.session.ReviewSession._default_editor_launcher",
            side_effect=fake_editor_launcher,
        ),
        patch("builtins.input", side_effect=["E", "Y"]),
    ):
        exit_code = main(
            [
                "review",
                "--date",
                target_date.isoformat(),
                "--db",
                str(db_path),
                "--artifacts-dir",
                str(runs_dir),
            ]
        )

    assert exit_code == 0

    store = LedgerStore(db_path=db_path)
    rec = store.get_entry(target_date)
    assert rec is not None
    assert rec.approved_at is not None
    assert rec.edit_ratio > 0.0

    parsed = json.loads(rec.approved_json)
    assert "penambahan checksum" in parsed["aktivitas"]


def test_portal_unapproved_submission_assertion(test_setup):
    _, _, target_date, draft = test_setup

    unapproved = ApprovedEntry(
        work_date=target_date,
        aktivitas=draft.aktivitas,
        pembelajaran=draft.pembelajaran,
        kendala=draft.kendala,
        approved_at=None,
    )

    with pytest.raises(NotApproved, match="approved_at kosong"):
        assert_approved_for_submission(unapproved)
