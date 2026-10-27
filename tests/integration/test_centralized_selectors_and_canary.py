"""Pengujian komprehensif untuk Issue 02:
Centralized Semantic Selectors and Static Canary Diagnostics.

Memverifikasi:
1. Seluruh locator semantik pada `portal/selectors.py` menemukan tepat 1 elemen unik
   pada fixture DOM portal (`riwayat.html`).
2. Fungsi `check_selectors_health` memverifikasi kesehatan seluruh selector.
3. Metode `PlaywrightPortal.check()` menghasilkan laporan canary yang lengkap.
4. CLI command `doctor` (termasuk `doctor --portal`) menampilkan output diagnostik
   yang mudah dibaca dan mengembalikan kode keluar yang tepat.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import MagicMock, patch

from magang_log.cli import cmd_doctor
from magang_log.models import EXIT_CODES, DayStatus, Status
from magang_log.portal import LoginRequired
from magang_log.portal import selectors as sel


def test_all_semantic_selectors_resolve_to_single_unique_element(open_portal) -> None:
    """Memverifikasi seluruh selector semantik portal menyelesaikan tepat satu elemen unik."""
    target_date = date(2026, 10, 27)

    with open_portal() as portal:
        portal.open_history(target_date)
        page = portal.page

        # 1. Judul Halaman Riwayat: h1:has-text("Riwayat Kehadiran")
        heading = sel.history_heading(page)
        assert heading.count() == 1
        assert heading.first.is_visible() is True

        # 2. Tombol Hari: button[role="button"][name*=", <DD> <MonthName> <YYYY>,"]
        day_btn = sel.day_button(page, target_date)
        assert day_btn.count() == 1
        assert day_btn.first.is_visible() is True
        assert "27 Oktober 2026" in day_btn.get_attribute("aria-label")

        # 3. Form Panel: form.daily-form
        form_panel = sel.form(page)
        assert form_panel.count() == 1
        assert form_panel.first.is_visible() is True

        # 4. Judul Form: h2 "Tambah laporan · 27 Oktober 2026"
        form_head = sel.form_heading(page, target_date)
        assert form_head.count() == 1
        assert form_head.first.is_visible() is True

        # 5. Blok Status Izin Lokasi: .location-permission:has-text("Lokasi berhasil diakses")
        loc_status = sel.location_ok(page)
        assert loc_status.count() == 1
        assert loc_status.first.is_visible() is True

        # 6. Kolom Kehadiran: input[role="combobox"]
        attendance = sel.attendance_input(page)
        assert attendance.count() == 1
        assert attendance.input_value() == "Hadir"
        assert sel.attendance_combobox(page).count() == 1

        # 7. Form Textareas: aktivitas, pembelajaran, kendala
        for key in ("aktivitas", "pembelajaran", "kendala"):
            field = sel.text_field(page, key)
            assert field.count() == 1
            assert field.first.is_visible() is True

        # 8. Confirmation Checkbox & Label
        decl_cb = sel.declaration(page)
        assert decl_cb.count() == 1
        assert decl_cb.is_checked() is False

        decl_lbl = sel.declaration_label(page)
        assert decl_lbl.count() == 1
        assert decl_lbl.first.is_visible() is True

        # 9. Tombol Simpan dan Kirim
        submit_btn = sel.save_button(page)
        assert submit_btn.count() == 1
        assert submit_btn.first.is_visible() is True
        assert submit_btn.is_disabled() is True


def test_check_selectors_health_function(open_portal) -> None:
    """Memverifikasi fungsi check_selectors_health memeriksa kesehatan seluruh selector."""
    target_date = date(2026, 10, 27)

    with open_portal() as portal:
        portal.open_history(target_date)
        health = sel.check_selectors_health(portal.page, target_date)

        expected_keys = [
            "page_heading",
            "day_button",
            "form_panel",
            "form_heading",
            "location_status",
            "attendance_field",
            "field_aktivitas",
            "field_pembelajaran",
            "field_kendala",
            "declaration_checkbox",
            "save_button",
        ]

        for key in expected_keys:
            assert key in health, f"Key {key} tidak ada dalam check_selectors_health"
            assert health[key]["healthy"] is True
            assert health[key]["count"] == 1
            assert health[key]["is_unique"] is True


def test_playwright_portal_check_canary_report(open_portal) -> None:
    """Memverifikasi PlaywrightPortal.check menghasilkan laporan canary lengkap."""
    target_date = date(2026, 10, 27)

    with open_portal() as portal:
        report = portal.check(target_date)

        assert report["date"] == "2026-10-27"
        assert report["login"] is True
        assert report["status"] == DayStatus.BELUM_DIISI.value
        assert report["location"] is True
        assert report["all_selectors_healthy"] is True
        assert "selectors_health" in report
        assert len(report["selectors_health"]) == 11


def test_cli_doctor_command_success(tmp_path) -> None:
    """Memverifikasi CLI command `magang-portal doctor` mencetak ringkasan diagnostik."""
    args = argparse.Namespace(
        date="2026-10-27",
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=True,
        portal=True,
        json=False,
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        portal_instance = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = portal_instance
        portal_instance.check.return_value = {
            "date": "2026-10-27",
            "login": True,
            "status": "BELUM_DIISI",
            "label": "Selasa, 27 Oktober 2026, Belum Diisi",
            "location": True,
            "all_selectors_healthy": True,
            "selectors_health": {
                "page_heading": {
                    "description": "Judul Riwayat Kehadiran",
                    "healthy": True,
                    "count": 1,
                },
                "save_button": {"description": "Tombol Simpan", "healthy": True, "count": 1},
            },
        }

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cmd_doctor(args)

        output = buf.getvalue()
        assert exit_code == 0
        assert "CANARY DIAGNOSTIK KESEHATAN PORTAL" in output
        assert "[PASS]" in output
        assert "SEMUA SEHAT & SIAP SUBMIT" in output


def test_cli_doctor_command_json_output(tmp_path) -> None:
    """Memverifikasi flag --json pada cmd_doctor mencetak JSON terstruktur."""
    args = argparse.Namespace(
        date="2026-10-27",
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=True,
        portal=True,
        json=True,
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        portal_instance = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = portal_instance
        portal_instance.check.return_value = {
            "date": "2026-10-27",
            "login": True,
            "status": "BELUM_DIISI",
            "all_selectors_healthy": True,
        }

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cmd_doctor(args)

        output = buf.getvalue()
        assert exit_code == 0
        parsed = json.loads(output)
        assert parsed["login"] is True
        assert parsed["all_selectors_healthy"] is True


def test_cli_doctor_command_on_login_required(tmp_path) -> None:
    """Memverifikasi cmd_doctor mengembalikan exit code 20 saat sesi tidak valid."""
    args = argparse.Namespace(
        date="2026-10-27",
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=True,
        portal=True,
        json=False,
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        portal_instance = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = portal_instance
        portal_instance.check.side_effect = LoginRequired("Sesi kedaluwarsa")

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cmd_doctor(args)

        output = buf.getvalue()
        assert exit_code == EXIT_CODES[Status.LOGIN_DIPERLUKAN]
        assert exit_code == 20
        assert "LOGIN_DIPERLUKAN" in output
        assert "magang-portal login" in output


def test_cli_doctor_command_on_selector_failure(tmp_path) -> None:
    """Memverifikasi cmd_doctor mengembalikan exit code 40 saat ada selector yang hilang/rusak."""
    args = argparse.Namespace(
        date="2026-10-27",
        base_url="https://test.portal",
        auth_state=str(tmp_path / "state.json"),
        artifacts_dir=str(tmp_path / "runs"),
        channel="chromium",
        headless=True,
        portal=True,
        json=False,
    )

    with patch("magang_log.cli.PlaywrightPortal") as mock_portal_cls:
        portal_instance = MagicMock()
        mock_portal_cls.return_value.__enter__.return_value = portal_instance
        portal_instance.check.return_value = {
            "date": "2026-10-27",
            "login": True,
            "status": "BELUM_DIISI",
            "all_selectors_healthy": False,
            "selectors_health": {
                "save_button": {"description": "Tombol Simpan", "healthy": False, "count": 0},
            },
            "error": "Tombol Simpan tidak ditemukan",
        }

        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cmd_doctor(args)

        output = buf.getvalue()
        assert exit_code == EXIT_CODES[Status.GAGAL]
        assert exit_code == 40
        assert "[FAIL]" in output
        assert "PERLU TINDAKAN" in output
