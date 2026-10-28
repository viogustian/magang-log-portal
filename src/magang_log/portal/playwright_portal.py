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

import time
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
from .anti_tamper import AntiTamperDecision, AntiTamperGate
from .session import LoginRequired, SessionManager


class PortalError(Exception):
    """Halaman tidak seperti yang diharapkan (selector/label berubah, periode lain, dsb.)."""


class NotApproved(Exception):
    """Entri belum disetujui manusia (approved_at kosong)."""


def assert_approved_for_submission(entry: ApprovedEntry) -> None:
    """Memastikan draf sudah disetujui manusia sebelum dikirim ke portal."""
    if entry.approved_at is None:
        raise NotApproved("entri belum disetujui manusia (approved_at kosong)")


@dataclass
class PortalConfig:
    base_url: str = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat"
    auth_state: Path = Path("data/auth/state.json")
    artifacts_dir: Path = Path("data/runs")
    headless: bool = False  # lokasi lebih andal pada browser berjendela; uji dengan `check`
    channel: str | None = "chrome"  # Chrome terpasang; None = Chromium bawaan Playwright
    timeout_ms: int = 15_000
    location_timeout_ms: int = 25_000
    min_chars: int = 100  # tertulis di form: "Minimal 100 karakter"
    max_chars: int = 5000  # atribut maxlength pada textarea
    allow_location: bool = True  # False hanya untuk menguji jalur "lokasi tidak tersedia"
    login_markers: tuple[str, ...] = ("account.kemnaker.go.id", "/login", "/auth")
    require_session: bool = False  # jika True, auth_state wajib valid sebelum membuka browser


_EARLY_EXIT: dict[DayStatus, Status] = {
    DayStatus.SUDAH_TERKIRIM: Status.SUDAH_TERKIRIM,
    DayStatus.LIBUR: Status.LIBUR,
    DayStatus.TERKUNCI: Status.TERKUNCI,
    DayStatus.PERLU_TINDAKAN: Status.PERLU_TINDAKAN,
    DayStatus.TIDAK_DIKENAL: Status.TIDAK_DIKENAL,
}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _first_line(exc: BaseException) -> str:
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0][:300]


class PlaywrightPortal(AbstractContextManager["PlaywrightPortal"]):
    def __init__(self, config: PortalConfig | None = None) -> None:
        self.cfg = config or PortalConfig()
        self.session_mgr = SessionManager(
            auth_state=self.cfg.auth_state,
            base_url=self.cfg.base_url,
            channel=self.cfg.channel,
            timeout_ms=self.cfg.timeout_ms,
            login_markers=self.cfg.login_markers,
        )
        self.page = None  # diisi di __enter__

    # ── siklus hidup ────────────────────────────────────────────────────────

    def __enter__(self) -> PlaywrightPortal:
        cfg = self.cfg
        if cfg.require_session:
            self.session_mgr.load_session()

        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(headless=cfg.headless, channel=cfg.channel)
            kwargs: dict[str, str] = {}
            if cfg.auth_state.exists():
                self.session_mgr.load_session()
                kwargs["storage_state"] = str(cfg.auth_state)
            self._ctx = self._browser.new_context(**kwargs)
            self._ctx.set_default_timeout(cfg.timeout_ms)
            if cfg.allow_location:
                # Hanya untuk origin portal. Koordinat dibaca langsung dari sensor fisik OS perangkat.
                self._ctx.grant_permissions(["geolocation"], origin=_origin(cfg.base_url))
                from .device_location import get_windows_device_location

                device_loc = get_windows_device_location()
                if device_loc is not None:
                    self._ctx.set_geolocation(device_loc)
            self._ctx.tracing.start(screenshots=True, snapshots=True, sources=True)
            self.page = self._ctx.new_page()
        except Exception:
            self._pw.stop()
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        if hasattr(self, "_ctx") and self._ctx is not None:
            try:
                self._ctx.tracing.stop()
            except PlaywrightError:
                pass
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

    def open_history(self, d: date, wait_until: str = "domcontentloaded") -> None:
        """Buka halaman Riwayat. Muat dari server (juga dipakai sebagai 'muat ulang')."""
        try:
            self.page.goto(self._url(d), wait_until=wait_until)
        except PlaywrightTimeout:
            if wait_until == "networkidle":
                self.page.goto(self._url(d), wait_until="domcontentloaded")
            else:
                raise
        self.session_mgr.check_page(self.page)
        try:
            sel.history_heading(self.page).wait_for(state="visible", timeout=3000)
        except PlaywrightTimeout:
            # Jika Nuxt SPA me-redirect cold-load ke /dashboard (Beranda), klik menu 'Riwayat'
            riwayat_nav = self.page.locator("text=Riwayat").first
            if riwayat_nav.is_visible():
                riwayat_nav.click()
            try:
                sel.history_heading(self.page).wait_for(state="visible", timeout=self.cfg.timeout_ms)
            except PlaywrightTimeout:
                self.session_mgr.check_page(self.page)
                url = self.page.url
                if any(marker in url for marker in self.cfg.login_markers):
                    raise LoginRequired(url=url) from None
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
        return sel.extract_day_info(button, d)

    def inspect_day(self, d: date) -> tuple[DayInfo, AntiTamperDecision]:
        """Pemeriksaan kalender dan evaluasi anti-tamper untuk tanggal d tanpa menyentuh form."""
        self.open_history(d)
        day = self.read_day(d)
        decision = AntiTamperGate.inspect(day)
        return day, decision

    def _open_form(self, d: date) -> None:
        heading = sel.form_heading(self.page, d)
        if not heading.is_visible():
            sel.day_button(self.page, d).click()
        heading.wait_for(state="visible", timeout=self.cfg.timeout_ms)

    def _location_ok(self) -> bool:
        """Periksa apakah lokasi berhasil diakses portal tanpa mock koordinat buatan."""
        try:
            start_time = time.monotonic()
            timeout_sec = self.cfg.location_timeout_ms / 1000.0
            ok_loc = sel.location_ok(self.page)
            err_loc = sel.location_error(self.page)

            while time.monotonic() - start_time < timeout_sec:
                if ok_loc.is_visible():
                    return True
                if err_loc.is_visible():
                    return False
                self.page.wait_for_timeout(200)

            return ok_loc.is_visible()
        except PlaywrightError:
            return False

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

    def _save_trace(self, d: date, name: str = "trace") -> Path | None:
        try:
            path = self.cfg.artifacts_dir / d.isoformat() / f"{name}.zip"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._ctx.tracing.stop(path=str(path))
            return path
        except (PlaywrightError, OSError):
            return None

    # ── diagnosis tanpa mengubah apa pun ────────────────────────────────────

    def check(self, d: date) -> dict:
        """Pemeriksaan kesiapan (canary): tidak mengisi atau mengirim apa pun."""
        report: dict = {"date": d.isoformat(), "login": False}
        try:
            self.open_history(d)
            report["login"] = True
            day = self.read_day(d)
            decision = AntiTamperGate.inspect(day)
            report.update(
                status=day.status.value,
                label=day.label,
                disabled=day.disabled,
                today=day.is_today,
                submittable=decision.submittable,
                anti_tamper_decision=decision.status.value,
                anti_tamper_reason=decision.reason,
            )
            if decision.submittable:
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
                report["selectors_health"] = sel.check_selectors_health(self.page, d)
                report["all_selectors_healthy"] = all(
                    bool(v.get("healthy")) for v in report["selectors_health"].values()
                )
        except LoginRequired as exc:
            report["error"] = f"LOGIN_DIPERLUKAN ({_first_line(exc)})"
        except (PortalError, PlaywrightError) as exc:
            report["error"] = _first_line(exc)
        return report

    # ── pengisian dan pengiriman ────────────────────────────────────────────

    def submit(self, entry: ApprovedEntry, *, dry_run: bool = False) -> PortalResult:
        if self.page is None:
            with self:
                return self.submit(entry, dry_run=dry_run)
        problems = entry.problems(self.cfg.min_chars, self.cfg.max_chars)
        if problems:
            raise ValueError("; ".join(problems))
        if not dry_run:
            assert_approved_for_submission(entry)

        d = entry.work_date
        day: DayInfo | None = None
        shots: list[Path] = []
        traces: list[Path] = []
        try:
            self.open_history(d)
            day = self.read_day(d)

            decision = AntiTamperGate.inspect(day)
            if not decision.submittable:
                return PortalResult(
                    decision.status,
                    f"status hari: '{day.label}'; form tidak disentuh ({decision.reason})",
                    day,
                    shots,
                    traces,
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
                    traces,
                )

            attendance = sel.attendance_input(self.page).input_value().strip()
            if attendance != entry.kehadiran:
                raise PortalError(
                    f"kolom Kehadiran bernilai {attendance!r}, bukan {entry.kehadiran!r}"
                )

            self.populate_form(entry)

            if dry_run:
                if (path := self._shot(d, "dryrun")) is not None:
                    shots.append(path)
                return PortalResult(
                    Status.DRYRUN,
                    "kolom terisi; pernyataan TIDAK dicentang dan tombol kirim TIDAK diklik",
                    day,
                    shots,
                    traces,
                )

            self._tick_declaration(entry)
            save = sel.save_button(self.page)
            if not self._wait_until(save.is_enabled, 5_000):
                raise PortalError("tombol 'Simpan dan Kirim' tetap nonaktif setelah form terisi")
            save.click()
            try:
                # Menunggu dialog/form tertutup atau network request selesai setelah kirim
                sel.form(self.page).wait_for(state="hidden", timeout=5_000)
            except (PlaywrightError, PlaywrightTimeout):
                pass
            return self._verify_after_submit(d, shots, traces)

        except LoginRequired as exc:
            return PortalResult(
                Status.LOGIN_DIPERLUKAN, f"sesi habis ({_first_line(exc)})", day, shots, traces
            )
        except (PortalError, PlaywrightError) as exc:
            if (path := self._shot(d, "gagal")) is not None:
                shots.append(path)
            if (tpath := self._save_trace(d, "trace-gagal")) is not None:
                traces.append(tpath)
            return PortalResult(Status.GAGAL, _first_line(exc), day, shots, traces)

    def populate_form(self, entry: ApprovedEntry) -> dict[str, str]:
        """Isi seluruh kolom formulir dan baca-balik untuk memverifikasi keutuhan teks."""
        read_back: dict[str, str] = {}
        for key in sel.FIELD_LABELS:
            text = getattr(entry, key).strip()
            field = sel.text_field(self.page, key)
            field.fill(text)
            val = field.input_value()
            read_back[key] = val
            if val != text:
                if len(val) < len(text):
                    raise PortalError(
                        f"kolom '{key}' mengalami pemotongan (truncation): "
                        f"diharapkan {len(text)} karakter, terbaca {len(val)} karakter"
                    )
                raise PortalError(
                    f"isi kolom '{key}' tidak tersimpan utuh di form "
                    f"(mismatch / encoding loss / corruption)"
                )
        return read_back

    def fill(self, entry: ApprovedEntry) -> PortalResult:
        """Isi formulir dalam mode dry-run tanpa mencentang atau mengirim."""
        return self.submit(entry, dry_run=True)

    def _tick_declaration(self, entry: ApprovedEntry) -> None:
        """Centang pernyataan legalitas HANYA jika draf sudah disetujui manusia."""
        assert_approved_for_submission(entry)
        checkbox = sel.declaration(self.page)
        try:
            checkbox.check(timeout=3_000)
        except PlaywrightError:
            # Input checkbox Vuetify bisa tersembunyi di balik wrapper: klik labelnya.
            sel.declaration_label(self.page).click()
        if not checkbox.is_checked():
            raise PortalError("pernyataan peninjauan tidak berhasil dicentang")

    def _verify_after_submit(self, d: date, shots: list[Path], traces: list[Path]) -> PortalResult:
        """Verifikasi independen: muat ulang dari server, baca status hari dari kalender."""
        last: DayInfo | None = None
        for _ in range(5):
            self.page.wait_for_timeout(2_000)
            self.open_history(d, wait_until="networkidle")
            last = self.read_day(d)
            if last.status is DayStatus.SUDAH_TERKIRIM or sel.is_submitted_status_text(last.label):
                return PortalResult(
                    Status.BERHASIL,
                    f"status hari setelah muat ulang: '{last.label}'. Catatan: isi teks belum "
                    "dibaca-balik (butuh snapshot halaman detail hari yang sudah terkirim)",
                    last,
                    shots,
                    traces,
                )
        if (path := self._shot(d, "verifikasi-gagal")) is not None:
            shots.append(path)
        if (tpath := self._save_trace(d, "trace-verifikasi-gagal")) is not None:
            traces.append(tpath)
        return PortalResult(
            Status.GAGAL,
            f"status hari tidak berubah setelah kirim (terakhir: '{last.label if last else '?'}')",
            last,
            shots,
            traces,
        )
