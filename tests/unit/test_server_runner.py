"""Tests for ServerRunner lifecycle and programmatic Uvicorn control."""

import httpx

from magang_log.server.config import ServerConfig
from magang_log.server.runner import ServerRunner


def test_server_runner_lifecycle() -> None:
    # Use a non-standard port for testing to avoid collisions
    config = ServerConfig(host="127.0.0.1", port=8943, log_level="warning")
    runner = ServerRunner(config=config)

    assert not runner.is_running

    runner.start(wait_ready=True, timeout=5.0)
    try:
        assert runner.is_running
        assert runner.url == "http://127.0.0.1:8943"

        # Verify server actually serves HTTP requests
        resp = httpx.get(f"{runner.url}/api/health", timeout=2.0)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
    finally:
        runner.stop(timeout=3.0)

    assert not runner.is_running


def test_server_runner_context_manager() -> None:
    config = ServerConfig(host="127.0.0.1", port=8944, log_level="warning")
    with ServerRunner(config=config) as runner:
        assert runner.is_running
        resp = httpx.get(f"{runner.url}/api/health", timeout=2.0)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    assert not runner.is_running
