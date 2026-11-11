"""Standalone executable entrypoint for PyInstaller backend builds."""

from __future__ import annotations

import multiprocessing
import sys


def run() -> int:
    """Initialize freeze support and invoke the main CLI entrypoint."""
    multiprocessing.freeze_support()
    from magang_log.cli import main

    return main()


if __name__ == "__main__":
    sys.exit(run())

