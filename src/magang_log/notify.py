"""Modul notifikasi sistem (toast OS & logger) untuk event kritis pipeline."""

from __future__ import annotations

import logging
from typing import Sequence

logger = logging.getLogger(__name__)


def send_system_notification(
    title: str,
    message: str,
    channels: Sequence[str] | None = None,
) -> bool:
    """Mengirim notifikasi sistem ke saluran yang dikonfigurasi (default: log/toast).

    Selalu fail-safe dan tidak pernah melempar exception keluar.
    """
    logger.warning("NOTIFIKASI: [%s] %s", title, message)

    active_channels = list(channels or ["toast"])
    if "toast" in active_channels:
        # Coba tampilkan notifikasi toast di Windows bila library tersedia
        try:
            from win10toast import ToastNotifier  # type: ignore[import-untyped]

            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return True
        except (ImportError, OSError, Exception) as exc:  # noqa: BLE001
            logger.debug("Toast OS opsional tidak tersedia atau gagal: %s", exc)

    return True
