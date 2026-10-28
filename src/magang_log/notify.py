"""Modul notifikasi desktop Windows Toast dengan penegakan guardrail privasi."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Protocol, Sequence, runtime_checkable

from .logger import PrivacyViolationError
from .models import Status

logger = logging.getLogger(__name__)

# Pemetaan nama bulan dalam bahasa Indonesia untuk format tanggal <DD> <Bln>
INDONESIAN_MONTHS: dict[int, str] = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

# Pola terlarang dalam pesan notifikasi untuk mencegah kebocoran data rahasia
PROHIBITED_NOTIFICATION_PATTERNS: tuple[str, ...] = (
    "aktivitas",
    "pembelajaran",
    "kendala",
    "diff --git",
    "commit ",
    "password",
    "token",
    "bearer ",
    "secret",
    "api_key",
)


def format_indonesian_date(d: date) -> str:
    """Format tanggal ke bentuk <DD> <Bln>, mis. '27 Oktober'."""
    month_name = INDONESIAN_MONTHS.get(d.month, str(d.month))
    return f"{d.day} {month_name}"


def assert_privacy_compliant(text: str) -> None:
    """Memastikan teks notifikasi tidak memuat rincian logbook, catatan refleksi, atau rahasia.

    Melempar PrivacyViolationError bila terdeteksi pelanggaran privasi.
    """
    lower = text.lower()
    for pattern in PROHIBITED_NOTIFICATION_PATTERNS:
        # Pengecualian khusus: kata kunci 'kendala' dalam kalimat bantuan diperbolehkan jika tidak memuat isi
        if pattern in lower:
            raise PrivacyViolationError(
                f"Pelanggaran privasi notifikasi: pesan tidak boleh memuat teks/pola '{pattern}'."
            )


@dataclass(frozen=True)
class NotificationSpec:
    """Spesifikasi judul dan template pesan notifikasi untuk satu status."""

    title: str
    body_template: str
    is_actionable: bool = True


# Matriks rute notifikasi resmi (lihat PRD & Issue 05-02)
NOTIFICATION_MATRIX: dict[Status, NotificationSpec] = {
    Status.PERLU_REVIEW: NotificationSpec(
        title="Magang Logbook",
        body_template="Draf {date_str} siap ditinjau: jalankan `magang-log review`.",
        is_actionable=True,
    ),
    Status.PERLU_INPUT: NotificationSpec(
        title="Magang Logbook",
        body_template="Bukti {date_str} belum cukup: tambahkan catatan lewat `magang-log note`.",
        is_actionable=True,
    ),
    Status.LOGIN_DIPERLUKAN: NotificationSpec(
        title="Sesi MagangHub Habis",
        body_template="Sesi portal telah berakhir: jalankan `magang-log login`.",
        is_actionable=True,
    ),
    Status.GAGAL: NotificationSpec(
        title="Pengiriman Gagal",
        body_template="Pengiriman {date_str} gagal; periksa log via `magang-log status`.",
        is_actionable=True,
    ),
    Status.TERKUNCI: NotificationSpec(
        title="Tanggal Terkunci",
        body_template="Tanggal {date_str} terkunci di portal; hubungi pembimbing.",
        is_actionable=True,
    ),
    Status.BERHASIL: NotificationSpec(
        title="Pengiriman Berhasil",
        body_template="Logbook {date_str} terkirim dan terverifikasi.",
        is_actionable=False,  # Opsional lewat konfigurasi notify_on_success
    ),
    # Event non-actionable: sepenuhnya senyap (silent)
    Status.LIBUR: NotificationSpec(
        title="",
        body_template="",
        is_actionable=False,
    ),
    Status.SUDAH_TERKIRIM: NotificationSpec(
        title="",
        body_template="",
        is_actionable=False,
    ),
    Status.DRYRUN: NotificationSpec(
        title="",
        body_template="",
        is_actionable=False,
    ),
}


@runtime_checkable
class Notifier(Protocol):
    """Protokol antarmuka untuk subsistem notifikasi."""

    def notify(self, status: Status, work_date: date, message: str = "") -> None:
        """Kirim notifikasi untuk status dan tanggal kerja yang bersangkutan."""
        ...


@runtime_checkable
class ToastBackend(Protocol):
    """Protokol untuk backend pengiriman toast OS."""

    def show_toast(self, title: str, message: str) -> bool:
        """Tampilkan notifikasi toast di layar."""
        ...


class PowerShellToastBackend:
    """Backend notifikasi toast Windows menggunakan PowerShell WinRT Runtime."""

    def show_toast(self, title: str, message: str) -> bool:
        safe_title = title.replace("'", "''")
        safe_msg = message.replace("'", "''")

        # Skrip PowerShell WinRT native (kompatibel Windows 10 & 11 tanpa modul pihak ketiga)
        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; "
            "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            "$textNodes = $template.GetElementsByTagName('text'); "
            f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) > $null; "
            f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) > $null; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Magang Logbook').Show($toast);"
        )

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                check=False,
                timeout=5,
                capture_output=True,
            )
            return res.returncode == 0
        except Exception as exc:  # noqa: BLE001
            logger.debug("PowerShell Toast gagal ditampilkan: %s", exc)
            return False


class WindowsToastNotifier:
    """Implementasi Notifier konkret yang mengirim Windows Toast sesuai matriks notifikasi."""

    def __init__(
        self,
        notify_on_success: bool = False,
        backend: ToastBackend | None = None,
    ) -> None:
        self.notify_on_success = notify_on_success
        self.backend = backend or PowerShellToastBackend()

    def notify(self, status: Status, work_date: date, message: str = "") -> None:
        spec = NOTIFICATION_MATRIX.get(status)
        if spec is None:
            return

        should_dispatch = spec.is_actionable
        if status == Status.BERHASIL:
            should_dispatch = self.notify_on_success

        if not should_dispatch or not spec.title:
            return

        date_str = format_indonesian_date(work_date)
        final_message = message if message else spec.body_template.format(date_str=date_str)

        # Tegakkan guardrail privasi sebelum mengirim
        assert_privacy_compliant(final_message)

        logger.info("TOAST: [%s] %s", spec.title, final_message)
        self.backend.show_toast(spec.title, final_message)


@dataclass(frozen=True)
class NotificationRecord:
    """Catatan riwayat pengiriman notifikasi untuk FakeNotifier."""

    status: Status
    work_date: date
    title: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def body(self) -> str:
        """Alias pesan notifikasi agar kompatibel dengan field body dan message."""
        return self.message


class FakeNotifier:
    """Implementasi Notifier tiruan untuk pengetesan unit, integrasi, dan headless CI."""

    def __init__(self, notify_on_success: bool = False) -> None:
        self.notify_on_success = notify_on_success
        self.notifications: list[NotificationRecord] = []

    def notify(self, status: Status, work_date: date, message: str = "") -> None:
        spec = NOTIFICATION_MATRIX.get(status)
        if spec is None:
            return

        should_dispatch = spec.is_actionable
        if status == Status.BERHASIL:
            should_dispatch = self.notify_on_success

        if not should_dispatch or not spec.title:
            return

        date_str = format_indonesian_date(work_date)
        final_message = message if message else spec.body_template.format(date_str=date_str)

        # Tegakkan guardrail privasi
        assert_privacy_compliant(final_message)

        self.notifications.append(
            NotificationRecord(
                status=status,
                work_date=work_date,
                title=spec.title,
                message=final_message,
            )
        )

    def clear(self) -> None:
        """Hapus riwayat notifikasi."""
        self.notifications.clear()


def get_notifier(fake: bool = False, notify_on_success: bool = False) -> Notifier:
    """Mengembalikan instans Notifier (FakeNotifier atau WindowsToastNotifier)."""
    if fake:
        return FakeNotifier(notify_on_success=notify_on_success)
    return WindowsToastNotifier(notify_on_success=notify_on_success)


def send_system_notification(
    title: str,
    message: str,
    channels: Sequence[str] | None = None,
) -> bool:
    """Fungsi pembantu kompatibilitas mundur untuk mengirim notifikasi sistem fail-safe."""
    logger.warning("NOTIFIKASI: [%s] %s", title, message)
    active_channels = list(channels or ["toast"])
    if "toast" in active_channels:
        try:
            assert_privacy_compliant(message)
            backend = PowerShellToastBackend()
            return backend.show_toast(title, message)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toast opsional gagal: %s", exc)
    return True
