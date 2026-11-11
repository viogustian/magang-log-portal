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
from urllib.parse import urlparse

from pydantic import BaseModel

from ...portal import selectors as sel
from ...portal.session import (
    DEFAULT_LOGIN_MARKERS,
    is_login_redirect,
    save_storage_state,
)
from ...settings import find_repo_root, load_config

logger = logging.getLogger(__name__)

DEFAULT_PORTAL_URL = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat"
DEFAULT_BROWSER_CHANNEL = "chrome"


class PortalAuthStatus(BaseModel):
    """Status details of MagangHub portal authentication session."""

    authenticated: bool
    expires_at: str | None = None
    username: str | None = None
    session_status: str  # "active" | "expired" | "missing" | "invalid"
    login_in_progress: bool = False
    login_stage: str | None = None
    login_message: str | None = None


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


def _resolve_login_defaults() -> tuple[str, str | None]:
    """Read portal base_url and browser channel from config, with safe defaults."""
    try:
        cfg = load_config()
        return (
            cfg.portal.base_url or DEFAULT_PORTAL_URL,
            cfg.portal.channel or DEFAULT_BROWSER_CHANNEL,
        )
    except Exception:  # noqa: BLE001
        return DEFAULT_PORTAL_URL, DEFAULT_BROWSER_CHANNEL


def _extract_username_from_storage(data: dict[str, Any]) -> str | None:
    """Attempt to extract username or email from cookies or localStorage."""
    cookies = data.get("cookies", [])
    for c in cookies:
        name = str(c.get("name", "")).lower()
        if name in ("username", "user_email", "email", "user"):
            val = c.get("value")
            if val:
                return str(val)

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


def _evaluate_auth_file(target_path: Path) -> PortalAuthStatus:
    """Evaluate storage state file health without login progress metadata."""
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
    origins = data.get("origins", [])
    has_local_storage = any(
        bool(origin.get("localStorage"))
        for origin in origins
        if isinstance(origin, dict)
    )
    if not cookies and not has_local_storage:
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

    if expired_count > 0 and len(future_exp) == 0 and not has_local_storage:
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


def get_portal_auth_status(auth_state_path: Path | str | None = None) -> PortalAuthStatus:
    """Inspect portal storage state file and attach live interactive login state."""
    target_path = Path(auth_state_path) if auth_state_path else get_auth_state_path()
    status_obj = _evaluate_auth_file(target_path)
    in_progress, stage, msg = _portal_auth_service.get_login_progress()
    status_obj.login_in_progress = in_progress
    status_obj.login_stage = stage
    status_obj.login_message = msg
    return status_obj


def _select_active_page(context: Any, portal_host: str) -> Any | None:
    """Pick the most relevant open tab (preferring an authenticated portal tab)."""
    pages = [p for p in getattr(context, "pages", []) if not p.is_closed()]
    if not pages:
        return None
    for page in reversed(pages):
        url = page.url or ""
        if url and url != "about:blank" and not is_login_redirect(url, DEFAULT_LOGIN_MARKERS):
            if not portal_host or portal_host in url.lower():
                return page
    return pages[-1]


def _is_history_heading_visible(page: Any) -> bool:
    """Safely check whether the 'Riwayat Kehadiran' heading is visible on the page."""
    try:
        return bool(sel.history_heading(page).is_visible())
    except Exception as exc:  # noqa: BLE001
        logger.debug("Heading selector check not yet ready: %s", exc)
        return False


def _has_browser_auth_data(context: Any, page: Any) -> bool:
    """Return True if browser context currently holds cookies or page localStorage entries."""
    try:
        cookies = context.cookies()
        if isinstance(cookies, list) and len(cookies) > 0:
            return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not inspect context cookies: %s", exc)

    try:
        ls_len = page.evaluate("() => (window.localStorage ? window.localStorage.length : 0)")
        if isinstance(ls_len, int) and ls_len > 0:
            return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not inspect page localStorage: %s", exc)

    return False


def _pump_playwright_wait(page: Any, milliseconds: int = 300) -> None:
    """Wait without starving Playwright greenlets or spinning CPU when mocked."""
    t0 = time.monotonic()
    try:
        page.wait_for_timeout(milliseconds)
    except Exception as exc:  # noqa: BLE001
        logger.debug("wait_for_timeout interrupted: %s", exc)
    elapsed = time.monotonic() - t0
    min_wait = milliseconds / 1000.0 * 0.65
    if elapsed < min_wait:
        time.sleep(min_wait - elapsed)


class PortalAuthService:
    """Service to coordinate portal authentication and manage single-flight login sessions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_active = False
        self._login_stage: str | None = None
        self._login_message: str | None = None
        self._confirm_event = threading.Event()
        self._confirm_done_event = threading.Event()
        self._cancel_event = threading.Event()
        self._confirm_result: tuple[bool, bool, str] = (False, False, "")

    @property
    def is_login_active(self) -> bool:
        """True if an interactive login session is currently active."""
        with self._lock:
            return self._is_active

    def get_login_progress(self) -> tuple[bool, str | None, str | None]:
        """Return (login_in_progress, stage, message) snapshot safely."""
        with self._lock:
            return self._is_active, self._login_stage, self._login_message

    def _set_progress(self, stage: str | None, message: str | None) -> None:
        with self._lock:
            self._login_stage = stage
            self._login_message = message

    @contextlib.contextmanager
    def acquire_login(self) -> Generator[None, None, None]:
        """Guard against multiple concurrent headed login windows."""
        with self._lock:
            if self._is_active:
                raise RuntimeError("A portal login session is already in progress.")
            self._is_active = True
            self._login_stage = "launching"
            self._login_message = "Meluncurkan browser Chrome untuk login portal..."
            self._confirm_event.clear()
            self._confirm_done_event.clear()
            self._cancel_event.clear()
            self._confirm_result = (False, False, "")

        try:
            yield
        finally:
            with self._lock:
                self._is_active = False
                self._login_stage = None
                self._login_message = None
            self._confirm_done_event.set()

    def confirm_interactive_login(self, wait_timeout: float = 15.0) -> tuple[bool, bool, str]:
        """Ask the running login browser session to verify auth & save storage state now."""
        if not self.is_login_active:
            disk_status = _evaluate_auth_file(get_auth_state_path())
            if disk_status.authenticated:
                return True, True, "Sesi autentikasi sudah aktif dan tersimpan."
            return (
                False,
                False,
                "Tidak ada jendela login yang aktif. Klik 'Buka Browser Login' terlebih dahulu.",
            )

        self._confirm_done_event.clear()
        self._confirm_event.set()
        if not self._confirm_done_event.wait(timeout=wait_timeout):
            disk_status = _evaluate_auth_file(get_auth_state_path())
            if disk_status.authenticated:
                return True, True, "Login berhasil, sesi autentikasi tersimpan."
            return (
                False,
                False,
                "Pemeriksaan browser masih berjalan. Pastikan halaman portal selesai dimuat lalu coba klik lagi.",
            )

        return self._confirm_result

    def cancel_interactive_login(self) -> bool:
        """Signal an active interactive login browser session to close cleanly."""
        if not self.is_login_active:
            return False
        self._cancel_event.set()
        self._confirm_event.set()
        return True

    def _try_capture_session(
        self,
        context: Any,
        page: Any,
        target_path: Path,
        base_url: str,
        *,
        navigate_if_needed: bool,
        manual_confirm: bool,
    ) -> tuple[bool, bool, str]:
        """Check current page/context and save session state if authenticated."""
        current_url = page.url or ""
        if (
            not current_url
            or current_url == "about:blank"
            or is_login_redirect(current_url, DEFAULT_LOGIN_MARKERS)
        ):
            if manual_confirm:
                return (
                    False,
                    False,
                    "Browser masih berada di halaman login Kemnaker. Selesaikan login + OTP terlebih dahulu, lalu klik 'Sudah Selesai Login' lagi.",
                )
            return False, False, ""

        if _is_history_heading_visible(page):
            save_storage_state(context, target_path)
            return True, True, "Login berhasil, sesi autentikasi tersimpan."

        if not navigate_if_needed:
            return False, False, ""

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=12000)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Navigation to %s during session verification failed: %s", base_url, exc)

        # Allow Nuxt SPA a short window to either render Riwayat Kehadiran or bounce to SSO
        verify_deadline = time.monotonic() + 3.0
        while time.monotonic() < verify_deadline:
            if page.is_closed():
                return False, False, "Jendela browser ditutup sebelum autentikasi diverifikasi."
            if is_login_redirect(page.url or "", DEFAULT_LOGIN_MARKERS):
                return (
                    False,
                    False,
                    "Sesi portal belum aktif (terdeteksi redirect ke halaman login). Selesaikan login di browser lalu coba lagi.",
                )
            if _is_history_heading_visible(page):
                save_storage_state(context, target_path)
                return True, True, "Login berhasil, sesi autentikasi tersimpan."
            _pump_playwright_wait(page, 250)

        if not is_login_redirect(page.url or "", DEFAULT_LOGIN_MARKERS):
            if manual_confirm and _has_browser_auth_data(context, page):
                save_storage_state(context, target_path)
                return True, True, "Login berhasil, sesi autentikasi tersimpan."
            if manual_confirm:
                return (
                    False,
                    False,
                    "Halaman Riwayat Kehadiran belum tampil atau cookie sesi belum terbaca. Pastikan Anda sudah masuk akun lalu coba lagi.",
                )

        return False, False, ""

    def launch_interactive_login(
        self,
        timeout_seconds: int = 300,
        auth_state_path: Path | None = None,
        base_url: str | None = None,
        channel: str | None = None,
    ) -> tuple[bool, str]:
        """Launch headed Playwright window and poll or accept manual confirmation until saved."""
        target_path = auth_state_path or get_auth_state_path()
        default_url, default_channel = _resolve_login_defaults()
        resolved_url = base_url or default_url
        resolved_channel = channel if channel is not None else default_channel
        portal_host = urlparse(resolved_url).netloc.lower()

        with self.acquire_login():
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=False, channel=resolved_channel)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    page.set_default_timeout(15000)

                    try:
                        page.goto(resolved_url)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Initial navigation error: %s", exc)

                    self._set_progress(
                        "awaiting_user",
                        "Browser Chrome terbuka. Silakan login + OTP di Chrome, lalu klik 'Sudah Selesai Login' (atau tunggu deteksi otomatis).",
                    )

                    start_time = time.monotonic()
                    deadline = start_time + timeout_seconds
                    off_login_since: float | None = None
                    auto_navigated_once = False

                    logger.info(
                        "Awaiting manual login by intern in headed browser (max %ss)...",
                        timeout_seconds,
                    )

                    while time.monotonic() < deadline:
                        if self._cancel_event.is_set():
                            return False, "Proses login dibatalkan."

                        active_page = _select_active_page(context, portal_host)
                        if active_page is None:
                            return False, "Jendela browser ditutup sebelum autentikasi selesai."

                        if self._confirm_event.is_set():
                            self._confirm_event.clear()
                            self._set_progress(
                                "verifying",
                                "Memeriksa status login di browser dan menyimpan sesi...",
                            )
                            should_finish, authenticated, confirm_msg = self._try_capture_session(
                                context,
                                active_page,
                                target_path,
                                resolved_url,
                                navigate_if_needed=True,
                                manual_confirm=True,
                            )
                            self._confirm_result = (authenticated, authenticated, confirm_msg)
                            self._confirm_done_event.set()
                            if should_finish and authenticated:
                                self._set_progress("completed", confirm_msg)
                                return True, confirm_msg
                            self._set_progress("awaiting_user", confirm_msg)
                            continue

                        current_url = active_page.url or ""
                        if (
                            current_url
                            and current_url != "about:blank"
                            and not is_login_redirect(current_url, DEFAULT_LOGIN_MARKERS)
                        ):
                            if off_login_since is None:
                                off_login_since = time.monotonic()

                            if _is_history_heading_visible(active_page):
                                save_storage_state(context, target_path)
                                msg = "Login berhasil, sesi autentikasi tersimpan."
                                self._set_progress("completed", msg)
                                return True, msg

                            if (
                                not auto_navigated_once
                                and (time.monotonic() - off_login_since) >= 1.5
                            ):
                                auto_navigated_once = True
                                self._set_progress(
                                    "verifying",
                                    "Terdeteksi redirect dari halaman login, memverifikasi halaman Riwayat Kehadiran...",
                                )
                                should_finish, authenticated, auto_msg = self._try_capture_session(
                                    context,
                                    active_page,
                                    target_path,
                                    resolved_url,
                                    navigate_if_needed=True,
                                    manual_confirm=False,
                                )
                                if should_finish and authenticated:
                                    self._set_progress("completed", auto_msg)
                                    return True, auto_msg
                                self._set_progress(
                                    "awaiting_user",
                                    auto_msg
                                    or "Silakan selesaikan login di Chrome lalu klik 'Sudah Selesai Login'.",
                                )
                        else:
                            off_login_since = None
                            auto_navigated_once = False

                        _pump_playwright_wait(active_page, 300)

                    return False, f"Batas waktu login ({timeout_seconds} detik) telah habis."
                finally:
                    browser.close()


_portal_auth_service = PortalAuthService()


def get_portal_auth_service() -> PortalAuthService:
    """Return singleton PortalAuthService."""
    return _portal_auth_service
