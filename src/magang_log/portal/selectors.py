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

from ..models import DayInfo, DayStatus

BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]  # fmt: skip

HARI = [
    "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu",
]  # fmt: skip

# Teks pernyataan di form. Dicentang HANYA setelah pengguna menyetujui isi (lihat ApprovedEntry).
DECLARATION = "Saya menyatakan telah meninjau dan memastikan isian laporan ini sudah benar"
LOCATION_OK_TEXT = "Lokasi berhasil diakses"
LOCATION_ERROR_TEXTS = (
    "Lokasi tidak dapat diakses",
    "tidak dapat diakses",
    "Gagal mengakses lokasi",
    "Izinkan akses lokasi",
    "Koordinat tidak ditemukan",
)
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

_NORMALIZED_STATUS_LABELS: dict[str, DayStatus] = {k.lower(): v for k, v in STATUS_LABELS.items()}

# Status terkirim yang sah menurut spesifikasi dan sistem portal
SUBMITTED_STATUS_LABELS: tuple[str, ...] = (
    "Menunggu Persetujuan",
    "Hadir disetujui",
    "Menunggu Tindakan Mentor",
    "Izin disetujui",
)


def is_submitted_status_text(text: str) -> bool:
    """Periksa apakah teks atau label memuat salah satu status terkirim resmi."""
    return any(s.lower() in text.lower() for s in SUBMITTED_STATUS_LABELS)


def classify(label: str, disabled: bool) -> DayStatus:
    """Ubah aria-label tombol hari + status disabled menjadi DayStatus."""
    if not label or not label.strip():
        return DayStatus.TIDAK_DIKENAL
    status_text = label.rsplit(",", 1)[-1].strip()
    status = STATUS_LABELS.get(status_text)
    if status is None:
        status = _NORMALIZED_STATUS_LABELS.get(status_text.lower(), DayStatus.TIDAK_DIKENAL)
    if status is DayStatus.BELUM_DIISI and disabled:
        return DayStatus.TERKUNCI
    return status


def nama_hari_id(d: date) -> str:
    """Nama hari dalam bahasa Indonesia (0=Senin, ..., 6=Minggu)."""
    return HARI[d.weekday()]


def tanggal_id(d: date) -> str:
    """'27 Oktober 2026' (tanpa nol di depan hari)."""
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def tanggal_lengkap_id(d: date) -> str:
    """'Selasa, 27 Oktober 2026'."""
    return f"{nama_hari_id(d)}, {tanggal_id(d)}"


def format_day_label_prefix(d: date) -> str:
    """Format awalan label hari aksesibel, mis. 'Selasa, 27 Oktober 2026'."""
    return tanggal_lengkap_id(d)


# ── Halaman riwayat ──────────────────────────────────────────────────────────


def history_heading(page: Page) -> Locator:
    return page.get_by_role("heading", name="Riwayat Kehadiran", exact=True)


def day_button(page: Page, d: date) -> Locator:
    """Tombol hari menggunakan format nama hari yang dapat diakses (mis. 'Selasa, 27 Oktober 2026, ...')."""
    pattern = re.compile(
        rf"(?:{re.escape(nama_hari_id(d))},\s*|,\s*){re.escape(tanggal_id(d))}\s*,"
    )
    return page.get_by_role("button", name=pattern)


def extract_day_info(button: Locator, d: date) -> DayInfo:
    """Ekstrak atribut aksesibilitas tombol hari menjadi instance DayInfo."""
    label = button.get_attribute("aria-label") or ""
    disabled = button.is_disabled()
    is_today = button.get_attribute("aria-current") == "date"
    return DayInfo(d, classify(label, disabled), label, disabled, is_today)


# ── Panel form "Tambah laporan" ──────────────────────────────────────────────


def form(page: Page) -> Locator:
    return page.locator("form.daily-form")


def form_heading(page: Page, d: date) -> Locator:
    """Judul panel, mis. 'Tambah laporan · 27 Oktober 2026' (pemisah: titik tengah U+00B7)."""
    pattern = re.compile(rf"Tambah laporan\s*\W+\s*{re.escape(tanggal_id(d))}")
    return page.get_by_role("heading", name=pattern)


def location_block(page: Page) -> Locator:
    """Blok indikator status izin lokasi pada form."""
    return form(page).locator(".location-permission")


def location_ok(page: Page) -> Locator:
    return location_block(page).get_by_text(LOCATION_OK_TEXT)


def location_error(page: Page) -> Locator:
    """Locator indikasi galat lokasi pada blok perizinan."""
    pattern = re.compile(
        r"tidak dapat diakses|gagal|ditolak|tidak ditemukan|izinkan akses", re.IGNORECASE
    )
    return location_block(page).filter(has_text=pattern)


def attendance_input(page: Page) -> Locator:
    """Kolom Kehadiran (v-select Vuetify; nilai bawaan 'Hadir')."""
    return form(page).get_by_label("Kehadiran", exact=True)


def attendance_combobox(page: Page) -> Locator:
    """Combobox Kehadiran (input[role='combobox'] di dalam form)."""
    return form(page).locator("input[role='combobox']")


def text_field(page: Page, key: str) -> Locator:
    return form(page).get_by_label(FIELD_LABELS[key], exact=True)


def declaration(page: Page) -> Locator:
    return form(page).get_by_role("checkbox", name=DECLARATION, exact=True)


def declaration_label(page: Page) -> Locator:
    """Cadangan bila input checkbox Vuetify tersembunyi: klik labelnya."""
    return form(page).locator("label").filter(has_text=DECLARATION)


def save_button(page: Page) -> Locator:
    return form(page).get_by_role("button", name=SAVE_BUTTON, exact=True)


def check_selectors_health(page: Page, d: date) -> dict[str, dict[str, object]]:
    """Pemeriksaan kesehatan canary untuk memastikan seluruh locator semantik portal ada dan unik."""
    health: dict[str, dict[str, object]] = {}

    checks: list[tuple[str, str, Locator]] = [
        ("page_heading", "Judul Riwayat Kehadiran (h1)", history_heading(page)),
        ("day_button", f"Tombol kalender hari {tanggal_id(d)}", day_button(page, d)),
        ("form_panel", "Panel formulir laporan (form.daily-form)", form(page)),
        ("form_heading", f"Judul panel formulir ({tanggal_id(d)})", form_heading(page, d)),
        ("location_status", "Blok status izin lokasi", location_ok(page)),
        ("attendance_field", "Kolom Kehadiran (role=combobox)", attendance_input(page)),
        ("field_aktivitas", "Textarea Uraian aktivitas", text_field(page, "aktivitas")),
        (
            "field_pembelajaran",
            "Textarea Pembelajaran yang diperoleh",
            text_field(page, "pembelajaran"),
        ),
        ("field_kendala", "Textarea Kendala yang dialami", text_field(page, "kendala")),
        ("declaration_checkbox", "Kotak centang konfirmasi peninjauan", declaration(page)),
        ("save_button", "Tombol 'Simpan dan Kirim'", save_button(page)),
    ]

    for key, desc, loc in checks:
        try:
            count = loc.count()
            health[key] = {
                "description": desc,
                "count": count,
                "is_unique": count == 1,
                "healthy": count == 1,
            }
        except Exception as exc:  # noqa: BLE001
            health[key] = {
                "description": desc,
                "count": 0,
                "is_unique": False,
                "healthy": False,
                "error": str(exc),
            }

    return health
