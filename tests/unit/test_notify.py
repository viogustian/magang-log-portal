"""Unit tests untuk modul notifikasi desktop Windows Toast dan matriks rute notifikasi."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from magang_log.logger import PrivacyViolationError
from magang_log.models import Status
from magang_log.notify import (
    FakeNotifier,
    Notifier,
    WindowsToastNotifier,
    assert_privacy_compliant,
    format_indonesian_date,
    get_notifier,
)


def test_format_indonesian_date() -> None:
    assert format_indonesian_date(date(2026, 10, 27)) == "27 Oktober"
    assert format_indonesian_date(date(2026, 1, 1)) == "1 Januari"
    assert format_indonesian_date(date(2026, 8, 17)) == "17 Agustus"
    assert format_indonesian_date(date(2026, 12, 31)) == "31 Desember"


def test_fake_notifier_protocol_conformance() -> None:
    notifier = FakeNotifier()
    assert isinstance(notifier, Notifier)


def test_notification_matrix_actionable_statuses() -> None:
    notifier = FakeNotifier()
    test_date = date(2026, 10, 27)

    # 1. PERLU_REVIEW
    notifier.notify(Status.PERLU_REVIEW, test_date)
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].title == "Magang Logbook"
    assert (
        notifier.notifications[0].message
        == "Draf 27 Oktober siap ditinjau: jalankan `magang-log review`."
    )

    # 2. PERLU_INPUT
    notifier.clear()
    notifier.notify(Status.PERLU_INPUT, test_date)
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].title == "Magang Logbook"
    assert (
        notifier.notifications[0].message
        == "Bukti 27 Oktober belum cukup: tambahkan catatan lewat `magang-log note`."
    )

    # 3. LOGIN_DIPERLUKAN
    notifier.clear()
    notifier.notify(Status.LOGIN_DIPERLUKAN, test_date)
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].title == "Sesi MagangHub Habis"
    assert (
        notifier.notifications[0].message
        == "Sesi portal telah berakhir: jalankan `magang-log login`."
    )

    # 4. GAGAL
    notifier.clear()
    notifier.notify(Status.GAGAL, test_date)
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].title == "Pengiriman Gagal"
    assert (
        notifier.notifications[0].message
        == "Pengiriman 27 Oktober gagal; periksa log via `magang-log status`."
    )

    # 5. TERKUNCI
    notifier.clear()
    notifier.notify(Status.TERKUNCI, test_date)
    assert len(notifier.notifications) == 1
    assert notifier.notifications[0].title == "Tanggal Terkunci"
    assert (
        notifier.notifications[0].message
        == "Tanggal 27 Oktober terkunci di portal; hubungi pembimbing."
    )


def test_notification_matrix_silent_statuses() -> None:
    notifier = FakeNotifier()
    test_date = date(2026, 10, 27)

    # Status non-actionable harus sepenuhnya senyap
    notifier.notify(Status.LIBUR, test_date)
    assert len(notifier.notifications) == 0

    notifier.notify(Status.SUDAH_TERKIRIM, test_date)
    assert len(notifier.notifications) == 0

    notifier.notify(Status.DRYRUN, test_date)
    assert len(notifier.notifications) == 0


def test_berhasil_notification_optional() -> None:
    test_date = date(2026, 10, 27)

    # Default: senyap (notify_on_success=False)
    notifier_default = FakeNotifier(notify_on_success=False)
    notifier_default.notify(Status.BERHASIL, test_date)
    assert len(notifier_default.notifications) == 0

    # Opt-in: notify_on_success=True
    notifier_opt_in = FakeNotifier(notify_on_success=True)
    notifier_opt_in.notify(Status.BERHASIL, test_date)
    assert len(notifier_opt_in.notifications) == 1
    assert notifier_opt_in.notifications[0].title == "Pengiriman Berhasil"
    assert (
        notifier_opt_in.notifications[0].message
        == "Logbook 27 Oktober terkirim dan terverifikasi."
    )


def test_privacy_guardrail_enforcement() -> None:
    # Teks notifikasi tidak boleh memuat kata kunci logbook atau komit rahasia
    leaks = [
        "Aktivitas: mengerjakan modul backend",
        "Pembelajaran: belajar microservice",
        "Kendala: server database mati",
        "diff --git a/file.py",
        "commit a1b2c3d4",
        "password = 12345",
        "token = secret_token",
        "bearer eyJhbGciOi...",
    ]

    for leak in leaks:
        with pytest.raises(PrivacyViolationError):
            assert_privacy_compliant(leak)

    # Teks ringkas instruksi tindakan lolos aman
    assert_privacy_compliant("Draf 27 Oktober siap ditinjau: jalankan `magang-log review`.")
    assert_privacy_compliant("Sesi portal telah berakhir: jalankan `magang-log login`.")


def test_windows_toast_notifier_dispatches_to_backend() -> None:
    backend = MagicMock()
    backend.show_toast.return_value = True

    notifier = WindowsToastNotifier(notify_on_success=True, backend=backend)
    test_date = date(2026, 10, 27)

    # Status actionable memicu backend
    notifier.notify(Status.PERLU_REVIEW, test_date)
    backend.show_toast.assert_called_once_with(
        "Magang Logbook",
        "Draf 27 Oktober siap ditinjau: jalankan `magang-log review`.",
    )

    backend.reset_mock()
    # Status silent tidak memicu backend
    notifier.notify(Status.LIBUR, test_date)
    backend.show_toast.assert_not_called()


def test_get_notifier_factory() -> None:
    fake = get_notifier(fake=True)
    assert isinstance(fake, FakeNotifier)

    real = get_notifier(fake=False)
    assert isinstance(real, WindowsToastNotifier)
