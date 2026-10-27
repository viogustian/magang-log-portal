"""Kolektor aktivitas commit Git lokal dengan author matching dan pembatasan tanggal ketat."""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from .base import Evidence, SourceConfig

logger = logging.getLogger(__name__)


def _run_git_cmd(repo_path: Path, args: Sequence[str]) -> str | None:
    """Menjalankan perintah git pada repositori tertentu dengan penanganan exception aman."""
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return res.stdout
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning(
            "Eksekusi git gagal di %s dengan argumen %s: [%s] %s",
            repo_path,
            args,
            exc.__class__.__name__,
            exc,
        )
        return None


def _is_git_repo(path: Path) -> bool:
    """Memeriksa apakah path merupakan direktori repositori git yang valid."""
    if not path.is_dir():
        return False
    # Cek cepat keberadaan .git atau gunakan git rev-parse
    git_dir = path / ".git"
    if git_dir.exists():
        return True
    out = _run_git_cmd(path, ["rev-parse", "--is-inside-work-tree"])
    return out is not None and "true" in out.lower()


class GitCollector:
    """Kolektor aktivitas git harian untuk repositori lokal terkonfigurasi."""

    name: str = "git"

    def __init__(
        self,
        repositories: Sequence[Path | str] | None = None,
        author_email: str | None = None,
        include_diff: bool = False,
    ) -> None:
        self.repositories = list(repositories) if repositories is not None else None
        self.author_email = author_email
        self.include_diff = include_diff

    def _resolve_settings(
        self,
        config: SourceConfig = None,
    ) -> tuple[list[Path], str | None, bool]:
        """Mengevaluasi repositori, author_email, dan include_diff dari config atau parameter."""
        repos_raw: list[str | Path] = []
        author_email = self.author_email
        include_diff = self.include_diff

        git_cfg: Any = None
        if config is not None:
            if hasattr(config, "sources") and hasattr(config.sources, "git"):
                git_cfg = config.sources.git
            elif hasattr(config, "get_repositories"):
                git_cfg = config

        if git_cfg is not None:
            if hasattr(git_cfg, "enabled") and not git_cfg.enabled:
                return [], None, False
            if hasattr(git_cfg, "get_repositories"):
                repos_raw = git_cfg.get_repositories()
            elif hasattr(git_cfg, "repos"):
                repos_raw = git_cfg.repos
            if hasattr(git_cfg, "author_email") and git_cfg.author_email:
                author_email = git_cfg.author_email
            if hasattr(git_cfg, "include_diff") and git_cfg.include_diff is not None:
                include_diff = bool(git_cfg.include_diff)
        elif self.repositories is not None:
            repos_raw = self.repositories

        resolved_paths: list[Path] = []
        for r in repos_raw:
            p = Path(r).expanduser()
            resolved_paths.append(p)

        return resolved_paths, author_email, include_diff

    def collect(self, target_date: date, config: SourceConfig = None) -> list[Evidence]:
        """Mengumpulkan commit git yang dibuat pada target_date oleh author yang sesuai."""
        repos, author_email, include_diff = self._resolve_settings(config)
        evidence_items: list[Evidence] = []

        if not repos:
            return []

        # Rentang tanggal lebar untuk git log guna mengantisipasi offset zona waktu lokal
        since_date = target_date - timedelta(days=1)
        until_date = target_date + timedelta(days=1)
        since_str = f"{since_date.isoformat()} 00:00:00"
        until_str = f"{until_date.isoformat()} 23:59:59"

        for repo_path in repos:
            if not _is_git_repo(repo_path):
                logger.warning(
                    "Direktori repositori git tidak valid atau tidak ditemukan: %s, melewati...",
                    repo_path,
                )
                continue

            # Ambil hash commit dalam rentang
            hashes_output = _run_git_cmd(
                repo_path,
                ["log", f"--since={since_str}", f"--until={until_str}", "--format=%H"],
            )
            if not hashes_output:
                continue

            commit_hashes = [h.strip() for h in hashes_output.splitlines() if h.strip()]

            for commit_hash in commit_hashes:
                # Ambil metadata commit: %an (nama), %ae (email), %aI (ISO datetime), %s (subject), %b (body)
                raw_info = _run_git_cmd(
                    repo_path,
                    [
                        "show",
                        "--no-patch",
                        "--format=%an%x00%ae%x00%aI%x00%s%x00%b",
                        commit_hash,
                    ],
                )
                if not raw_info:
                    continue

                parts = raw_info.split("\x00")
                if len(parts) < 4:
                    continue

                author_name = parts[0].strip()
                commit_email = parts[1].strip()
                author_date_iso = parts[2].strip()
                subject = parts[3].strip()
                body = parts[4].strip() if len(parts) > 4 else ""

                # Filter email author bila author_email dikonfigurasi
                if author_email is not None and author_email.strip():
                    if commit_email.lower() != author_email.strip().lower():
                        continue

                # Parse ISO timestamp dan validasi kalender bounds (target_date)
                try:
                    dt = datetime.fromisoformat(author_date_iso)
                except ValueError:
                    continue

                if dt.date() != target_date:
                    continue

                # Konversi timestamp ke UTC
                utc_ts = dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

                # Ambil statistik perubahan berkas (--numstat)
                numstat_out = _run_git_cmd(
                    repo_path,
                    ["show", "--numstat", "--format=", commit_hash],
                )

                file_stats: list[tuple[str, int, int]] = []
                total_add = 0
                total_del = 0

                if numstat_out:
                    for line in numstat_out.splitlines():
                        parts_stat = line.split("\t")
                        if len(parts_stat) >= 3:
                            add_str, del_str, file_path = parts_stat[0], parts_stat[1], parts_stat[2]
                            add_cnt = int(add_str) if add_str.isdigit() else 0
                            del_cnt = int(del_str) if del_str.isdigit() else 0
                            total_add += add_cnt
                            total_del += del_cnt
                            # Normalisasi path relatif menggunakan forward slash
                            normalized_path = file_path.replace(os.sep, "/")
                            file_stats.append((normalized_path, add_cnt, del_cnt))

                # Bangun teks detail terstruktur
                detail_lines = [
                    f"Commit: {commit_hash}",
                    f"Author: {author_name} <{commit_email}>",
                    f"Repo: {repo_path.name}",
                ]

                if body:
                    detail_lines.extend(["", body])

                if file_stats:
                    detail_lines.extend(["", "Files modified:"])
                    for path_str, add_cnt, del_cnt in file_stats:
                        detail_lines.append(f"- {path_str} (+{add_cnt}/-{del_cnt})")

                    detail_lines.extend(
                        [
                            "",
                            f"Summary: {len(file_stats)} files changed, +{total_add} insertions, -{total_del} deletions",
                        ]
                    )

                # Sertakan diff patch bila diminta (default: False)
                if include_diff:
                    diff_out = _run_git_cmd(
                        repo_path,
                        ["show", "--patch", "--format=", commit_hash],
                    )
                    if diff_out:
                        detail_lines.extend(["", "--- Diff ---", diff_out.strip()])

                detail_text = "\n".join(detail_lines)

                ev = Evidence(
                    source="git",
                    kind="commit",
                    ts=utc_ts,
                    title=subject,
                    detail=detail_text,
                    strength="strong",
                    work_date=target_date,
                )
                evidence_items.append(ev)

        return evidence_items
