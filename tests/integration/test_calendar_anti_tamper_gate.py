"""Pengujian integrasi Anti-Tamper Calendar Inspection Gatekeeper (Isu 04-03).

Memverifikasi:
1. Format tanggal aksesibel bahasa Indonesia (nama hari + tanggal).
2. Penemuan tombol hari menggunakan accessible day name pattern.
3. Ekstraksi atribut aksesibilitas (aria-label, disabled, aria-current) menjadi DayInfo.
4. Mesin keputusan anti-tamper (AntiTamperGate) menghentikan eksekusi pada status non-submittable:
   - "Menunggu Persetujuan", "Hadir disetujui", "Menunggu Tindakan Mentor" -> SUDAH_TERKIRIM (exit code 0)
   - "Jadwal libur posisi", "Hari Libur" -> LIBUR (exit code 0)
   - "Belum Diisi" with disabled=True -> TERKUNCI (exit code 40)
   - "Perlu Tindakan Anda", "Kehadiran Ditolak" -> PERLU_TINDAKAN (exit code 10)
   - Unrecognized label -> TIDAK_DIKENAL (fail-closed, exit code 40)
5. Pada semua status non-submittable, eksekusi berhenti bersih tanpa menyentuh atau membuka form.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from magang_log import cli
from magang_log.models import EXIT_CODES, ApprovedEntry, DayInfo, DayStatus, Status
from magang_log.portal import (
    AntiTamperDecision,
    AntiTamperGate,
    format_day_label_prefix,
    nama_hari_id,
    tanggal_lengkap_id,
)
from magang_log.portal import selectors as sel

TEST_TEXT_120 = (
    "Melakukan implementasi unit test dan integration test untuk modul anti-tamper gatekeeper "
    "guna memastikan kalender portal tidak pernah disentuh pada hari non-submittable secara aman."
)
APPROVED_TIMESTAMP = datetime(2026, 10, 27, 10, 0, 0)


def sample_entry(d: date = date(2026, 10, 27), *, approved: bool = True) -> ApprovedEntry:
    return ApprovedEntry(
        work_date=d,
        aktivitas=TEST_TEXT_120,
        pembelajaran=TEST_TEXT_120,
        kendala=TEST_TEXT_120,
        approved_at=APPROVED_TIMESTAMP if approved else None,
        kehadiran="Hadir",
    )


# ── 1. Format Nama Hari Aksesibel Bahasa Indonesia ────────────────────────────


def test_accessible_day_name_format_and_helpers() -> None:
    # 2026-10-27 adalah Selasa
    d_selasa = date(2026, 10, 27)
    assert nama_hari_id(d_selasa) == "Selasa"
    assert tanggal_lengkap_id(d_selasa) == "Selasa, 27 Oktober 2026"
    assert format_day_label_prefix(d_selasa) == "Selasa, 27 Oktober 2026"

    # Siklus 7 hari (Senin .. Minggu)
    assert nama_hari_id(date(2026, 10, 26)) == "Senin"
    assert nama_hari_id(date(2026, 10, 27)) == "Selasa"
    assert nama_hari_id(date(2026, 10, 28)) == "Rabu"
    assert nama_hari_id(date(2026, 10, 29)) == "Kamis"
    assert nama_hari_id(date(2026, 10, 30)) == "Jumat"
    assert nama_hari_id(date(2026, 10, 31)) == "Sabtu"
    assert nama_hari_id(date(2026, 11, 1)) == "Minggu"


# ── 2. Klasifikasi Status Hari dari Label ─────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "disabled", "expected"),
    [
        ("Selasa, 27 Oktober 2026, Belum Diisi", False, DayStatus.BELUM_DIISI),
        ("Jumat, 23 Oktober 2026, Belum Diisi", True, DayStatus.TERKUNCI),
        ("Rabu, 21 Oktober 2026, Menunggu Persetujuan", False, DayStatus.SUDAH_TERKIRIM),
        ("Rabu, 21 Oktober 2026, Menunggu Persetujuan", True, DayStatus.SUDAH_TERKIRIM),
        ("Senin, 19 Oktober 2026, Hadir disetujui", False, DayStatus.SUDAH_TERKIRIM),
        ("Senin, 19 Oktober 2026, Menunggu Tindakan Mentor", False, DayStatus.SUDAH_TERKIRIM),
        ("Senin, 19 Oktober 2026, Izin disetujui", False, DayStatus.SUDAH_TERKIRIM),
        ("Sabtu, 24 Oktober 2026, Jadwal libur posisi", False, DayStatus.LIBUR),
        ("Minggu, 25 Oktober 2026, Hari Libur", False, DayStatus.LIBUR),
        ("Selasa, 27 Oktober 2026, Perlu Tindakan Anda", False, DayStatus.PERLU_TINDAKAN),
        ("Selasa, 27 Oktober 2026, Kehadiran Ditolak", False, DayStatus.PERLU_TINDAKAN),
        ("Selasa, 27 Oktober 2026, Tidak Hadir", False, DayStatus.PERLU_TINDAKAN),
        ("Selasa, 27 Oktober 2026, Status Tidak Dikenal", False, DayStatus.TIDAK_DIKENAL),
        ("Selasa, 27 Oktober 2026, ", False, DayStatus.TIDAK_DIKENAL),
        ("", False, DayStatus.TIDAK_DIKENAL),
    ],
)
def test_day_status_classification(label: str, disabled: bool, expected: DayStatus) -> None:
    assert sel.classify(label, disabled) is expected


# ── 3. Unit Test Mesin Keputusan AntiTamperGate ───────────────────────────────


@pytest.mark.parametrize(
    ("day_status", "disabled", "expected_submittable", "expected_status", "expected_exit_code"),
    [
        (DayStatus.BELUM_DIISI, False, True, Status.BERHASIL, 0),
        (DayStatus.BELUM_DIISI, True, False, Status.TERKUNCI, 40),
        (DayStatus.SUDAH_TERKIRIM, False, False, Status.SUDAH_TERKIRIM, 0),
        (DayStatus.SUDAH_TERKIRIM, True, False, Status.SUDAH_TERKIRIM, 0),
        (DayStatus.LIBUR, False, False, Status.LIBUR, 0),
        (DayStatus.TERKUNCI, True, False, Status.TERKUNCI, 40),
        (DayStatus.PERLU_TINDAKAN, False, False, Status.PERLU_TINDAKAN, 10),
        (DayStatus.TIDAK_DIKENAL, False, False, Status.TIDAK_DIKENAL, 40),
    ],
)
def test_anti_tamper_gate_inspect_logic(
    day_status: DayStatus,
    disabled: bool,
    expected_submittable: bool,
    expected_status: Status,
    expected_exit_code: int,
) -> None:
    d = date(2026, 10, 27)
    day = DayInfo(
        work_date=d,
        status=day_status,
        label=f"Selasa, 27 Oktober 2026, {day_status.value}",
        disabled=disabled,
        is_today=True,
    )
    decision = AntiTamperGate.inspect(day)
    assert isinstance(decision, AntiTamperDecision)
    assert decision.submittable is expected_submittable
    assert decision.status is expected_status
    assert decision.exit_code == expected_exit_code
    assert EXIT_CODES[decision.status] == expected_exit_code
    assert decision.reason != ""


# ── 4. Integrasi Browser: Ekstraksi DayInfo & inspect_day ─────────────────────


def test_playwright_inspect_day_attributes(open_portal) -> None:
    with open_portal() as portal:
        d = date(2026, 10, 27)
        day, decision = portal.inspect_day(d)
        assert day.work_date == d
        assert day.status is DayStatus.BELUM_DIISI
        assert "Selasa, 27 Oktober 2026, Belum Diisi" in day.label
        assert day.disabled is False
        assert day.is_today is True
        assert decision.submittable is True
        assert decision.exit_code == 0


def test_playwright_inspect_disabled_day(open_portal) -> None:
    with open_portal() as portal:
        d = date(2026, 10, 23)
        day, decision = portal.inspect_day(d)
        assert day.work_date == d
        assert day.status is DayStatus.TERKUNCI
        assert day.disabled is True
        assert decision.submittable is False
        assert decision.status is Status.TERKUNCI
        assert decision.exit_code == 40


# ── 5. Integrasi Browser: Anti-Tamper Menghentikan Eksekusi Tanpa Modifikasi ─


@pytest.mark.parametrize(
    ("override_status", "disable_today", "expected_status", "expected_exit_code"),
    [
        ("Menunggu Persetujuan", False, Status.SUDAH_TERKIRIM, 0),
        ("Hadir disetujui", False, Status.SUDAH_TERKIRIM, 0),
        ("Menunggu Tindakan Mentor", False, Status.SUDAH_TERKIRIM, 0),
        ("Jadwal libur posisi", False, Status.LIBUR, 0),
        ("Hari Libur", False, Status.LIBUR, 0),
        ("Belum Diisi", True, Status.TERKUNCI, 40),
        ("Perlu Tindakan Anda", False, Status.PERLU_TINDAKAN, 10),
        ("Kehadiran Ditolak", False, Status.PERLU_TINDAKAN, 10),
        ("Status Tidak Dikenal", False, Status.TIDAK_DIKENAL, 40),
    ],
)
def test_anti_tamper_halts_immediately_without_form_tampering(
    open_portal,
    override_status: str,
    disable_today: bool,
    expected_status: Status,
    expected_exit_code: int,
) -> None:
    query = f"override_status={override_status}" + ("&disable_today=1" if disable_today else "")
    d = date(2026, 10, 27)
    with open_portal(query=query) as portal:
        entry = sample_entry(d)
        result = portal.submit(entry)

        # 1. Hasil sesuai status yang diharapkan
        assert result.status is expected_status
        assert EXIT_CODES[result.status] == expected_exit_code
        assert "form tidak disentuh" in result.note

        # 2. Form tidak pernah dibuka untuk tanggal ini
        assert not sel.form_heading(portal.page, d).is_visible()
        assert sel.text_field(portal.page, "aktivitas").input_value() == ""


# ── 6. Integrasi CLI: magang-portal submit & fill Mengembalikan Exit Code Sesuai ─


@pytest.mark.parametrize(
    ("override_status", "disable_today", "expected_exit_code"),
    [
        ("Menunggu Persetujuan", False, 0),
        ("Hadir disetujui", False, 0),
        ("Menunggu Tindakan Mentor", False, 0),
        ("Jadwal libur posisi", False, 0),
        ("Hari Libur", False, 0),
        ("Belum Diisi", True, 40),
        ("Perlu Tindakan Anda", False, 10),
        ("Kehadiran Ditolak", False, 10),
        ("Status Tidak Dikenal", False, 40),
    ],
)
def test_cli_submit_and_fill_respect_anti_tamper_exit_codes(
    mock_base: str,
    tmp_path: Path,
    override_status: str,
    disable_today: bool,
    expected_exit_code: int,
) -> None:
    entry_file = tmp_path / "entry.json"
    entry_data = {
        "work_date": "2026-10-27",
        "aktivitas": TEST_TEXT_120,
        "pembelajaran": TEST_TEXT_120,
        "kendala": TEST_TEXT_120,
        "approved_at": APPROVED_TIMESTAMP.isoformat(),
        "kehadiran": "Hadir",
    }
    entry_file.write_text(json.dumps(entry_data), encoding="utf-8")

    query = f"override_status={override_status}" + ("&disable_today=1" if disable_today else "")
    base_url = f"{mock_base}?{query}"

    # Test CLI submit
    submit_argv = [
        "submit",
        "--entry",
        str(entry_file),
        "--base-url",
        base_url,
        "--auth-state",
        str(tmp_path / "state.json"),
        "--artifacts-dir",
        str(tmp_path / "runs"),
        "--headless",
        "--channel",
        "chromium",
    ]
    exit_code = cli.main(submit_argv)
    assert exit_code == expected_exit_code

    # Test CLI fill (dry-run)
    fill_argv = [
        "fill",
        "--entry",
        str(entry_file),
        "--base-url",
        base_url,
        "--auth-state",
        str(tmp_path / "state.json"),
        "--artifacts-dir",
        str(tmp_path / "runs"),
        "--headless",
        "--channel",
        "chromium",
    ]
    exit_code_fill = cli.main(fill_argv)
    assert exit_code_fill == expected_exit_code
