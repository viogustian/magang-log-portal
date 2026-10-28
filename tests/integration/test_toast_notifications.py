"""Integration tests untuk verifikasi pengiriman Windows Toast Notifications via PipelineCoordinator."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from magang_log.collectors.base import Evidence
from magang_log.gates import CalendarGate, HolidayProvider, PreflightGate
from magang_log.models import (
    ApprovedEntry,
    PortalResult,
    Status,
)
from magang_log.notify import FakeNotifier, assert_privacy_compliant
from magang_log.pipeline import (
    DraftResult,
    PipelineCoordinator,
    ValidationResult,
)
from magang_log.store import LedgerStore


def _setup_coordinator(
    tmp_path: Path,
    notifier: FakeNotifier,
    collector=None,
    drafter=None,
    validator=None,
    approval=None,
    portal=None,
) -> tuple[PipelineCoordinator, LedgerStore]:
    db_path = tmp_path / "state.db"
    artifacts_dir = tmp_path / "runs"
    store = LedgerStore(db_path=db_path)
    cal_gate = CalendarGate(
        holidays=HolidayProvider(national_holidays={}, personal_holidays={}),
        workdays={0, 1, 2, 3, 4},  # Senin - Jumat
    )
    preflight_gate = PreflightGate(calendar_gate=cal_gate, store=store)

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=preflight_gate,
        collector=collector,
        drafter=drafter,
        validator=validator,
        approval=approval,
        portal=portal,
        artifacts_dir=artifacts_dir,
        notifier=notifier,
    )
    return coordinator, store


def test_pipeline_holiday_silent_notifications(tmp_path: Path) -> None:
    """Status LIBUR harus sepenuhnya senyap (0 notifikasi)."""
    notifier = FakeNotifier()
    coord, _ = _setup_coordinator(tmp_path, notifier=notifier)

    # 2026-10-25 adalah hari Minggu
    res = coord.run(target_date=date(2026, 10, 25))
    assert res.status == Status.LIBUR
    assert len(notifier.notifications) == 0


def test_pipeline_perlu_input_toast_notification(tmp_path: Path) -> None:
    """Status PERLU_INPUT memicu notifikasi aksi yang sesuai dan lolos audit privasi."""
    notifier = FakeNotifier()

    mock_collector = MagicMock()
    mock_collector.collect.return_value = []  # Tanpa bukti aktivitas

    coord, _ = _setup_coordinator(
        tmp_path,
        notifier=notifier,
        collector=mock_collector,
    )

    # 2026-10-26 adalah hari Senin
    target_date = date(2026, 10, 26)
    res = coord.run(target_date=target_date)

    assert res.status == Status.PERLU_INPUT
    assert len(notifier.notifications) == 1

    rec = notifier.notifications[0]
    assert rec.status == Status.PERLU_INPUT
    assert rec.title == "Magang Logbook"
    assert rec.body == "Bukti 26 Oktober belum cukup: tambahkan catatan lewat `magang-log note`."
    assert rec.work_date == target_date

    # Memastikan tidak ada kebocoran rahasia
    assert_privacy_compliant(rec.title)
    assert_privacy_compliant(rec.body)


def test_pipeline_perlu_review_toast_notification(tmp_path: Path) -> None:
    """Status PERLU_REVIEW memicu notifikasi ajakan review tanpa membocorkan draf isi."""
    notifier = FakeNotifier()

    mock_collector = MagicMock()
    mock_collector.collect.return_value = [
        Evidence(
            source="git",
            kind="commit",
            ts=datetime(2026, 10, 27, 10, 0),
            title="Refactoring auth module",
        )
    ]

    mock_drafter = MagicMock()
    mock_drafter.draft.return_value = DraftResult(
        draft_json=json.dumps(
            {
                "aktivitas": "Sangat rahasia kode produksi internal perusahaan",
                "pembelajaran": "Memahami arsitektur internal backend",
                "kendala": "Tidak ada kendala berarti hari ini",
            }
        )
    )

    mock_validator = MagicMock()
    mock_validator.validate.return_value = ValidationResult(is_valid=True, errors=[])

    mock_approval = MagicMock()
    # Review manual belum dilakukan/mengembalikan None
    mock_approval.review_and_approve.return_value = None

    coord, _ = _setup_coordinator(
        tmp_path,
        notifier=notifier,
        collector=mock_collector,
        drafter=mock_drafter,
        validator=mock_validator,
        approval=mock_approval,
    )

    target_date = date(2026, 10, 27)
    res = coord.run(target_date=target_date)

    assert res.status == Status.PERLU_REVIEW
    assert len(notifier.notifications) == 1

    rec = notifier.notifications[0]
    assert rec.status == Status.PERLU_REVIEW
    assert rec.title == "Magang Logbook"
    assert rec.body == "Draf 27 Oktober siap ditinjau: jalankan `magang-log review`."
    assert rec.work_date == target_date

    # Guardrail privasi: draf teks TIDAK boleh ada dalam pesan notifikasi
    assert "Sangat rahasia" not in rec.body
    assert "aktivitas" not in rec.body.lower()
    assert_privacy_compliant(rec.body)


def test_pipeline_exception_dispatches_failure_toast(tmp_path: Path) -> None:
    """Unhandled exception pada pipeline memicu toast Status.GAGAL."""
    notifier = FakeNotifier()

    mock_collector = MagicMock()
    mock_collector.collect.side_effect = RuntimeError("Fatal hardware or network failure")

    coord, _ = _setup_coordinator(
        tmp_path,
        notifier=notifier,
        collector=mock_collector,
    )

    target_date = date(2026, 10, 28)
    res = coord.run(target_date=target_date)

    assert res.status == Status.GAGAL
    assert res.exit_code == 1

    assert len(notifier.notifications) == 1
    rec = notifier.notifications[0]
    assert rec.status == Status.GAGAL
    assert rec.title == "Pengiriman Gagal"
    assert rec.body == "Pengiriman 28 Oktober gagal; periksa log via `magang-log status`."
    assert_privacy_compliant(rec.body)


def test_pipeline_berhasil_toast_notification_opt_in(tmp_path: Path) -> None:
    """Status BERHASIL hanya mengirim toast jika notify_on_success=True."""
    target_date = date(2026, 10, 29)
    approved_entry = ApprovedEntry(
        work_date=target_date,
        aktivitas="Implementasi fitur logging",
        pembelajaran="Mempelajari format JSON terstruktur",
        kendala="Tidak ada kendala",
        approved_at=datetime(2026, 10, 29, 11, 0),
    )

    mock_collector = MagicMock()
    mock_collector.collect.return_value = [
        Evidence(
            source="git",
            kind="commit",
            ts=datetime(2026, 10, 29, 9, 0),
            title="Commit A",
        )
    ]
    mock_drafter = MagicMock()
    mock_drafter.draft.return_value = DraftResult(
        draft_json=json.dumps(
            {
                "aktivitas": "Implementasi fitur logging",
                "pembelajaran": "Mempelajari format JSON terstruktur",
                "kendala": "Tidak ada kendala",
            }
        )
    )
    mock_validator = MagicMock()
    mock_validator.validate.return_value = ValidationResult(is_valid=True, errors=[])

    mock_approval = MagicMock()
    mock_approval.review_and_approve.return_value = approved_entry

    mock_portal = MagicMock()
    mock_portal.submit.return_value = PortalResult(status=Status.BERHASIL, note="Success")
    mock_portal.verify_submission.return_value = True

    # Skenario 1: Default false -> senyap
    notifier_default = FakeNotifier(notify_on_success=False)
    coord1, _ = _setup_coordinator(
        tmp_path / "c1",
        notifier=notifier_default,
        collector=mock_collector,
        drafter=mock_drafter,
        validator=mock_validator,
        approval=mock_approval,
        portal=mock_portal,
    )

    res1 = coord1.run(target_date=target_date)
    assert res1.status == Status.BERHASIL
    assert len(notifier_default.notifications) == 0

    # Skenario 2: Opt-in notify_on_success=True -> kirim toast
    notifier_opt_in = FakeNotifier(notify_on_success=True)
    coord2, _ = _setup_coordinator(
        tmp_path / "c2",
        notifier=notifier_opt_in,
        collector=mock_collector,
        drafter=mock_drafter,
        validator=mock_validator,
        approval=mock_approval,
        portal=mock_portal,
    )

    res2 = coord2.run(target_date=target_date)
    assert res2.status == Status.BERHASIL
    assert len(notifier_opt_in.notifications) == 1
    rec = notifier_opt_in.notifications[0]
    assert rec.status == Status.BERHASIL
    assert rec.title == "Pengiriman Berhasil"
    assert rec.body == "Logbook 29 Oktober terkirim dan terverifikasi."
    assert_privacy_compliant(rec.body)
