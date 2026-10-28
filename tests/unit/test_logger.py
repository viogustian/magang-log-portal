"""Unit tests untuk structured logging engine, exit codes, dan retention cleaner."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from magang_log.logger import (
    PrivacyViolationError,
    StructuredLogEntry,
    StructuredLogger,
    check_privacy_guard,
    clean_old_logs,
    clean_old_run_artifacts,
    format_utc_iso,
)
from magang_log.models import EXIT_CODES, Status, get_exit_code


def test_utc_iso_timestamp_format() -> None:
    dt = datetime(2026, 10, 27, 16, 30, 15, 123456, tzinfo=timezone.utc)
    ts = format_utc_iso(dt)
    assert ts == "2026-10-27T16:30:15.123Z"


def test_structured_log_entry_serialization() -> None:
    entry = StructuredLogEntry(
        ts="2026-10-27T16:30:15.123Z",
        level="INFO",
        run_id="run-20261027-163015-abcd1234",
        work_date="2026-10-27",
        stage="submit",
        status="BERHASIL",
        duration_ms=14250,
        tokens_in=100,
        tokens_out=250,
        error_code=None,
    )
    raw_json = entry.to_json()
    parsed = json.loads(raw_json)

    # Pastikan seluruh field skema ada dan sesuai tipe
    assert parsed["ts"] == "2026-10-27T16:30:15.123Z"
    assert parsed["level"] == "INFO"
    assert parsed["run_id"] == "run-20261027-163015-abcd1234"
    assert parsed["work_date"] == "2026-10-27"
    assert parsed["stage"] == "submit"
    assert parsed["status"] == "BERHASIL"
    assert parsed["duration_ms"] == 14250
    assert parsed["tokens_in"] == 100
    assert parsed["tokens_out"] == 250
    assert parsed["error_code"] is None

    # Reconstruct from json
    reconstructed = StructuredLogEntry.from_json(raw_json)
    assert reconstructed == entry


def test_logger_emits_jsonl_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "magang-log.jsonl"
    logger = StructuredLogger(log_file=log_file, auto_rotate=False)

    entry1 = logger.info(
        run_id="run-1",
        work_date=date(2026, 10, 27),
        stage="gate",
        status=Status.LIBUR,
        duration_ms=50,
    )
    entry2 = logger.warning(
        run_id="run-2",
        work_date="2026-10-28",
        stage="review",
        status=Status.PERLU_REVIEW,
        duration_ms=1200,
    )
    entry3 = logger.error(
        run_id="run-3",
        work_date="2026-10-29",
        stage="submit",
        status=Status.GAGAL,
        duration_ms=4500,
        error_code="TIMEOUT",
    )

    assert entry1.level == "INFO"
    assert entry2.level == "WARNING"
    assert entry3.level == "ERROR"

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    p1, p2, p3 = [json.loads(line) for line in lines]
    assert p1["level"] == "INFO" and p1["status"] == "LIBUR"
    assert p2["level"] == "WARNING" and p2["status"] == "PERLU_REVIEW"
    assert p3["level"] == "ERROR" and p3["error_code"] == "TIMEOUT"

    read_back = logger.read_logs()
    assert len(read_back) == 3
    assert read_back[0].run_id == "run-1"
    assert read_back[1].run_id == "run-2"
    assert read_back[2].run_id == "run-3"


def test_strict_privacy_guard_rejects_sensitive_fields() -> None:
    # Cek bahwa field terlarang memicu PrivacyViolationError pada level INFO
    forbidden_payloads = [
        {"aktivitas": "Membuat fitur autentikasi rahasia"},
        {"pembelajaran": "Belajar sistem internal perusahaan"},
        {"kendala": "Ada kendala pada server internal"},
        {"draft": {"isi": "teks laporan"}},
        {"logbook": "Laporan resmi"},
        {"evidence": ["commit hash 123", "detail pekerjaan"]},
        {"secret": "kunci_rahasia_123"},
        {"password": "password_super_aman"},
        {"token": "bearer eyJhbGciOi..."},
        {"api_key": "AIzaSy..."},
    ]

    for payload in forbidden_payloads:
        with pytest.raises(PrivacyViolationError):
            check_privacy_guard(payload, level="INFO")

    # Aman jika bukan level INFO atau payload tidak memuat field terlarang
    safe_payload = {"stage_metric": "ok", "retry_count": 2}
    check_privacy_guard(safe_payload, level="INFO")  # Tidak boleh raise


def test_logger_rejects_sensitive_extra_data_at_info(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "magang-log.jsonl"
    logger = StructuredLogger(log_file=log_file)

    with pytest.raises(PrivacyViolationError):
        logger.log_event(
            run_id="run-leak",
            work_date="2026-10-27",
            stage="draft",
            status="DRAFTED",
            extra_data={"aktivitas": "Menulis kode rahasia klien"},
            level="INFO",
        )


def test_weekly_log_rotation(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "magang-log.jsonl"
    logger = StructuredLogger(log_file=log_file, auto_rotate=False)

    # Tulis catatan untuk minggu lalu (mis. 2026-10-14, Rabu W42)
    past_dt = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    logger.emit(
        StructuredLogEntry(
            ts=format_utc_iso(past_dt),
            level="INFO",
            run_id="run-past",
            work_date="2026-10-14",
            stage="gate",
            status="BERHASIL",
        )
    )

    assert log_file.exists()

    # Sekarang kita berada di minggu berikutnya (mis. 2026-10-27, Selasa W44)
    current_dt = datetime(2026, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
    rotated_path = logger.rotate_weekly(now=current_dt)

    assert rotated_path is not None
    assert rotated_path.exists()
    assert "2026-W42" in rotated_path.name
    # File utama telah dipindah/kosong
    assert not log_file.exists()

    # Tulis entri baru di minggu sekarang
    logger.emit(
        StructuredLogEntry(
            ts=format_utc_iso(current_dt),
            level="INFO",
            run_id="run-current",
            work_date="2026-10-27",
            stage="submit",
            status="BERHASIL",
        ),
        now=current_dt,
    )

    assert log_file.exists()
    current_entries = logger.read_logs()
    assert len(current_entries) == 1
    assert current_entries[0].run_id == "run-current"

    # read_all_logs membaca baik arsip lama maupun file aktif
    all_entries = logger.read_all_logs()
    assert len(all_entries) == 2
    ids = {e.run_id for e in all_entries}
    assert ids == {"run-past", "run-current"}


def test_clean_old_run_artifacts(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Folder baru (7 hari lalu: 2026-10-20) -> harus dipertahankan
    fresh_dir = runs_dir / "2026-10-20"
    fresh_dir.mkdir()
    (fresh_dir / "draft.json").write_text("{}", encoding="utf-8")

    # 2. Folder lama (35 hari lalu: 2026-09-22) -> harus dibersihkan (> 30 hari)
    old_dir = runs_dir / "2026-09-22"
    old_dir.mkdir()
    (old_dir / "draft.json").write_text("{}", encoding="utf-8")

    # 3. File non-date lama berdasarkan st_mtime
    old_file = runs_dir / "old_trace.zip"
    old_file.write_text("binary", encoding="utf-8")
    old_mtime = (now - timedelta(days=40)).timestamp()
    import os
    os.utime(str(old_file), (old_mtime, old_mtime))

    # Jalankan cleaner
    removed = clean_old_run_artifacts(runs_dir=runs_dir, max_age_days=30, now=now)

    assert old_dir in removed
    assert old_file in removed
    assert fresh_dir not in removed

    assert not old_dir.exists()
    assert not old_file.exists()
    assert fresh_dir.exists()


def test_clean_old_logs(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)

    # File aktif: tidak boleh dihapus
    active_log = logs_dir / "magang-log.jsonl"
    active_log.write_text("{}\n", encoding="utf-8")

    # Arsip baru (20 hari lalu)
    recent_archive = logs_dir / "magang-log.2026-W41.jsonl"
    recent_archive.write_text("{}\n", encoding="utf-8")

    # Arsip sangat lama (100 hari lalu)
    old_archive = logs_dir / "magang-log.2026-W28.jsonl"
    old_archive.write_text("{}\n", encoding="utf-8")
    import os
    old_mtime = (now - timedelta(days=100)).timestamp()
    os.utime(str(old_archive), (old_mtime, old_mtime))

    removed = clean_old_logs(logs_dir=logs_dir, max_age_days=90, now=now)

    assert old_archive in removed
    assert active_log not in removed
    assert recent_archive not in removed

    assert not old_archive.exists()
    assert active_log.exists()
    assert recent_archive.exists()


def test_exit_codes_mapping() -> None:
    # 0: Clean success
    assert EXIT_CODES[Status.BERHASIL] == 0
    assert EXIT_CODES[Status.SUDAH_TERKIRIM] == 0
    assert EXIT_CODES[Status.LIBUR] == 0
    assert EXIT_CODES[Status.DRYRUN] == 0

    # 10: User action needed
    assert EXIT_CODES[Status.PERLU_REVIEW] == 10
    assert EXIT_CODES[Status.PERLU_INPUT] == 10
    assert EXIT_CODES[Status.PERLU_TINDAKAN] == 10

    # 20: Authentication needed
    assert EXIT_CODES[Status.LOGIN_DIPERLUKAN] == 20

    # 30: Validation error
    assert EXIT_CODES[Status.VALIDATION_ERROR] == 30
    assert EXIT_CODES[Status.VALIDATION_FAILED] == 30

    # 40: Portal / environment failure
    assert EXIT_CODES[Status.GAGAL] == 40
    assert EXIT_CODES[Status.TERKUNCI] == 40
    assert EXIT_CODES[Status.LOKASI_TIDAK_TERSEDIA] == 40
    assert EXIT_CODES[Status.TIDAK_DIKENAL] == 40

    # 1: Unexpected / crash
    assert EXIT_CODES[Status.CRASH] == 1


def test_get_exit_code_helper() -> None:
    assert get_exit_code(Status.BERHASIL) == 0
    assert get_exit_code("BERHASIL") == 0
    assert get_exit_code(Status.PERLU_REVIEW) == 10
    assert get_exit_code("PERLU_REVIEW") == 10
    assert get_exit_code(Status.LOGIN_DIPERLUKAN) == 20
    assert get_exit_code("LOGIN_DIPERLUKAN") == 20
    assert get_exit_code(Status.VALIDATION_ERROR) == 30
    assert get_exit_code("VALIDATION_ERROR") == 30
    assert get_exit_code(Status.GAGAL) == 40
    assert get_exit_code("GAGAL") == 40
    assert get_exit_code(Status.CRASH) == 1
    assert get_exit_code("CRASH") == 1

    # Unknown status or None fallback to 1
    assert get_exit_code("UNKNOWN_WEIRD_STATUS") == 1
    assert get_exit_code(None) == 1
