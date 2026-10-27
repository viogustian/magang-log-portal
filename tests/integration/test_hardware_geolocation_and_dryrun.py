"""Pengujian integrasi Penegakan Geolocation Hardware, Pengisian Form, dan Dry-Run (Isu 04-04).

Memverifikasi:
1. Izin geolocation diberikan eksklusif ke origin portal tanpa override koordinat buatan di produksi.
2. Indikator lokasi portal diperiksa: bila izin ditolak, koordinat absen, atau galat, berhenti seketika
   dengan status LOKASI_TIDAK_TERSEDIA (exit code 40) dan screenshot diagnostik tersimpan.
3. Form dibuka dan combobox Kehadiran diverifikasi bernilai "Hadir".
4. Textarea aktivitas, pembelajaran, dan kendala diisi dengan teks ApprovedEntry (100 - 5000 karakter).
5. Nilai yang diisi dibaca-balik dari DOM untuk memastikan tidak terjadi pemotongan (truncation)
   atau korupsi enkripsi/masking.
6. Perintah dry-run (`magang-portal fill` atau `magang-portal submit --dry-run`):
   - Mengisi kolom form sesuai entri.
   - Menahan diri dari mencentang pernyataan persetujuan atau mengeklik tombol Simpan dan Kirim.
   - Mengambil screenshot verifikasi resolusi tinggi ke data/runs/<date>/dryrun.png.
   - Menghasilkan status DRYRUN dan exit code 0.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from magang_log import cli
from magang_log.models import EXIT_CODES, ApprovedEntry, Status
from magang_log.portal import (
    PlaywrightPortal,
    PortalConfig,
    PortalError,
)
from magang_log.portal import (
    selectors as sel,
)

SAMPLE_DATE = date(2026, 10, 27)
TEXT_AKTIVITAS = (
    "Melakukan implementasi fitur penegakan hardware geolocation, populasi formulir logbook, "
    "dan pengujian dry-run dengan inspeksi baca-balik DOM untuk memastikan keutuhan konten."
)
TEXT_PEMBELAJARAN = (
    "Memahami arsitektur integrasi Playwright headless vs windowed dalam membaca koordinat "
    "perangkat keras asli serta proteksi compliance hukum sebelum persetujuan final."
)
TEXT_KENDALA = (
    "Tantangan dalam memverifikasi bahwa textarea Vuetify tidak memotong karakter panjang "
    "atau mengubah format teks beraksen/simbol khusus berhasil diatasi dengan baca-balik deterministik."
)
APPROVED_TIME = datetime(2026, 10, 27, 14, 0, 0)


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


# ── 1. Geolocation Guardrail & Deteksi Ketiadaan Lokasi ────────────────────────


def test_missing_location_halts_with_lokasi_tidak_tersedia_and_takes_screenshot(
    open_portal,
) -> None:
    d = SAMPLE_DATE
    with open_portal(allow_location=False) as portal:
        entry = create_entry(d)
        result = portal.submit(entry, dry_run=True)

        assert result.status is Status.LOKASI_TIDAK_TERSEDIA
        assert EXIT_CODES[result.status] == 40
        assert "lokasi tidak dipalsukan" in result.note

        # Pastikan kolom form tidak sempat diisi apapun
        assert sel.text_field(portal.page, "aktivitas").input_value() == ""
        assert sel.text_field(portal.page, "pembelajaran").input_value() == ""
        assert sel.text_field(portal.page, "kendala").input_value() == ""
        assert sel.declaration(portal.page).is_checked() is False

        # Pastikan screenshot diagnostik 'lokasi-tidak-tersedia' berhasil disimpan
        assert len(result.screenshots) >= 1
        shot_path = result.screenshots[0]
        assert shot_path.exists()
        assert "lokasi-tidak-tersedia" in shot_path.name


def test_cli_fill_when_location_unavailable_returns_exit_code_40(
    mock_base: str, tmp_path: Path
) -> None:
    entry_file = tmp_path / "entry.json"
    entry_file.write_text(
        json.dumps(
            {
                "work_date": SAMPLE_DATE.isoformat(),
                "aktivitas": TEXT_AKTIVITAS,
                "pembelajaran": TEXT_PEMBELAJARAN,
                "kendala": TEXT_KENDALA,
                "approved_at": APPROVED_TIME.isoformat(),
                "kehadiran": "Hadir",
            }
        ),
        encoding="utf-8",
    )

    # Jalankan CLI fill dengan allow_location dinonaktifkan via query mock atau context
    cfg = PortalConfig(
        base_url=mock_base,
        auth_state=tmp_path / "state.json",
        artifacts_dir=tmp_path / "runs",
        headless=True,
        channel=None,
        allow_location=False,
    )

    with PlaywrightPortal(cfg) as portal:
        result = portal.fill(create_entry(SAMPLE_DATE))
        assert result.status is Status.LOKASI_TIDAK_TERSEDIA
        assert EXIT_CODES[result.status] == 40


# ── 2. Verifikasi Combobox Kehadiran & Nilai Awal ─────────────────────────────


def test_attendance_combobox_verified_as_hadir(open_portal) -> None:
    with open_portal() as portal:
        portal.open_history(SAMPLE_DATE)
        portal._open_form(SAMPLE_DATE)

        # Combobox Kehadiran pada portal harus bernilai "Hadir"
        attendance_val = sel.attendance_input(portal.page).input_value().strip()
        assert attendance_val == "Hadir"

        combobox_loc = sel.attendance_combobox(portal.page)
        assert combobox_loc.count() == 1
        assert combobox_loc.input_value().strip() == "Hadir"


def test_submit_rejects_entry_if_kehadiran_is_not_hadir(open_portal) -> None:
    entry = create_entry(kehadiran="Izin")
    assert any("kehadiran harus 'Hadir'" in p for p in entry.problems(100, 5000))
    with open_portal() as portal, pytest.raises(ValueError, match=r"kehadiran harus 'Hadir'"):
        portal.submit(entry)


# ── 3. Populasi Form & Inspeksi Baca-Balik DOM ────────────────────────────────


def test_populate_form_reads_back_and_verifies_exact_match(open_portal) -> None:
    d = SAMPLE_DATE
    with open_portal() as portal:
        portal.open_history(d)
        portal._open_form(d)

        entry = create_entry(d)
        read_back = portal.populate_form(entry)

        assert read_back["aktivitas"] == TEXT_AKTIVITAS
        assert read_back["pembelajaran"] == TEXT_PEMBELAJARAN
        assert read_back["kendala"] == TEXT_KENDALA

        # Verifikasi langsung pada DOM
        for key in ("aktivitas", "pembelajaran", "kendala"):
            dom_val = sel.text_field(portal.page, key).input_value()
            assert dom_val == getattr(entry, key).strip()
            assert len(dom_val) >= 100


def test_populate_form_detects_truncation_or_corruption(open_portal) -> None:
    d = SAMPLE_DATE
    with open_portal() as portal:
        portal.open_history(d)
        portal._open_form(d)

        entry = create_entry(d)

        # Simulasikan mock di mana input_value mengembalikan teks yang terpotong
        mock_field = MagicMock()
        mock_field.input_value.return_value = TEXT_AKTIVITAS[:50]  # terpotong

        original_text_field = sel.text_field
        try:
            sel.text_field = lambda page, key: (
                mock_field if key == "aktivitas" else original_text_field(page, key)
            )
            with pytest.raises(PortalError, match=r"mengalami pemotongan \(truncation\)"):
                portal.populate_form(entry)
        finally:
            sel.text_field = original_text_field


def test_form_limits_enforced_strictly_before_portal_access() -> None:
    # Terlalu pendek (< 100 karakter)
    short_entry = create_entry(aktivitas="x" * 99)
    assert any("minimal 100" in p for p in short_entry.problems(100, 5000))

    # Tepat 100 karakter diterima
    exact_100_entry = create_entry(aktivitas="x" * 100)
    assert exact_100_entry.problems(100, 5000) == []

    # Terlalu panjang (> 5000 karakter)
    long_entry = create_entry(pembelajaran="y" * 5001)
    assert any("maksimal 5000" in p for p in long_entry.problems(100, 5000))


# ── 4. Eksekusi Dry-Run (magang-portal fill / submit --dry-run) ────────────────


def test_dry_run_via_portal_fill_method(open_portal) -> None:
    d = SAMPLE_DATE
    with open_portal() as portal:
        entry = create_entry(d, approved=False)  # Dry-run tidak mewajibkan approved_at
        result = portal.fill(entry)

        assert result.status is Status.DRYRUN
        assert EXIT_CODES[result.status] == 0
        assert "kolom terisi" in result.note
        assert "pernyataan TIDAK dicentang" in result.note

        # Form terisi
        assert sel.text_field(portal.page, "aktivitas").input_value() == TEXT_AKTIVITAS

        # Legal declaration TIDAK dicentang
        assert sel.declaration(portal.page).is_checked() is False

        # Tombol simpan tetap nonaktif
        assert sel.save_button(portal.page).is_disabled()

        # Screenshot tersimpan
        assert len(result.screenshots) == 1
        shot = result.screenshots[0]
        assert shot.exists()
        assert "dryrun.png" in shot.name


def test_cli_fill_and_submit_dry_run_flags(mock_base: str, tmp_path: Path) -> None:
    entry_file = tmp_path / "entry_dryrun.json"
    entry_data = {
        "work_date": SAMPLE_DATE.isoformat(),
        "aktivitas": TEXT_AKTIVITAS,
        "pembelajaran": TEXT_PEMBELAJARAN,
        "kendala": TEXT_KENDALA,
        "approved_at": None,  # belum disetujui manusia, sah untuk dry-run
        "kehadiran": "Hadir",
    }
    entry_file.write_text(json.dumps(entry_data), encoding="utf-8")

    cli_base_url = f"{mock_base}?mock_geo=1"
    # 1. Uji CLI `magang-portal fill --entry ...`
    fill_argv = [
        "fill",
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
    exit_fill = cli.main(fill_argv)
    assert exit_fill == 0

    # 2. Uji CLI `magang-portal submit --entry ... --dry-run`
    submit_dryrun_argv = [
        "submit",
        "--entry",
        str(entry_file),
        "--dry-run",
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
    exit_submit_dry = cli.main(submit_dryrun_argv)
    assert exit_submit_dry == 0
