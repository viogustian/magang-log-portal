"""Portal authentication state checker and background interactive login manager."""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ...portal import selectors as sel
from ...portal.session import (
    DEFAULT_LOGIN_MARKERS,
    is_login_redirect,
    save_storage_state,
)
from ...settings import find_repo_root, load_config

logger = logging.getLogger(__name__)


class PortalAuthStatus(BaseModel):
    """Status details of MagangHub portal authentication session."""

    authenticated: bool
    expires_at: str | None = None
    username: str | None = None
    session_status: str  # "active" | "expired" | "missing" | "invalid"


def get_auth_state_path() -> Path:
    """Resolve configured or default auth storage state path."""
    try:
        cfg = load_config()
        return cfg.portal.auth_state
    except Exception:  # noqa: BLE001
        root = find_repo_root()
        default_state = root / "data" / "auth" / "state.json"
        alt_state = root / "auth" / "storage_state.json"
        return default_state if default_state.exists() else alt_state


def _extract_username_from_storage(data: dict[str, Any]) -> str | None:
    """Attempt to extract username or email from cookies or localStorage."""
    cookies = data.get("cookies", [])
    for c in cookies:
        name = str(c.get("name", "")).lower()
        if name in ("username", "user_email", "email", "user"):
            val = c.get("value")
            if val:
                return str(val)

    # Search localStorage in origins
    origins = data.get("origins", [])
    for origin_obj in origins:
        for item in origin_obj.get("localStorage", []):
            item_name = str(item.get("name", "")).lower()
            if any(k in item_name for k in ("user", "profile", "auth", "email")):
                raw_val = item.get("value", "")
                if "@" in raw_val and not raw_val.startswith("{"):
                    return raw_val
                try:
                    parsed = json.loads(raw_val)
                    if isinstance(parsed, dict):
                        for field in ("email", "username", "name"):
                            if field in parsed and parsed[field]:
                                return str(parsed[field])
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed parsing localStorage user payload: %s", exc)

    return None


def get_portal_auth_status(auth_state_path: Path | str | None = None) -> PortalAuthStatus:
    """Inspect portal storage state file and evaluate session health."""
    target_path = Path(auth_state_path) if auth_state_path else get_auth_state_path()

    if not target_path.exists() or target_path.stat().st_size == 0:
        return PortalAuthStatus(
            authenticated=False,
            expires_at=None,
            username=None,
            session_status="missing",
        )

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Failed to read storage state from %s: %s", target_path, exc)
        return PortalAuthStatus(
            authenticated=False,
            expires_at=None,
            username=None,
            session_status="invalid",
        )

    cookies = data.get("cookies", [])
    if not cookies:
        return PortalAuthStatus(
            authenticated=False,
            expires_at=None,
            username=None,
            session_status="missing",
        )

    now_ts = datetime.now(timezone.utc).timestamp()
    future_exp: list[float] = []
    expired_count = 0

    for c in cookies:
        exp = c.get("expires", -1)
        if exp > 0:
            if exp < now_ts:
                expired_count += 1
            else:
                future_exp.append(exp)

    if expired_count > 0 and len(future_exp) == 0:
        return PortalAuthStatus(
            authenticated=False,
            expires_at=None,
            username=None,
            session_status="expired",
        )

    expires_at = None
    if future_exp:
        expires_at = datetime.fromtimestamp(min(future_exp), timezone.utc).isoformat()

    username = _extract_username_from_storage(data)

    return PortalAuthStatus(
        authenticated=True,
        expires_at=expires_at,
        username=username,
        session_status="active",
    )


class PortalAuthService:
    """Service to coordinate portal authentication and manage single-flight login sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_active = False

    @property
    def is_login_active(self) -> bool:
        """True if an interactive login session is currently active."""
        with self._lock:
            return self._is_active

    @contextlib.contextmanager
    def acquire_login(self) -> Generator[None, None, None]:
        """Guard against multiple concurrent headed login windows."""
        with self._lock:
            if self._is_active:
                raise RuntimeError("A portal login session is already in progress.")
            self._is_active = True

        try:
            yield
        finally:
            with self._lock:
                self._is_active = False

    def launch_interactive_login(
        self,
        timeout_seconds: int = 300,
        auth_state_path: Path | None = None,
        base_url: str = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat",
        channel: str | None = "chrome",
    ) -> tuple[bool, str]:
        """Launch headed Playwright window and poll until manual login completes."""
        target_path = auth_state_path or get_auth_state_path()

        with self.acquire_login():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=False, channel=channel)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    page.set_default_timeout(15000)

                    try:
                        page.goto(base_url)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Initial navigation error: %s", exc)

                    start_time = time.monotonic()
                    deadline = start_time + timeout_seconds

                    logger.info("Awaiting manual login by intern in headed browser (max %ss)...", timeout_seconds)

                    while time.monotonic() < deadline:
                        if page.is_closed():
                            return False, "Jendela browser ditutup sebelum autentikasi selesai."

                        current_url = page.url or ""
                        if not is_login_redirect(current_url, DEFAULT_LOGIN_MARKERS):
                            # Check if history heading is visible
                            try:
                                if sel.history_heading(page).is_visible():
                                    save_storage_state(context, target_path)
                                    return True, "Login berhasil, sesi autentikasi tersimpan."
                            except Exception as exc:  # noqa: BLE001
                                logger.debug("Heading selector check not yet ready: %s", exc)

                        time.sleep(1.0)

                    return False, f"Batas waktu login ({timeout_seconds} detik) telah habis."
                finally:
                    browser.close()


_portal_auth_service = PortalAuthService()


def get_portal_auth_service() -> PortalAuthService:
    """Return singleton PortalAuthService."""
    return _portal_auth_service
