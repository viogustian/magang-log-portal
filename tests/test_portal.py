"""Test adapter portal terhadap halaman tiruan yang markup-nya berasal dari snapshot asli."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from magang_log.models import ApprovedEntry, DayStatus, Status
from magang_log.portal import NotApproved
from magang_log.portal import selectors as sel

AKTIVITAS = (
    "Menulis unit test untuk modul validasi dan memperbaiki dua bug pada endpoint laporan "
    "berdasarkan hasil review mentor, lalu menggabungkan perubahan ke branch fitur."
)
PEMBELAJARAN = (
    "Memahami perbedaan unit test dan integration test serta cara memakai fixture agar data "
    "uji tetap terisolasi antar skenario pengujian."
)
KENDALA = (
    "Satu test gagal intermiten karena bergantung pada urutan eksekusi; diselesaikan dengan "
    "membuat data uji terpisah untuk setiap test."
)
APPROVED = datetime(2026, 10, 27, 16, 40)


def entry(d: date = date(2026, 10, 27), *, approved: bool = True, **kw) -> ApprovedEntry:
    fields = {"aktivitas": AKTIVITAS, "pembelajaran": PEMBELAJARAN, "kendala": KENDALA, **kw}
    return ApprovedEntry(d, approved_at=APPROVED if approved else None, **fields)


# ── Teks contoh memenuhi batas form ─────────────────────────────────────────


def test_sample_texts_meet_portal_limits() -> None:
    assert entry().problems(100, 5000) == []


# ── Membaca status hari dari kalender (markup asli) ─────────────────────────


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (27, DayStatus.BELUM_DIISI),  # hari ini, aktif
        (26, DayStatus.SUDAH_TERKIRIM),  # "Menunggu Persetujuan"
        (22, DayStatus.SUDAH_TERKIRIM),
        (24, DayStatus.LIBUR),  # "Jadwal libur posisi" (Sabtu)
        (25, DayStatus.LIBUR),
        (23, DayStatus.TERKUNCI),  # "Belum Diisi" tapi tombol nonaktif (sudah lewat)
        (28, DayStatus.TERKUNCI),  # masa depan, nonaktif
    ],
)
def test_read_day_status(open_portal, day: int, expected: DayStatus) -> None:
    d = date(2026, 10, day)
    with open_portal() as portal:
        portal.open_history(d)
        assert portal.read_day(d).status is expected


def test_today_is_marked(open_portal) -> None:
    with open_portal() as portal:
        portal.open_history(date(2026, 10, 27))
        assert portal.read_day(date(2026, 10, 27)).is_today is True
        assert portal.read_day(date(2026, 10, 26)).is_today is False


def test_unknown_status_label_is_fail_closed() -> None:
    assert sel.classify("Selasa, 27 Oktober 2026, Status Baru", False) is DayStatus.TIDAK_DIKENAL


def test_day_pattern_does_not_confuse_2_with_12_november(open_portal) -> None:
    with open_portal() as portal:
        portal.open_history(date(2026, 11, 2))
        info = portal.read_day(date(2026, 11, 2))
        assert "2 November 2026" in info.label and "12 November" not in info.label


# ── Selector harus unik pada markup asli ────────────────────────────────────


def test_every_form_selector_resolves_to_exactly_one_element(open_portal) -> None:
    with open_portal() as portal:
        portal.open_history(date(2026, 10, 27))
        page = portal.page
        assert sel.form_heading(page, date(2026, 10, 27)).count() == 1
        assert sel.attendance_input(page).count() == 1
        for key in sel.FIELD_LABELS:
            assert sel.text_field(page, key).count() == 1, key
        assert sel.declaration(page).count() == 1
        assert sel.save_button(page).count() == 1


def test_attendance_default_is_hadir(open_portal) -> None:
    with open_portal() as portal:
        portal.open_history(date(2026, 10, 27))
        assert sel.attendance_input(portal.page).input_value() == "Hadir"


# ── Dry-run ─────────────────────────────────────────────────────────────────


def test_dry_run_fills_but_does_not_declare_or_send(open_portal) -> None:
    d = date(2026, 10, 27)
    with open_portal() as portal:
        result = portal.submit(entry(approved=False), dry_run=True)
        assert result.status is Status.DRYRUN
        assert sel.text_field(portal.page, "aktivitas").input_value() == AKTIVITAS
        assert sel.declaration(portal.page).is_checked() is False
        assert sel.save_button(portal.page).is_disabled()
        assert portal.read_day(d).status is DayStatus.BELUM_DIISI  # tidak ada yang tersimpan
        assert result.screenshots and result.screenshots[0].exists()


# ── Kirim sungguhan + verifikasi ────────────────────────────────────────────


def test_submit_success_is_verified_by_reload_and_second_run_is_idempotent(open_portal) -> None:
    with open_portal() as portal:
        first = portal.submit(entry())
        assert first.status is Status.BERHASIL, first.note
        assert first.day is not None and "Menunggu Persetujuan" in first.day.label
        second = portal.submit(entry())
        assert second.status is Status.SUDAH_TERKIRIM  # tidak mengirim dua kali


def test_false_success_is_caught_by_independent_verification(open_portal) -> None:
    with open_portal(query="fail=nosave") as portal:
        result = portal.submit(entry())
        assert result.status is Status.GAGAL
        assert "tidak berubah" in result.note
        assert result.screenshots  # bukti diagnosis tersimpan


def test_form_opens_by_clicking_the_day_when_not_preopened(open_portal) -> None:
    with open_portal(query="preopen=0") as portal:
        assert portal.submit(entry()).status is Status.BERHASIL


# ── Penjaga: tidak menyentuh form pada hari yang tidak boleh ────────────────


@pytest.mark.parametrize(
    ("day", "expected"),
    [(26, Status.SUDAH_TERKIRIM), (24, Status.LIBUR), (23, Status.TERKUNCI)],
)
def test_untouchable_days_stop_before_the_form(open_portal, day: int, expected: Status) -> None:
    with open_portal() as portal:
        result = portal.submit(entry(date(2026, 10, day)))
        assert result.status is expected
        assert sel.text_field(portal.page, "aktivitas").input_value() == ""  # form tak disentuh


# ── Persetujuan manusia dan aturan form ─────────────────────────────────────


def test_submit_requires_approval_and_never_opens_the_browser_page(open_portal) -> None:
    with open_portal() as portal, pytest.raises(NotApproved):
        portal.submit(entry(approved=False))
    # (halaman tidak sempat dinavigasi: pengecekan terjadi sebelum open_history)


def test_too_short_text_is_rejected_before_any_browser_action(open_portal) -> None:
    with open_portal() as portal, pytest.raises(ValueError, match=r"aktivitas: 99 karakter"):
        portal.submit(entry(aktivitas="x" * 99))
        pytest.fail("seharusnya ditolak sebelum menyentuh portal")


def test_exactly_100_characters_is_accepted_by_validation() -> None:
    assert entry(aktivitas="x" * 100).problems(100, 5000) == []


def test_over_5000_characters_is_rejected() -> None:
    assert any("maksimal 5000" in p for p in entry(kendala="x" * 5001).problems(100, 5000))


# ── Login dan lokasi ────────────────────────────────────────────────────────


def test_login_redirect_is_reported_not_attempted(open_portal) -> None:
    with open_portal(query="scenario=login") as portal:
        result = portal.submit(entry())
        assert result.status is Status.LOGIN_DIPERLUKAN


def test_missing_location_stops_without_typing_anything_and_never_fakes_it(open_portal) -> None:
    with open_portal(allow_location=False) as portal:
        result = portal.submit(entry())
        assert result.status is Status.LOKASI_TIDAK_TERSEDIA
        assert "tidak dipalsukan" in result.note
        assert sel.text_field(portal.page, "aktivitas").input_value() == ""


# ── Diagnosis (canary) ──────────────────────────────────────────────────────


def test_check_reports_readiness_without_changing_anything(open_portal) -> None:
    d = date(2026, 10, 27)
    with open_portal() as portal:
        report = portal.check(d)
        assert report["login"] is True and report["status"] == "BELUM_DIISI"
        assert report["location"] is True and report["attendance_value"] == "Hadir"
        assert all(report["fields_found"].values()) and report["declaration_found"]
        assert report["save_button_found"] and report["save_button_enabled"] is False
        assert portal.read_day(d).status is DayStatus.BELUM_DIISI
