"""Manajemen sesi autentikasi dan penyimpanan state browser (cookies & localStorage).

Prinsip keamanan ketat (PRD bagian 8.7 dan 14):
* Tidak pernah mengetik, meminta, mencegat, atau menyimpan kredensial (kata sandi)
  maupun token OTP/MFA pengguna.
* Sesi dibuat secara interaktif oleh pengguna manusia di jendela browser terlihat
  (headed browser) via perintah CLI `magang-portal login`.
* State autentikasi yang tersimpan di `data/auth/state.json` setara dengan kunci akses:
  wajib dilindungi dengan permission ketat (0o600 pada POSIX) dan di-gitignore.
* Pemantauan sesi otomatis mendeteksi kedaluwarsa atau redirect login, segera
  menghentikan eksekusi dengan status `LOGIN_DIPERLUKAN` (kode keluar 20) serta
  memberikan panduan yang jelas kepada pengguna.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from playwright.sync_api import BrowserContext, Page, sync_playwright

from . import selectors as sel

if TYPE_CHECKING:
    from playwright.sync_api import Playwright

logger = logging.getLogger(__name__)

DEFAULT_LOGIN_MARKERS: tuple[str, ...] = (
    "account.kemnaker.go.id",
    "/login",
    "/auth",
    "/signin",
    "/masuk",
)


class LoginRequired(Exception):
    """Sesi habis atau belum login: pengguna harus menjalankan `magang-portal login`."""

    def __init__(self, message: str = "", *, url: str | None = None) -> None:
        self.url = url
        detail = f" ({url})" if url else ""
        guidance = "Silakan jalankan 'magang-portal login' untuk melakukan autentikasi interaktif."
        full_msg = f"{message}{detail}. {guidance}" if message else guidance
        super().__init__(full_msg.strip())


def save_storage_state(context: BrowserContext, path: Path | str) -> Path:
    """Menyimpan state autentikasi browser (cookies dan localStorage) ke file JSON.

    Args:
        context: Objek browser context Playwright yang terautentikasi.
        path: Path lokasi penyimpanan file state.json.

    Returns:
        Path file state yang berhasil disimpan.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(dest))

    # Terapkan izin akses terbatas (hanya pemilik) pada sistem POSIX
    try:
        os.chmod(dest, 0o600)
    except OSError:
        pass  # Windows mengabaikan chmod POSIX; dilindungi oleh gitignore folder data/

    # Validasi bahwa file tersimpan dan bukan berkas kosong
    if not dest.exists() or dest.stat().st_size == 0:
        raise OSError(f"Gagal menyimpan storage state ke {dest}: file kosong atau tidak terbentuk.")

    return dest


def load_storage_state(path: Path | str) -> dict[str, Any]:
    """Memuat dan memvalidasi file state autentikasi browser.

    Args:
        path: Path lokasi file state.json.

    Returns:
        Dictionary representasi storage state (berisi 'cookies' dan 'origins').

    Raises:
        LoginRequired: Jika file tidak ditemukan, kosong, atau format JSON tidak valid.
    """
    source = Path(path)
    if not source.exists():
        raise LoginRequired(
            f"File sesi tidak ditemukan di '{source}'",
            url=None,
        )

    try:
        content = source.read_text(encoding="utf-8").strip()
        if not content:
            raise LoginRequired(f"File sesi di '{source}' kosong")
        data = json.loads(content)
        if not isinstance(data, dict):
            raise LoginRequired(f"Format file sesi di '{source}' tidak valid (bukan JSON object)")
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LoginRequired(f"File sesi di '{source}' rusak ({exc.__class__.__name__})") from exc


def is_login_redirect(url: str, login_markers: tuple[str, ...] = DEFAULT_LOGIN_MARKERS) -> bool:
    """Memeriksa apakah URL yang diberikan merupakan halaman login atau SSO."""
    normalized = url.lower()
    return any(marker.lower() in normalized for marker in login_markers)


def assert_not_login_redirect(
    page: Page,
    login_markers: tuple[str, ...] = DEFAULT_LOGIN_MARKERS,
) -> None:
    """Memastikan halaman saat ini bukan halaman login/SSO atau redirect unauthenticated.

    Raises:
        LoginRequired: Jika halaman saat ini terdeteksi mengarah ke halaman login.
    """
    current_url = page.url or ""
    if is_login_redirect(current_url, login_markers):
        raise LoginRequired(
            "Diarahkan ke halaman login",
            url=current_url,
        )


class SessionManager:
    """Manajer sesi autentikasi dan persistensi storage state Playwright."""

    def __init__(
        self,
        auth_state: Path | str = Path("data/auth/state.json"),
        base_url: str = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat",
        channel: str | None = "chrome",
        timeout_ms: int = 15_000,
        login_markers: tuple[str, ...] = DEFAULT_LOGIN_MARKERS,
    ) -> None:
        self.auth_state = Path(auth_state)
        self.base_url = base_url
        self.channel = channel
        self.timeout_ms = timeout_ms
        self.login_markers = login_markers

    def save_session(self, context: BrowserContext) -> Path:
        """Menyimpan session storage state dari browser context."""
        return save_storage_state(context, self.auth_state)

    def load_session(self) -> dict[str, Any]:
        """Memuat session storage state dari disk."""
        return load_storage_state(self.auth_state)

    def has_session(self) -> bool:
        """Memeriksa apakah file session storage state ada dan tidak kosong."""
        return self.auth_state.exists() and self.auth_state.stat().st_size > 0

    def check_page(self, page: Page) -> None:
        """Memeriksa apakah halaman saat ini diarahkan ke URL login."""
        assert_not_login_redirect(page, self.login_markers)

    def interactive_login(
        self,
        *,
        input_func: Callable[[], str] = input,
        playwright_instance: Playwright | None = None,
    ) -> bool:
        """Menjalankan proses login interaktif dalam browser berjendela (headed).

        Pengguna menyelesaikan pengisian kredensial dan MFA/OTP secara mandiri.
        Otomasi menunggu konfirmasi dan memverifikasi kemunculan halaman riwayat
        sebelum menyimpan storage state.

        Args:
            input_func: Fungsi untuk menerima input pengguna (default: built-in input).
            playwright_instance: Instance Playwright opsional (mis. untuk mock pengujian).

        Returns:
            True jika sesi berhasil diverifikasi dan disimpan.

        Raises:
            LoginRequired: Jika autentikasi tidak berhasil diselesaikan.
        """

        def _execute(pw: Playwright) -> bool:
            browser = pw.chromium.launch(headless=False, channel=self.channel)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(self.base_url)

                print("=" * 60)
                print("PETUNJUK AUTENTIKASI INTERAKTIF MAGANG-PORTAL:")
                print(
                    "1. Selesaikan login dan OTP/MFA secara mandiri di jendela browser yang terbuka."
                )
                print(
                    "2. Sistem ini TIDAK meminta, mencatat, atau menyimpan password maupun OTP Anda."
                )
                print(
                    "3. Setelah halaman 'Riwayat Kehadiran' tampil sempurna, kembali ke terminal ini."
                )
                print("=" * 60)
                print("Tekan [Enter] di sini setelah Anda selesai login...")
                input_func()

                try:
                    sel.history_heading(page).wait_for(state="visible", timeout=self.timeout_ms)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Verifikasi halaman Riwayat Kehadiran gagal: %s", exc)
                    print(
                        f"Halaman Riwayat Kehadiran belum tampil sempurna ({exc.__class__.__name__}). "
                        "Sesi TIDAK disimpan."
                    )
                    raise LoginRequired(
                        "Halaman Riwayat Kehadiran belum tampil setelah login interaktif",
                        url=page.url,
                    ) from exc

                self.save_session(context)
                print(f"Sesi berhasil disimpan di '{self.auth_state}'.")
                print("File ini setara kunci akun: JANGAN di-commit atau dibagikan.")
                return True
            finally:
                browser.close()

        if playwright_instance is not None:
            return _execute(playwright_instance)

        with sync_playwright() as pw:
            return _execute(pw)
