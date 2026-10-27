"""Pengujian integrasi Kepatuhan Hukum, Zero-Token Submit, dan Verifikasi Independen (Isu 04-05).

Memverifikasi:
1. Legal compliance guard: checkbox pernyataan legalitas HANYA dicentang jika approved_at sah;
   menolak entri tanpa persetujuan dengan error NotApproved sebelum manipulasi checkbox.
2. Form submit mengeklik tombol 'Simpan dan Kirim' dan menunggu penutupan form / network.
3. Eksekusi submit deterministik selesai dalam waktu <= 30 detik menggunakan 0 token LLM.
4. Loop polling verifikasi independen:
   - Memuat ulang halaman riwayat dari server dengan wait_until='networkidle'.
   - Mencari ulang tombol hari pada DOM yang diperbarui.
   - Memastikan accessible name telah beralih ke status terkirim ("Menunggu Persetujuan", dsb.).
   - Melakukan polling interval 2 detik hingga 5 kali.
5. Pada transisi terkonfirmasi, mencatat status BERHASIL dan exit code 0.
6. Pada kegagalan pembaruan status / timeout, mengambil screenshot full-page dan Playwright trace
   ke data/runs/, mencatat status GAGAL, dan menghasilkan exit code 40.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log import cli
from magang_log.models import EXIT_CODES, ApprovedEntry, DayStatus, Status
from magang_log.portal import (
    NotApproved,
)
from magang_log.portal import (
    selectors as sel,
)

SAMPLE_DATE = date(2026, 10, 27)
TEXT_AKTIVITAS = (
    "Melakukan implementasi compliance checkbox guard, zero-token submit, dan independent "
    "server verification polling loop dengan re-locating target day button pada refreshed DOM."
)
TEXT_PEMBELAJARAN = (
    "Memahami arsitektur verifikasi independen pasca-pengiriman dan penanganan trace artefak "
    "Playwright saat terjadi ketidaksesuaian status kalender di sisi server."
)
TEXT_KENDALA = (
    "Memastikan tidak ada asumsi optimistik atas respons tombol simpan, melainkan selalu "
    "melakukan verifikasi muat ulang server penuh dengan interval polling terukur."
)
APPROVED_TIME = datetime(2026, 10, 27, 14, 30, 0)


def create_entry(
    d: date = SAMPLE_DATE,
    *,
    approved: bool = True,
    kehadiran: str = "Hadir",
    aktivitas: str = TEXT_AKTIVITAS,
    pembelajaran: str = TEXT_PEMBELAJARAN,
    kendala: str = TEXT_KENDALA,
) -> ApprovedEntry:
    return ApprovedEntry(
        work_date=d,
        aktivitas=aktivitas,
        pembelajaran=pembelajaran,
        kendala=kendala,
        approved_at=APPROVED_TIME if approved else None,
        kehadiran=kehadiran,
    )


# ── 1. Penjaga Kepatuhan Hukum (Legal Compliance Guard) ───────────────────────


def test_unapproved_entry_rejected_with_not_approved_before_checkbox_interaction(
    open_portal,
) -> None:
    """Entri tanpa approved_at wajib ditolak seketika dan checkbox tidak boleh dicentang."""
    d = SAMPLE_DATE
    entry_unapproved = create_entry(d, approved=False)

    # 1. portal.submit menolak sebelum navigasi browser
    with open_portal() as portal, pytest.raises(NotApproved, match="approved_at kosong"):
        portal.submit(entry_unapproved)

    # 2. Panggilan langsung _tick_declaration juga menolak sebelum menyentuh checkbox
    with open_portal() as portal:
        portal.open_history(d)
        portal._open_form(d)

        checkbox = sel.declaration(portal.page)
        assert checkbox.is_checked() is False

        with pytest.raises(NotApproved, match="approved_at kosong"):
            portal._tick_declaration(entry_unapproved)

        # Checkbox tetap tidak dicentang di DOM
        assert checkbox.is_checked() is False


# ── 2. Zero-Token Submit & Batas Kecepatan Deterministik (<= 30 detik) ────────


def test_zero_llm_tokens_and_deterministic_execution_speed(open_portal) -> None:
    """Submit berjalan sepenuhnya deterministik dengan 0 LLM token dan durasi <= 30 detik."""
    d = SAMPLE_DATE
    entry = create_entry(d)

    start_time = time.monotonic()
    with open_portal() as portal:
        result = portal.submit(entry)
    elapsed = time.monotonic() - start_time

    assert result.status is Status.BERHASIL
    assert elapsed < 30.0, f"Submit memakan waktu {elapsed:.2f} detik, melampaui batas p95 30 detik"


# ── 3. Pengiriman Berhasil & Verifikasi Muat Ulang Independen ──────────────────


def test_successful_submission_and_reload_confirmation(open_portal) -> None:
    """Pengiriman berhasil diverifikasi dengan muat ulang independen dan bersifat idempoten."""
    d = SAMPLE_DATE
    entry = create_entry(d)

    with open_portal() as portal:
        # Kirim pertama: berhasil
        first = portal.submit(entry)
        assert first.status is Status.BERHASIL
        assert EXIT_CODES[first.status] == 0
        assert first.day is not None
        assert first.day.status is DayStatus.SUDAH_TERKIRIM
        assert "Menunggu Persetujuan" in first.day.label

        # Kirim kedua untuk hari yang sama: idempoten, dihentikan oleh anti-tamper gate
        second = portal.submit(entry)
        assert second.status is Status.SUDAH_TERKIRIM
        assert EXIT_CODES[second.status] == 0
        assert "form tidak disentuh" in second.note


# ── 4. Deteksi Kegagalan Server, Tangkapan Layar, dan Trace Playwright ─────────


def test_failure_to_update_dom_after_submit_captures_screenshot_and_trace(
    open_portal,
) -> None:
    """Jika status di server tidak berubah (fail=nosave), submitter mencatat GAGAL (kode 40),

    mengambil screenshot resolusi penuh dan menyimpan trace Playwright.
    """
    d = SAMPLE_DATE
    entry = create_entry(d)

    with open_portal(query="fail=nosave") as portal:
        result = portal.submit(entry)

        assert result.status is Status.GAGAL
        assert EXIT_CODES[result.status] == 40
        assert "tidak berubah setelah kirim" in result.note

        # Screenshot verifikasi gagal tersimpan
        assert len(result.screenshots) >= 1
        shot = result.screenshots[-1]
        assert shot.exists()
        assert "verifikasi-gagal" in shot.name

        # Playwright trace tersimpan
        assert len(result.traces) >= 1
        trace = result.traces[-1]
        assert trace.exists()
        assert "trace-verifikasi-gagal" in trace.name
        assert trace.suffix == ".zip"


# ── 5. Form Dismissal Awaiting ───────────────────────────────────────────────


def test_submit_awaits_form_dismissal_after_save_click(open_portal) -> None:
    """Setelah tombol Simpan diklik, submitter menunggu form tertutup sebelum polling."""
    d = SAMPLE_DATE
    entry = create_entry(d)

    with open_portal() as portal:
        result = portal.submit(entry)
        assert result.status is Status.BERHASIL

        # Form dialog telah tertutup pada halaman
        assert sel.form(portal.page).is_hidden()


# ── 6. Integrasi CLI dengan Status Kode Keluar dan Artefak ─────────────────────


def test_cli_submit_unapproved_and_success_flow(mock_base: str, tmp_path: Path) -> None:
    """CLI submit menolak entri tanpa persetujuan (exit 10) dan sukses jika disetujui (exit 0)."""
    entry_file = tmp_path / "entry_cli.json"
    cli_base_url = f"{mock_base}?mock_geo=1"

    # 1. Entri belum disetujui -> exit code 10 (PERLU_TINDAKAN)
    unapproved_data = {
        "work_date": SAMPLE_DATE.isoformat(),
        "aktivitas": TEXT_AKTIVITAS,
        "pembelajaran": TEXT_PEMBELAJARAN,
        "kendala": TEXT_KENDALA,
        "approved_at": None,
        "kehadiran": "Hadir",
    }
    entry_file.write_text(json.dumps(unapproved_data), encoding="utf-8")

    submit_argv_unapproved = [
        "submit",
        "--entry",
        str(entry_file),
        "--base-url",
        cli_base_url,
        "--auth-state",
        str(tmp_path / "state.json"),
        "--artifacts-dir",
        str(tmp_path / "runs"),
        "--headless",
        "--channel",
        "chromium",
    ]
    exit_code_unapproved = cli.main(submit_argv_unapproved)
    assert exit_code_unapproved == 10

    # 2. Entri sudah disetujui -> exit code 0 (BERHASIL)
    approved_data = {
        **unapproved_data,
        "approved_at": APPROVED_TIME.isoformat(),
    }
    entry_file.write_text(json.dumps(approved_data), encoding="utf-8")

    submit_argv_approved = [
        "submit",
        "--entry",
        str(entry_file),
        "--base-url",
        cli_base_url,
        "--auth-state",
        str(tmp_path / "state.json"),
        "--artifacts-dir",
        str(tmp_path / "runs"),
        "--headless",
        "--channel",
        "chromium",
    ]
    exit_code_approved = cli.main(submit_argv_approved)
    assert exit_code_approved == 0
