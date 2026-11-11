"""Unit tests for portal authentication state checker and login guard."""

import json
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from magang_log.server.services.portal_service import (
    PortalAuthService,
    get_portal_auth_status,
)


def _make_mock_playwright(
    *,
    initial_url: str,
    cookies: list[dict[str, Any]] | None = None,
    has_heading: Any = False,
    goto_side_effect: Any = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    page = MagicMock()
    page.url = initial_url
    page.is_closed.return_value = False
    if goto_side_effect is not None:
        page.goto.side_effect = goto_side_effect

    heading = MagicMock()
    if callable(has_heading):
        heading.is_visible.side_effect = has_heading
    else:
        heading.is_visible.return_value = has_heading

    context = MagicMock()
    context.new_page.return_value = page
    context.pages = [page]
    context.cookies.return_value = cookies if cookies is not None else [{"name": "session", "value": "tok"}]

    def fake_storage_state(path: str) -> None:
        saved = {"cookies": context.cookies.return_value, "origins": []}
        Path(path).write_text(json.dumps(saved), encoding="utf-8")

    context.storage_state.side_effect = fake_storage_state

    browser = MagicMock()
    browser.new_context.return_value = context
    pw = MagicMock()
    pw.chromium.launch.return_value = browser
    cm = MagicMock()
    cm.__enter__.return_value = pw
    cm.__exit__.return_value = False
    return cm, heading, page, context


def test_auth_status_missing_file(tmp_path: Path) -> None:
    non_existent = tmp_path / "state.json"
    status = get_portal_auth_status(auth_state_path=non_existent)
    assert status.authenticated is False
    assert status.session_status == "missing"
    assert status.expires_at is None
    assert status.username is None


def test_auth_status_invalid_json(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "state.json"
    corrupt_file.write_text("not-a-valid-json", encoding="utf-8")
    status = get_portal_auth_status(auth_state_path=corrupt_file)
    assert status.authenticated is False
    assert status.session_status == "invalid"


def test_auth_status_expired_cookies(tmp_path: Path) -> None:
    expired_file = tmp_path / "state.json"
    past_timestamp = time.time() - 3600
    data = {
        "cookies": [
            {"name": "session_id", "value": "123", "expires": past_timestamp},
        ],
        "origins": [],
    }
    expired_file.write_text(json.dumps(data), encoding="utf-8")

    status = get_portal_auth_status(auth_state_path=expired_file)
    assert status.authenticated is False
    assert status.session_status == "expired"


def test_auth_status_valid_session(tmp_path: Path) -> None:
    valid_file = tmp_path / "state.json"
    future_timestamp = time.time() + 86400
    data = {
        "cookies": [
            {
                "name": "auth_token",
                "value": "xyz",
                "expires": future_timestamp,
            },
            {
                "name": "username",
                "value": "intern@example.com",
                "expires": future_timestamp,
            },
        ],
        "origins": [],
    }
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    status = get_portal_auth_status(auth_state_path=valid_file)
    assert status.authenticated is True
    assert status.session_status == "active"
    assert status.expires_at is not None
    assert status.username == "intern@example.com"


def test_auth_status_valid_with_local_storage_only(tmp_path: Path) -> None:
    valid_file = tmp_path / "state.json"
    data = {
        "cookies": [],
        "origins": [
            {
                "origin": "https://monev.maganghub.kemnaker.go.id",
                "localStorage": [
                    {"name": "auth_user", "value": '{"email": "intern@kemnaker.go.id"}'},
                ],
            }
        ],
    }
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    status = get_portal_auth_status(auth_state_path=valid_file)
    assert status.authenticated is True
    assert status.session_status == "active"
    assert status.username == "intern@kemnaker.go.id"


def test_concurrent_login_guard() -> None:
    service = PortalAuthService()
    assert service.is_login_active is False

    with service.acquire_login():
        assert service.is_login_active is True
        with pytest.raises(RuntimeError, match="already in progress"):
            with service.acquire_login():
                pass

    assert service.is_login_active is False


def test_launch_interactive_login_navigates_to_riwayat_from_dashboard(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    service = PortalAuthService()
    goto_calls = 0
    navigated_after_login = False

    def fake_goto(url: str, **_kwargs: Any) -> None:
        nonlocal goto_calls, navigated_after_login
        goto_calls += 1
        if goto_calls == 1:
            # Initial navigation redirects to SSO login; user later lands on /dashboard
            page.url = "https://monev.maganghub.kemnaker.go.id/dashboard"
        elif url.endswith("/dashboard/riwayat"):
            navigated_after_login = True
            page.url = url

    cm, heading, page, _ctx = _make_mock_playwright(
        initial_url="about:blank",
        has_heading=lambda: navigated_after_login,
        goto_side_effect=fake_goto,
    )

    with (
        patch("playwright.sync_api.sync_playwright", return_value=cm),
        patch("magang_log.portal.selectors.history_heading", return_value=heading),
    ):
        ok, msg = service.launch_interactive_login(
            timeout_seconds=6,
            auth_state_path=state_file,
            base_url="https://monev.maganghub.kemnaker.go.id/dashboard/riwayat",
            channel="chrome",
        )

    assert ok is True, f"Expected auto-navigation capture to succeed, got: {msg}"
    assert state_file.exists()


def test_launch_interactive_login_manual_confirm_captures_session(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    service = PortalAuthService()

    def fake_goto(url: str, **_kwargs: Any) -> None:
        page.url = url

    cm, heading, page, _ctx = _make_mock_playwright(
        initial_url="https://monev.maganghub.kemnaker.go.id/profil",
        cookies=[{"name": "session", "value": "tok456"}],
        has_heading=False,
        goto_side_effect=fake_goto,
    )

    confirm_outcome: list[tuple[bool, bool, str]] = []

    def trigger_confirm() -> None:
        for _ in range(50):
            if service.is_login_active:
                break
            time.sleep(0.05)
        confirm_outcome.append(service.confirm_interactive_login(wait_timeout=5.0))

    t = threading.Thread(target=trigger_confirm, daemon=True)
    t.start()

    with (
        patch("playwright.sync_api.sync_playwright", return_value=cm),
        patch("magang_log.portal.selectors.history_heading", return_value=heading),
    ):
        ok, _msg = service.launch_interactive_login(
            timeout_seconds=10,
            auth_state_path=state_file,
            base_url="https://monev.maganghub.kemnaker.go.id/dashboard/riwayat",
            channel="chrome",
        )

    t.join(timeout=3.0)
    assert ok is True
    assert state_file.exists()
    assert confirm_outcome and confirm_outcome[0][0] is True
    assert confirm_outcome[0][1] is True


def test_confirm_login_while_on_login_page_does_not_close_browser(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    service = PortalAuthService()

    cm, heading, _page, _ctx = _make_mock_playwright(
        initial_url="https://account.kemnaker.go.id/auth/login",
        cookies=[],
        has_heading=False,
    )

    confirm_outcome: list[tuple[bool, bool, str]] = []

    def trigger_early_confirm_then_cancel() -> None:
        for _ in range(50):
            if service.is_login_active:
                break
            time.sleep(0.05)
        res = service.confirm_interactive_login(wait_timeout=5.0)
        confirm_outcome.append(res)
        assert service.is_login_active is True
        service.cancel_interactive_login()

    t = threading.Thread(target=trigger_early_confirm_then_cancel, daemon=True)
    t.start()

    with (
        patch("playwright.sync_api.sync_playwright", return_value=cm),
        patch("magang_log.portal.selectors.history_heading", return_value=heading),
    ):
        ok, _msg = service.launch_interactive_login(
            timeout_seconds=10,
            auth_state_path=state_file,
            base_url="https://monev.maganghub.kemnaker.go.id/dashboard/riwayat",
            channel="chrome",
        )

    t.join(timeout=3.0)
    assert ok is False
    assert not state_file.exists()
    assert confirm_outcome and confirm_outcome[0][1] is False
    assert "halaman login" in confirm_outcome[0][2].lower()
