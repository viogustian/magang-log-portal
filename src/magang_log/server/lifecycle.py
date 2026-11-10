"""Process lifecycle management coordinating the FastAPI server and the desktop client."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from .config import ServerConfig
from .runner import ServerRunner

logger = logging.getLogger(__name__)

DEFAULT_EXE_CANDIDATES = [
    Path("desktop/MagangLog.Desktop/bin/Debug/net8.0-windows/MagangLogPortal.exe"),
    Path("desktop/MagangLog.Desktop/bin/Release/net8.0-windows/MagangLogPortal.exe"),
    Path("tools/MagangLogPortal.exe"),
    Path("bin/MagangLogPortal.exe"),
    Path("MagangLogPortal.exe"),
]


def find_desktop_executable(custom_path: str | Path | None = None) -> Path | None:
    """Find the native desktop executable (MagangLogPortal.exe)."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p.resolve()
        return None

    env_path = os.environ.get("MAGANG_LOG_DESKTOP_EXE")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return p.resolve()

    cwd = Path.cwd()
    for candidate in DEFAULT_EXE_CANDIDATES:
        p = (cwd / candidate).resolve()
        if p.is_file():
            return p

    which_result = shutil.which("MagangLogPortal.exe") or shutil.which("MagangLogPortal")
    if which_result:
        return Path(which_result).resolve()

    return None


def launch_server_and_desktop(
    view: str = "dashboard",
    host: str = "127.0.0.1",
    port: int = 8000,
    exe_path: str | Path | None = None,
    server_only: bool = False,
    timeout: float = 5.0,
) -> int:
    """Start local FastAPI server and spawn desktop executable, tearing down cleanly on exit."""
    config = ServerConfig(host=host, port=port)
    runner = ServerRunner(config=config)

    logger.info("Starting local backend server on %s", runner.url)
    runner.start(wait_ready=True, timeout=timeout)

    if server_only:
        print(f"Magang Log Backend Server running at {runner.url} (Press Ctrl+C to stop)")
        try:
            while runner.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal; shutting down server.")
        finally:
            runner.stop()
        return 0

    exe = find_desktop_executable(exe_path)
    if exe is None:
        runner.stop()
        target_name = str(exe_path) if exe_path else "MagangLogPortal.exe"
        raise FileNotFoundError(
            f"Desktop executable '{target_name}' not found. Please ensure the desktop app "
            "is built, provide --exe path, or run with --server-only."
        )

    cmd = [str(exe), f"--view={view}", f"--api-url={runner.url}"]
    logger.info("Launching desktop client: %s", " ".join(cmd))

    proc = subprocess.Popen(cmd)
    try:
        ret = proc.wait()
        return ret
    except KeyboardInterrupt:
        logger.info("Received interrupt signal; stopping desktop client and server.")
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        return 0
    finally:
        runner.stop()

