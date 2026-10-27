from __future__ import annotations

import http.server
import threading
import urllib.parse
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from magang_log.portal import PlaywrightPortal, PortalConfig

FIXTURES = Path(__file__).parent / "fixtures" / "portal_mock"

# Koordinat PALSU khusus untuk halaman tiruan (0,0 = "Null Island"). Hanya dipakai di test;
# kode produksi tidak pernah mengisi koordinat.
TEST_ONLY_FAKE_COORDS = {"latitude": 0.0, "longitude": 0.0}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - nama method ditentukan http.server
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path == "/dashboard/riwayat":
            if query.get("scenario") == ["login"]:
                self.send_response(302)
                self.send_header("Location", "/auth/login")
                self.end_headers()
                return
            self._send(200, (FIXTURES / "riwayat.html").read_bytes())
        elif url.path == "/auth/login":
            self._send(
                200, "<html><body><h1>Masuk</h1><p>Silakan login.</p></body></html>".encode()
            )
        else:
            self._send(404, b"not found")

    def _send(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # diamkan log server uji
        return


@pytest.fixture(scope="session")
def mock_base() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/dashboard/riwayat"
    server.shutdown()


@pytest.fixture
def open_portal(mock_base: str, tmp_path: Path) -> Callable[..., object]:
    """Pabrik context manager: `with open_portal(query="fail=nosave") as portal:`."""

    @contextmanager
    def _open(*, query: str = "", geo: bool = True, **overrides) -> Iterator[PlaywrightPortal]:
        cfg = PortalConfig(
            base_url=mock_base + (f"?{query}" if query else ""),
            auth_state=tmp_path / "state.json",  # tidak ada => sesi kosong
            artifacts_dir=tmp_path / "runs",
            headless=True,
            channel=None,  # Chromium bawaan Playwright
            timeout_ms=5_000,
            location_timeout_ms=3_000,
        )
        for key, value in overrides.items():
            setattr(cfg, key, value)
        with PlaywrightPortal(cfg) as portal:
            if geo and cfg.allow_location:
                portal._ctx.set_geolocation(TEST_ONLY_FAKE_COORDS)  # hanya untuk halaman tiruan
            yield portal

    return _open
