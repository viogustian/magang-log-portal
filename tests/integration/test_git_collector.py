"""Integration test untuk GitCollector: ekstraksi aktivitas commit Git lokal dengan author matching."""

from __future__ import annotations

import logging
import subprocess
from datetime import date
from pathlib import Path

import pytest

from magang_log.collectors.base import Collector, Evidence
from magang_log.collectors.git import GitCollector
from magang_log.settings import AppConfig, GitSourceSettings, SourcesSettings


def _run_git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Helper untuk menjalankan perintah git di repositori pengujian."""
    res = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    return res.stdout.strip()


@pytest.fixture
def test_git_repo(tmp_path: Path) -> Path:
    """Membuat repositori git sementara dengan beberapa commit dan author berbeda."""
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    _run_git(repo, "init")
    _run_git(repo, "config", "user.name", "Tester Intern")
    _run_git(repo, "config", "user.email", "intern@example.com")
    _run_git(repo, "config", "commit.gpgSign", "false")

    # 1. Commit pada tanggal target (2026-10-27) oleh intern@example.com
    f1 = repo / "src" / "feature.py"
    f1.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("print('hello world')\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    env_target_1 = {
        "GIT_AUTHOR_NAME": "Tester Intern",
        "GIT_AUTHOR_EMAIL": "intern@example.com",
        "GIT_AUTHOR_DATE": "2026-10-27T10:00:00+00:00",
        "GIT_COMMITTER_NAME": "Tester Intern",
        "GIT_COMMITTER_EMAIL": "intern@example.com",
        "GIT_COMMITTER_DATE": "2026-10-27T10:00:00+00:00",
    }
    _run_git(
        repo,
        "commit",
        "-m",
        "feat: initial feature\n\nDetailed context about this commit.",
        env={**dict(subprocess.os.environ), **env_target_1},
    )

    # 2. Commit kedua pada tanggal target (2026-10-27) oleh intern@example.com
    f2 = repo / "tests" / "test_feature.py"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f2.write_text("def test_dummy(): pass\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    env_target_2 = {
        "GIT_AUTHOR_NAME": "Tester Intern",
        "GIT_AUTHOR_EMAIL": "intern@example.com",
        "GIT_AUTHOR_DATE": "2026-10-27T14:30:00+00:00",
        "GIT_COMMITTER_NAME": "Tester Intern",
        "GIT_COMMITTER_EMAIL": "intern@example.com",
        "GIT_COMMITTER_DATE": "2026-10-27T14:30:00+00:00",
    }
    _run_git(
        repo,
        "commit",
        "-m",
        "test: add unit test for feature",
        env={**dict(subprocess.os.environ), **env_target_2},
    )

    # 3. Commit pada tanggal LAIN (2026-10-26) oleh intern@example.com (harus diabaikan)
    f3 = repo / "docs" / "readme.txt"
    f3.parent.mkdir(parents=True, exist_ok=True)
    f3.write_text("Documentation\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    env_yesterday = {
        "GIT_AUTHOR_NAME": "Tester Intern",
        "GIT_AUTHOR_EMAIL": "intern@example.com",
        "GIT_AUTHOR_DATE": "2026-10-26T16:00:00+00:00",
        "GIT_COMMITTER_NAME": "Tester Intern",
        "GIT_COMMITTER_EMAIL": "intern@example.com",
        "GIT_COMMITTER_DATE": "2026-10-26T16:00:00+00:00",
    }
    _run_git(
        repo,
        "commit",
        "-m",
        "docs: update readme yesterday",
        env={**dict(subprocess.os.environ), **env_yesterday},
    )

    # 4. Commit pada tanggal target (2026-10-27) oleh AUTHOR LAIN (other@example.com) (harus diabaikan)
    f4 = repo / "other.txt"
    f4.write_text("other work\n", encoding="utf-8")
    _run_git(repo, "add", ".")
    env_other = {
        "GIT_AUTHOR_NAME": "Other Dev",
        "GIT_AUTHOR_EMAIL": "other@example.com",
        "GIT_AUTHOR_DATE": "2026-10-27T15:00:00+00:00",
        "GIT_COMMITTER_NAME": "Other Dev",
        "GIT_COMMITTER_EMAIL": "other@example.com",
        "GIT_COMMITTER_DATE": "2026-10-27T15:00:00+00:00",
    }
    _run_git(
        repo,
        "commit",
        "-m",
        "chore: teammate work",
        env={**dict(subprocess.os.environ), **env_other},
    )

    return repo


def test_git_collector_protocol_conformance() -> None:
    collector = GitCollector()
    assert isinstance(collector, Collector)


def test_git_collector_extracts_commits_with_author_and_date_filtering(test_git_repo: Path) -> None:
    target_date = date(2026, 10, 27)

    collector = GitCollector(
        repositories=[test_git_repo],
        author_email="intern@example.com",
        include_diff=False,
    )
    evidence_list = collector.collect(target_date)

    # Hanya 2 commit dari intern@example.com pada tanggal 2026-10-27
    assert len(evidence_list) == 2

    for ev in evidence_list:
        assert isinstance(ev, Evidence)
        assert ev.source == "git"
        assert ev.kind == "commit"
        assert ev.strength == "strong"
        assert len(ev.id) == 10
        assert ev.work_date == target_date

    # Urutan kronologis atau reverse-kronologis
    titles = [ev.title for ev in evidence_list]
    assert "feat: initial feature" in titles
    assert "test: add unit test for feature" in titles
    assert "docs: update readme yesterday" not in titles
    assert "chore: teammate work" not in titles

    # Verifikasi payload detail berisi path relatif dan statistik perubahan
    feat_ev = next(ev for ev in evidence_list if ev.title == "feat: initial feature")
    assert "src/feature.py" in feat_ev.detail or "src\\feature.py" in feat_ev.detail
    assert "Detailed context about this commit." in feat_ev.detail
    # Diffs dikecualikan secara default
    assert "diff --git" not in feat_ev.detail


def test_git_collector_include_diff(test_git_repo: Path) -> None:
    target_date = date(2026, 10, 27)

    collector = GitCollector(
        repositories=[test_git_repo],
        author_email="intern@example.com",
        include_diff=True,
    )
    evidence_list = collector.collect(target_date)

    assert len(evidence_list) == 2
    feat_ev = next(ev for ev in evidence_list if ev.title == "feat: initial feature")
    # Diff disertakan bila include_diff = True
    assert "diff --git" in feat_ev.detail
    assert "+print('hello world')" in feat_ev.detail


def test_git_collector_resilience_to_invalid_or_missing_repos(
    test_git_repo: Path,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    target_date = date(2026, 10, 27)
    invalid_path = tmp_path / "does_not_exist_dir"

    collector = GitCollector(
        repositories=[invalid_path, test_git_repo],
        author_email="intern@example.com",
    )

    with caplog.at_level(logging.WARNING):
        evidence_list = collector.collect(target_date)

    # Masih berhasil mengekstrak commit dari repositori valid
    assert len(evidence_list) == 2
    # Peringatan terstruktur dicatat untuk repositori yang tidak valid
    assert "does_not_exist_dir" in caplog.text


def test_git_collector_with_app_config(test_git_repo: Path) -> None:
    target_date = date(2026, 10, 27)
    config = AppConfig(
        sources=SourcesSettings(
            git=GitSourceSettings(
                enabled=True,
                repositories=[str(test_git_repo)],
                author_email="intern@example.com",
                include_diff=False,
            )
        )
    )

    collector = GitCollector()
    evidence_list = collector.collect(target_date, config=config)

    assert len(evidence_list) == 2
