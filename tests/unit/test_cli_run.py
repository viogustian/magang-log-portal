"""Unit tests untuk perintah CLI `magang-portal run`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from magang_log.cli import main
from magang_log.store import LedgerStore


def test_cli_run_weekend_libur(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "test_run.db"
    # 2026-10-25 adalah hari Minggu
    exit_code = main(["run", "--date", "2026-10-25", "--db", str(db_path)])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["state"] == "LIBUR"
    assert payload["status"] == "LIBUR"
    assert payload["exit_code"] == 0


def test_cli_run_perlu_review_when_non_interactive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test_run.db"
    store = LedgerStore(db_path=db_path)

    # Simpan catatan atau bukti kuat agar lolos tahap collect
    from magang_log.models import EvidenceItem

    store.save_evidence(
        [
            EvidenceItem(
                id="e1",
                work_date=tmp_path.name and __import__("datetime").date(2026, 10, 27),
                source="git",
                kind="commit",
                ts="2026-10-27T10:00:00",
                title="feat: test commit",
                strength="strong",
            )
        ]
    )

    # 2026-10-27 adalah hari Selasa (hari kerja)
    # Tanpa --auto-approve dan non-interaktif, harus berhenti di PERLU_REVIEW dengan exit code 10
    exit_code = main(["run", "--date", "2026-10-27", "--db", str(db_path), "--dry-run"])
    assert exit_code == 10

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["state"] == "PERLU_REVIEW"
    assert payload["status"] == "PERLU_REVIEW"
    assert payload["exit_code"] == 10


def test_cli_run_dry_run_with_auto_approve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "test_run.db"
    store = LedgerStore(db_path=db_path)

    from magang_log.models import EvidenceItem

    target = __import__("datetime").date(2026, 10, 27)
    store.save_evidence(
        [
            EvidenceItem(
                id="e1",
                work_date=target,
                source="git",
                kind="commit",
                ts="2026-10-27T10:00:00",
                title="feat: test commit",
                strength="strong",
            )
        ]
    )

    exit_code = main(
        ["run", "--date", "2026-10-27", "--db", str(db_path), "--dry-run", "--auto-approve"]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["state"] == "DRYRUN"
    assert payload["status"] == "DRYRUN"
    assert payload["exit_code"] == 0
