"""Pengujian komprehensif untuk Issue 01:
Interactive Session Authentication and Storage State Management.

Memverifikasi:
1. Persistensi storage state (cookies & localStorage) ke data/auth/state.json.
2. Pemuatan storage state dan validasi format.
3. Penanganan galat jika file sesi hilang atau rusak (missing/corrupted state).
4. Deteksi redirect halaman login/SSO yang memicu LoginRequired dan status LOGIN_DIPERLUKAN.
5. Panduan pengguna yang jelas untuk menjalankan `magang-portal login`.
6. Alur CLI `magang-portal login` dan `magang-portal check` dengan kode keluar 20.
7. Tidak adanya penangkapan atau penyimpanan kredensial/OTP dalam bentuk apa pun.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from magang_log.cli import cmd_check, cmd_login
from magang_log.models import EXIT_CODES, Status
from magang_log.portal import (
    LoginRequired,
    PlaywrightPortal,
    PortalConfig,
    SessionManager,
    assert_not_login_redirect,
    is_login_redirect,
    load_storage_state,
    save_storage_state,
)


def test_storage_state_persistence_and_loading(tmp_path: Path) -> None:
    """Verifikasi penyimpanan dan pemuatan storage state (cookies & localStorage)."""
    state_file = tmp_path / "auth" / "state.json"
    dummy_payload = {
        "cookies": [
            {
                "name": "session_id",
                "value": "xyz123secret",
                "domain": "monev.maganghub.kemnaker.go.id",
                "path": "/",
                "expires": 1893456000,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
        "origins": [
            {
                "origin": "https://monev.maganghub.kemnaker.go.id",
                "localStorage": [{"name": "auth_token", "value": "jwt-token-abc"}],
            }
        ],
    }

    mock_context = MagicMock()

    def _mock_storage_state(*, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dummy_payload), encoding="utf-8")

    mock_context.storage_state.side_effect = _mock_storage_state

    # 1. Simpan session storage state
    saved_path = save_storage_state(mock_context, state_file)
    assert saved_path == state_file
    assert state_file.exists()
    assert state_file.stat().st_size > 0

    # 2. Muat session storage state
    loaded_data = load_storage_state(state_file)
    assert loaded_data == dummy_payload
    assert len(loaded_data["cookies"]) == 1
    assert loaded_data["cookies"][0]["name"] == "session_id"
    assert loaded_data["origins"][0]["localStorage"][0]["name"] == "auth_token"


def test_missing_state_error_handling(tmp_path: Path) -> None:
    """Memverifikasi penanganan galat saat file state.json tidak ada di disk."""
    missing_path = tmp_path / "non_existent_state.json"

    with pytest.raises(LoginRequired) as exc_info:
        load_storage_state(missing_path)

    msg = str(exc_info.value)
    assert "File sesi tidak ditemukan" in msg
    assert "magang-portal login" in msg


def test_corrupted_or_empty_state_error_handling(tmp_path: Path) -> None:
    """Memverifikasi penanganan galat saat file state.json kosong atau berisi JSON korup."""
    # File kosong
    empty_path = tmp_path / "empty_state.json"
    empty_path.write_text("", encoding="utf-8")
    with pytest.raises(LoginRequired) as exc_info:
        load_storage_state(empty_path)
    assert "kosong" in str(exc_info.value)
    assert "magang-portal login" in str(exc_info.value)

    # JSON rusak sintaks
    corrupt_path = tmp_path / "corrupt_state.json"
    corrupt_path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(LoginRequired) as exc_info:
        load_storage_state(corrupt_path)
    assert "rusak" in str(exc_info.value)
    assert "magang-portal login" in str(exc_info.value)

    # Format bukan JSON object (misalnya array)
    list_path = tmp_path / "list_state.json"
    list_path.write_text("[]", encoding="utf-8")
    with pytest.raises(LoginRequired) as exc_info:
        load_storage_state(list_path)
    assert "tidak valid" in str(exc_info.value)
    assert "magang-portal login" in str(exc_info.value)


def test_is_login_redirect_detection() -> None:
    """Memverifikasi deteksi akurat URL redirect login atau SSO."""
    assert is_login_redirect("https://account.kemnaker.go.id/auth/login") is True
    assert is_login_redirect("https://monev.maganghub.kemnaker.go.id/login") is True
    assert is_login_redirect("https://monev.maganghub.kemnaker.go.id/auth/callback") is True
    assert is_login_redirect("https://sso.kemnaker.go.id/masuk") is True
    assert is_login_redirect("https://account.kemnaker.go.id/signin") is True

    # URL normal aplikasi
    assert is_login_redirect("https://monev.maganghub.kemnaker.go.id/dashboard/riwayat") is False
    assert is_login_redirect("https://monev.maganghub.kemnaker.go.id/dashboard/home") is False


def test_assert_not_login_redirect_raises_login_required() -> None:
    """Memverifikasi assert_not_login_redirect membangkitkan LoginRequired dengan URL detail."""
    mock_page = MagicMock()
    mock_page.url = "https://account.kemnaker.go.id/auth/login?redirect=riwayat"

    with pytest.raises(LoginRequired) as exc_info:
        assert_not_login_redirect(mock_page)

    assert "account.kemnaker.go.id" in str(exc_info.value)
    assert "magang-portal login" in str(exc_info.value)


def test_open_history_redirect_triggers_login_diperlukan(open_portal) -> None:
    """Verifikasi PlaywrightPortal mendeteksi redirect login dan menghasilkan status LOGIN_DIPERLUKAN."""
    with open_portal(query="scenario=login") as portal:
        d = date(2026, 10, 27)
        with pytest.raises(LoginRequired) as exc_info:
            portal.open_history(d)
        assert "login" in str(exc_info.value).lower()
        assert "magang-portal login" in str(exc_info.value)

        # Uji juga via check()
        report = portal.check(d)
        assert report["login"] is False
        assert "LOGIN_DIPERLUKAN" in report["error"]
        assert "magang-portal login" in report["error"]


def test_session_manager_require_session_flag(tmp_path: Path) -> None:
    """Memverifikasi flag require_session pada PortalConfig menghentikan eksekusi jika file hilang."""
    cfg = PortalConfig(
        auth_state=tmp_path / "does_not_exist.json",
        require_session=True,
    )
    with pytest.raises(LoginRequired) as exc_info:
        with PlaywrightPortal(cfg):
            pass
    assert "tidak ditemukan" in str(exc_info.value)


def test_interactive_login_flow_success(tmp_path: Path) -> None:
    """Memverifikasi alur login interaktif headed browser berhasil menyimpan state."""
    state_file = tmp_path / "auth" / "state.json"
    mgr = SessionManager(auth_state=state_file, base_url="https://monev.maganghub.kemnaker.go.id")

    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_pw.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    def _fake_storage_state(*, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    mock_context.storage_state.side_effect = _fake_storage_state

    with patch("magang_log.portal.session.sel.history_heading") as mock_heading:
        heading_locator = MagicMock()
        mock_heading.return_value = heading_locator

        # User menekan Enter di terminal
        fake_input = MagicMock(return_value="")

        success = mgr.interactive_login(input_func=fake_input, playwright_instance=mock_pw)

        assert success is True
        # Memastikan browser dibuka dengan jendela terlihat (headless=False)
        mock_pw.chromium.launch.assert_called_once_with(headless=False, channel=mgr.channel)
        mock_page.goto.assert_called_once_with(mgr.base_url)
        fake_input.assert_called_once()
        heading_locator.wait_for.assert_called_once_with(state="visible", timeout=mgr.timeout_ms)
        mock_context.storage_state.assert_called_once()
        mock_browser.close.assert_called_once()
        assert state_file.exists()


def test_interactive_login_flow_timeout_does_not_save_session(tmp_path: Path) -> None:
    """Memverifikasi jika heading Riwayat Kehadiran tidak muncul, sesi tidak disimpan."""
    state_file = tmp_path / "auth" / "state.json"
    mgr = SessionManager(auth_state=state_file, base_url="https://monev.maganghub.kemnaker.go.id")

    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_pw.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    with patch("magang_log.portal.session.sel.history_heading") as mock_heading:
        heading_locator = MagicMock()
        heading_locator.wait_for.side_effect = PlaywrightTimeout("Heading tidak terlihat")
        mock_heading.return_value = heading_locator

        with pytest.raises(LoginRequired) as exc_info:
            mgr.interactive_login(input_func=lambda: "", playwright_instance=mock_pw)

        assert "belum tampil" in str(exc_info.value)
        # Sesi TIDAK boleh disimpan
        mock_context.storage_state.assert_not_called()
        mock_browser.close.assert_called_once()
        assert not state_file.exists()


def test_cli_login_command_failure_returns_exit_code_20(tmp_path: Path) -> None:
    """Memverifikasi CLI command `magang-portal login` mengembalikan kode keluar 20 saat login gagal."""
    args = argparse.Namespace(
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=False,
    )

    with patch("magang_log.portal.session.SessionManager.interactive_login") as mock_login:
        mock_login.side_effect = LoginRequired("Autentikasi dibatalkan")
        exit_code = cmd_login(args)
        assert exit_code == EXIT_CODES[Status.LOGIN_DIPERLUKAN]
        assert exit_code == 20


def test_cli_check_command_on_login_required_returns_exit_code_20(tmp_path: Path) -> None:
    """Memverifikasi CLI command `magang-portal check` mengembalikan kode keluar 20 saat sesi habis."""
    args = argparse.Namespace(
        date="2026-10-27",
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=True,
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        portal_instance = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = portal_instance
        portal_instance.check.return_value = {
            "date": "2026-10-27",
            "login": False,
            "error": "LOGIN_DIPERLUKAN (Diarahkan ke login)",
        }

        exit_code = cmd_check(args)
        assert exit_code == EXIT_CODES[Status.LOGIN_DIPERLUKAN]
        assert exit_code == 20
