"""Pengisi form logbook MagangHub: Playwright deterministik, TANPA LLM.

Prinsip (lihat PRD, bagian 8.7 dan 14):
* Satu-satunya input pengiriman adalah ``ApprovedEntry`` (isi yang sudah ditinjau manusia).
* Tidak pernah mengetik kredensial/OTP. Sesi dibuat pengguna lewat ``magang-portal login``.
* Tidak pernah memalsukan lokasi: izin geolocation hanya diberikan ke origin portal dan
  koordinat TIDAK di-override. Bila portal tidak mendapat lokasi => berhenti.
* Fail-closed: status hari/label yang tidak dikenal => berhenti tanpa menyentuh form.
* Pernyataan "sudah meninjau" hanya dicentang bila ``approved_at`` ada.
* Verifikasi setelah kirim = muat ulang halaman dari server lalu baca status hari, bukan
  percaya pada hasil klik.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from ..models import ApprovedEntry, DayInfo, DayStatus, PortalResult, Status
from . import selectors as sel


class LoginRequired(Exception):
    """Sesi habis / belum login: pengguna harus menjalankan `magang-portal login`."""


class PortalError(Exception):
    """Halaman tidak seperti yang diharapkan (selector/label berubah, periode lain, dsb.)."""


class NotApproved(Exception):
    """Entri belum disetujui manusia (approved_at kosong)."""


@dataclass
class PortalConfig:
    base_url: str = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat"
    auth_state: Path = Path("data/auth/state.json")
    artifacts_dir: Path = Path("data/runs")
    headless: bool = False  # lokasi lebih andal pada browser berjendela; uji dengan `check`
    channel: str | None = "chrome"  # Chrome terpasang; None = Chromium bawaan Playwright
    timeout_ms: int = 15_000
    location_timeout_ms: int = 10_000
    min_chars: int = 100  # tertulis di form: "Minimal 100 karakter"
    max_chars: int = 5000  # atribut maxlength pada textarea
    allow_location: bool = True  # False hanya untuk menguji jalur "lokasi tidak tersedia"
    login_markers: tuple[str, ...] = ("account.kemnaker.go.id", "/login", "/auth")


_EARLY_EXIT: dict[DayStatus, Status] = {
    DayStatus.SUDAH_TERKIRIM: Status.SUDAH_TERKIRIM,
    DayStatus.LIBUR: Status.LIBUR,
    DayStatus.TERKUNCI: Status.TERKUNCI,
    DayStatus.PERLU_TINDAKAN: Status.PERLU_TINDAKAN,
    DayStatus.TIDAK_DIKENAL: Status.PERLU_TINDAKAN,
}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _first_line(exc: BaseException) -> str:
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0][:300]


class PlaywrightPortal(AbstractContextManager["PlaywrightPortal"]):
    def __init__(self, config: PortalConfig | None = None) -> None:
        self.cfg = config or PortalConfig()
        self.page = None  # diisi di __enter__

    # ── siklus hidup ────────────────────────────────────────────────────────

    def __enter__(self) -> PlaywrightPortal:
        cfg = self.cfg
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(headless=cfg.headless, channel=cfg.channel)
            kwargs: dict[str, str] = {}
            if cfg.auth_state.exists():
                kwargs["storage_state"] = str(cfg.auth_state)
            self._ctx = self._browser.new_context(**kwargs)
            self._ctx.set_default_timeout(cfg.timeout_ms)
            if cfg.allow_location:
                # Hanya untuk origin portal. Koordinat TIDAK di-override.
                self._ctx.grant_permissions(["geolocation"], origin=_origin(cfg.base_url))
            self.page = self._ctx.new_page()
        except Exception:
            self._pw.stop()
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        for name in ("_ctx", "_browser"):
            obj = getattr(self, name, None)
            if obj is not None:
                try:
                    obj.close()
                except PlaywrightError:
                    pass  # sudah tertutup; tidak ada yang perlu dilaporkan
        self._pw.stop()

    # ── navigasi dan pembacaan ──────────────────────────────────────────────

    def _url(self, d: date) -> str:
        parts = urlsplit(self.cfg.base_url)
        query = dict(parse_qsl(parts.query))
        query.update({"date": d.isoformat(), "view": "detail"})
        return urlunsplit(parts._replace(query=urlencode(query)))

    def open_history(self, d: date) -> None:
        """Buka halaman Riwayat. Muat dari server (juga dipakai sebagai 'muat ulang')."""
        self.page.goto(self._url(d), wait_until="domcontentloaded")
        try:
            sel.history_heading(self.page).wait_for(state="visible", timeout=self.cfg.timeout_ms)
        except PlaywrightTimeout:
            url = self.page.url
            if any(marker in url for marker in self.cfg.login_markers):
                raise LoginRequired(url) from None
            raise PortalError(f"halaman Riwayat Kehadiran tidak muncul (url: {url})") from None

    def read_day(self, d: date) -> DayInfo:
        button = sel.day_button(self.page, d)
        try:
            button.first.wait_for(state="attached", timeout=self.cfg.timeout_ms)
        except PlaywrightTimeout:
            raise PortalError(f"tombol tanggal {d} tidak ditemukan (periode lain?)") from None
        count = button.count()
        if count != 1:
            raise PortalError(f"tombol tanggal {d} ditemukan {count}x, seharusnya 1x")
        label = button.get_attribute("aria-label") or ""
        disabled = button.is_disabled()
        is_today = button.get_attribute("aria-current") == "date"
        return DayInfo(d, sel.classify(label, disabled), label, disabled, is_today)

    def _open_form(self, d: date) -> None:
        heading = sel.form_heading(self.page, d)
        if not heading.is_visible():
            sel.day_button(self.page, d).click()
        heading.wait_for(state="visible", timeout=self.cfg.timeout_ms)

    def _location_ok(self) -> bool:
        try:
            sel.location_ok(self.page).wait_for(
                state="visible", timeout=self.cfg.location_timeout_ms
            )
        except PlaywrightTimeout:
            return False
        return True

    def _wait_until(self, predicate: Callable[[], bool], timeout_ms: int) -> bool:
        waited = 0
        while waited <= timeout_ms:
            if predicate():
                return True
            self.page.wait_for_timeout(200)
            waited += 200
        return predicate()

    def _shot(self, d: date, name: str) -> Path | None:
        try:
            path = self.cfg.artifacts_dir / d.isoformat() / f"{name}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path), full_page=True)
        except (PlaywrightError, OSError):
            return None  # screenshot hanya bantuan diagnosis; jangan menutupi galat asli
        return path

    # ── diagnosis tanpa mengubah apa pun ────────────────────────────────────

    def check(self, d: date) -> dict:
        """Pemeriksaan kesiapan (canary): tidak mengisi atau mengirim apa pun."""
        report: dict = {"date": d.isoformat(), "login": False}
        try:
            self.open_history(d)
            report["login"] = True
            day = self.read_day(d)
            report.update(
                status=day.status.value, label=day.label, disabled=day.disabled, today=day.is_today
            )
            if day.status is DayStatus.BELUM_DIISI:
                self._open_form(d)
                report["location"] = self._location_ok()
                report["attendance_value"] = sel.attendance_input(self.page).input_value()
                report["fields_found"] = {
                    key: sel.text_field(self.page, key).count() == 1 for key in sel.FIELD_LABELS
                }
                report["declaration_found"] = sel.declaration(self.page).count() == 1
                save = sel.save_button(self.page)
                report["save_button_found"] = save.count() == 1
                report["save_button_enabled"] = save.is_enabled() if save.count() == 1 else None
        except LoginRequired as exc:
            report["error"] = f"LOGIN_DIPERLUKAN ({_first_line(exc)})"
        except (PortalError, PlaywrightError) as exc:
            report["error"] = _first_line(exc)
        return report

    # ── pengisian dan pengiriman ────────────────────────────────────────────

    def submit(self, entry: ApprovedEntry, *, dry_run: bool = False) -> PortalResult:
        problems = entry.problems(self.cfg.min_chars, self.cfg.max_chars)
        if problems:
            raise ValueError("; ".join(problems))
        if not dry_run and entry.approved_at is None:
            raise NotApproved("entri belum disetujui manusia (approved_at kosong)")

        d = entry.work_date
        day: DayInfo | None = None
        shots: list[Path] = []
        try:
            self.open_history(d)
            day = self.read_day(d)

            early = _EARLY_EXIT.get(day.status)
            if early is not None:
                return PortalResult(
                    early, f"status hari: '{day.label}'; form tidak disentuh", day, shots
                )

            self._open_form(d)

            if not self._location_ok():
                if (path := self._shot(d, "lokasi-tidak-tersedia")) is not None:
                    shots.append(path)
                return PortalResult(
                    Status.LOKASI_TIDAK_TERSEDIA,
                    "portal tidak mendapat lokasi; lokasi tidak dipalsukan. Izinkan lokasi "
                    "untuk browser lalu coba lagi (uji dengan `magang-portal check`)",
                    day,
                    shots,
                )

            attendance = sel.attendance_input(self.page).input_value().strip()
            if attendance != entry.kehadiran:
                raise PortalError(
                    f"kolom Kehadiran bernilai {attendance!r}, bukan {entry.kehadiran!r}"
                )

            for key in sel.FIELD_LABELS:
                text = getattr(entry, key).strip()
                field = sel.text_field(self.page, key)
                field.fill(text)
                if field.input_value() != text:
                    raise PortalError(f"isi '{key}' tidak tersimpan utuh di form")

            if dry_run:
                if (path := self._shot(d, "dryrun")) is not None:
                    shots.append(path)
                return PortalResult(
                    Status.DRYRUN,
                    "kolom terisi; pernyataan TIDAK dicentang dan tombol kirim TIDAK diklik",
                    day,
                    shots,
                )

            self._tick_declaration()
            save = sel.save_button(self.page)
            if not self._wait_until(save.is_enabled, 5_000):
                raise PortalError("tombol 'Simpan dan Kirim' tetap nonaktif setelah form terisi")
            save.click()
            return self._verify_after_submit(d, shots)

        except LoginRequired as exc:
            return PortalResult(
                Status.LOGIN_DIPERLUKAN, f"sesi habis ({_first_line(exc)})", day, shots
            )
        except (PortalError, PlaywrightError) as exc:
            if (path := self._shot(d, "gagal")) is not None:
                shots.append(path)
            return PortalResult(Status.GAGAL, _first_line(exc), day, shots)

    def _tick_declaration(self) -> None:
        checkbox = sel.declaration(self.page)
        try:
            checkbox.check(timeout=3_000)
        except PlaywrightError:
            # Input checkbox Vuetify bisa tersembunyi di balik wrapper: klik labelnya.
            sel.declaration_label(self.page).click()
        if not checkbox.is_checked():
            raise PortalError("pernyataan peninjauan tidak berhasil dicentang")

    def _verify_after_submit(self, d: date, shots: list[Path]) -> PortalResult:
        """Verifikasi independen: muat ulang dari server, baca status hari dari kalender."""
        last: DayInfo | None = None
        for _ in range(5):
            self.page.wait_for_timeout(1_500)
            self.open_history(d)
            last = self.read_day(d)
            if last.status is DayStatus.SUDAH_TERKIRIM:
                return PortalResult(
                    Status.BERHASIL,
                    f"status hari setelah muat ulang: '{last.label}'. Catatan: isi teks belum "
                    "dibaca-balik (butuh snapshot halaman detail hari yang sudah terkirim)",
                    last,
                    shots,
                )
        if (path := self._shot(d, "verifikasi-gagal")) is not None:
            shots.append(path)
        return PortalResult(
            Status.GAGAL,
            f"status hari tidak berubah setelah kirim (terakhir: '{last.label if last else '?'}')",
            last,
            shots,
        )
