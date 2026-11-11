"""Shared root discovery helpers for source checkouts and frozen executables."""

from __future__ import annotations

import sys
from pathlib import Path


def find_app_root(
    start: Path | None = None,
    *,
    markers: tuple[str, ...] = ("pyproject.toml", ".git"),
    frozen_markers: tuple[str, ...] = ("pyproject.toml", "config", "prompts"),
    source_fallback: Path | None = None,
) -> Path:
    """Resolve the repository or installed application root directory.

    When running from a PyInstaller-frozen binary without an explicit ``start``
    path, checks the executable's parent directories first so running from an
    arbitrary working directory (e.g. Task Scheduler or another Git repo) still
    resolves the installed application directory.
    """
    if start is None and getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for parent in [exe_dir, *exe_dir.parents]:
            if any((parent / marker).exists() for marker in frozen_markers):
                return parent

    cur = (start or Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        if any((parent / marker).exists() for marker in markers):
            return parent

    if start is None and source_fallback is not None:
        return source_fallback.resolve()
    return cur

