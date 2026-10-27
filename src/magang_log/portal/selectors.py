"""SEMUA selector dan teks portal ada di file ini (satu-satunya tempat yang perlu diubah
bila portal berubah).

Sumber: snapshot halaman /dashboard/riwayat bertanggal 2026-10-27 (Nuxt + Vuetify).
Keputusan desain berdasarkan snapshot itu:

* ID elemen (input-v-5, input-v-9, checkbox-v-17 ...) dibuat otomatis oleh Vuetify dan
  berubah antar-render, jadi TIDAK dipakai. Semua elemen dicari lewat role + nama yang
  terlihat pengguna (label/aria-label), yang stabil selama teks di layar tidak berubah.
* Status sebuah hari dibaca dari aria-label tombol hari, mis.
  "Selasa, 27 Oktober 2026, Belum Diisi" (segmen terakhir setelah koma = status).
* Hari yang tidak boleh diisi ditandai atribut `disabled` pada tombol hari.
"""

from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Locator, Page

from ..models import DayStatus

BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]  # fmt: skip

# Teks pernyataan di form. Dicentang HANYA setelah pengguna menyetujui isi (lihat ApprovedEntry).
DECLARATION = "Saya menyatakan telah meninjau dan memastikan isian laporan ini sudah benar"
LOCATION_OK_TEXT = "Lokasi berhasil diakses"
SAVE_BUTTON = "Simpan dan Kirim"

FIELD_LABELS = {
    "aktivitas": "Uraian aktivitas",
    "pembelajaran": "Pembelajaran yang diperoleh",
    "kendala": "Kendala yang dialami",
}

# Status hari. "teramati" = terlihat di aria-label pada snapshot; "legenda" = hanya ada di
# legenda kalender, jadi bentuk aria-label-nya belum dikonfirmasi. Label yang tidak ada di
# tabel ini diperlakukan TIDAK_DIKENAL (berhenti, tidak menyentuh apa pun).
STATUS_LABELS: dict[str, DayStatus] = {
    "Belum Diisi": DayStatus.BELUM_DIISI,  # teramati
    "Menunggu Persetujuan": DayStatus.SUDAH_TERKIRIM,  # teramati
    "Jadwal libur posisi": DayStatus.LIBUR,  # teramati
    "Menunggu Tindakan Mentor": DayStatus.SUDAH_TERKIRIM,  # legenda
    "Hadir disetujui": DayStatus.SUDAH_TERKIRIM,  # legenda
    "Izin disetujui": DayStatus.SUDAH_TERKIRIM,  # legenda
    "Hari Libur": DayStatus.LIBUR,  # legenda
    "Perlu Tindakan Anda": DayStatus.PERLU_TINDAKAN,  # legenda
    "Kehadiran Ditolak": DayStatus.PERLU_TINDAKAN,  # legenda
    "Tidak Hadir": DayStatus.PERLU_TINDAKAN,  # legenda
}


def classify(label: str, disabled: bool) -> DayStatus:
    """Ubah aria-label tombol hari + status disabled menjadi DayStatus."""
    status_text = label.rsplit(",", 1)[-1].strip()
    status = STATUS_LABELS.get(status_text, DayStatus.TIDAK_DIKENAL)
    if status is DayStatus.BELUM_DIISI and disabled:
        return DayStatus.TERKUNCI
    return status


def tanggal_id(d: date) -> str:
    """'27 Oktober 2026' (tanpa nol di depan hari)."""
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


# ── Halaman riwayat ──────────────────────────────────────────────────────────


def history_heading(page: Page) -> Locator:
    return page.get_by_role("heading", name="Riwayat Kehadiran", exact=True)


def day_button(page: Page, d: date) -> Locator:
    """Tombol hari. Pola ', 2 November 2026,' tidak cocok dengan ', 12 November 2026,'."""
    pattern = re.compile(rf",\s*{re.escape(tanggal_id(d))}\s*,")
    return page.get_by_role("button", name=pattern)


# ── Panel form "Tambah laporan" ──────────────────────────────────────────────


def form(page: Page) -> Locator:
    return page.locator("form.daily-form")


def form_heading(page: Page, d: date) -> Locator:
    """Judul panel, mis. 'Tambah laporan · 27 Oktober 2026' (pemisah: titik tengah U+00B7)."""
    pattern = re.compile(rf"Tambah laporan\s*\W+\s*{re.escape(tanggal_id(d))}")
    return page.get_by_role("heading", name=pattern)


def location_ok(page: Page) -> Locator:
    return form(page).locator(".location-permission").get_by_text(LOCATION_OK_TEXT)


def attendance_input(page: Page) -> Locator:
    """Kolom Kehadiran (v-select Vuetify; nilai bawaan 'Hadir')."""
    return form(page).get_by_label("Kehadiran", exact=True)


def text_field(page: Page, key: str) -> Locator:
    return form(page).get_by_label(FIELD_LABELS[key], exact=True)


def declaration(page: Page) -> Locator:
    return form(page).get_by_role("checkbox", name=DECLARATION, exact=True)


def declaration_label(page: Page) -> Locator:
    """Cadangan bila input checkbox Vuetify tersembunyi: klik labelnya."""
    return form(page).locator("label").filter(has_text=DECLARATION)


def save_button(page: Page) -> Locator:
    return form(page).get_by_role("button", name=SAVE_BUTTON, exact=True)
