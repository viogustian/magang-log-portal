"""Programmatic Uvicorn server runner in a background thread with graceful shutdown."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI

from .app import create_app
from .config import ServerConfig

logger = logging.getLogger(__name__)


class ServerRunner:
    """Manages the lifecycle of a local FastAPI server running in a dedicated thread."""

    def __init__(
        self,
        config: ServerConfig | None = None,
        app: FastAPI | None = None,
    ) -> None:
        self.config = config or ServerConfig()
        self.app = app or create_app()

        self._uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        """Base URL for the running server."""
        return f"http://{self.config.host}:{self.config.port}"

    @property
    def is_running(self) -> bool:
        """Check if the server thread is active and running."""
        if self._thread is None or not self._thread.is_alive():
            return False
        if self._server is not None and getattr(self._server, "should_exit", False):
            return False
        return True

    def start(self, wait_ready: bool = True, timeout: float = 5.0) -> None:
        """Start the Uvicorn server in a background thread."""
        if self.is_running:
            return

        self._server = uvicorn.Server(self._uvicorn_config)
        self._thread = threading.Thread(
            target=self._server.run,
            name="magang-log-fastapi-server",
            daemon=True,
        )
        self._thread.start()

        if wait_ready:
            self._wait_until_ready(timeout=timeout)

    def _wait_until_ready(self, timeout: float = 5.0) -> None:
        """Poll the health check endpoint until the server reports status ok."""
        deadline = time.monotonic() + timeout
        health_url = f"{self.url}/api/health"

        while time.monotonic() < deadline:
            if not (self._thread and self._thread.is_alive()):
                raise RuntimeError("Server thread died unexpectedly during startup.")
            try:
                resp = httpx.get(health_url, timeout=0.5)
                if resp.status_code == 200:
                    logger.info("FastAPI server ready at %s", self.url)
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.05)

        self.stop()
        raise TimeoutError(f"FastAPI server failed to start at {self.url} within {timeout}s.")

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully shut down the Uvicorn server and join its thread."""
        if self._server is not None:
            self._server.should_exit = True

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        self._thread = None
        self._server = None
        logger.info("FastAPI server stopped.")

    def __enter__(self) -> ServerRunner:
        self.start(wait_ready=True)
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
