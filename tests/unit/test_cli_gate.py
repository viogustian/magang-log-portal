import json
from pathlib import Path

import pytest

from magang_log.cli import main


def test_cli_gate_workday(capsys: pytest.CaptureFixture[str]) -> None:
    # 2026-10-27 adalah hari Selasa (hari kerja)
    exit_code = main(["gate", "--date", "2026-10-27"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "WORKDAY"
    assert payload["status"] == "BERHASIL"
    assert "Hari kerja" in payload["reason"]


def test_cli_gate_weekend_libur(capsys: pytest.CaptureFixture[str]) -> None:
    # 2026-10-24 adalah hari Sabtu -> LIBUR
    exit_code = main(["gate", "--date", "2026-10-24"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "LIBUR"
    assert payload["status"] == "LIBUR"
    assert "Sabtu" in payload["reason"]


def test_cli_gate_national_holiday(capsys: pytest.CaptureFixture[str]) -> None:
    # 2026-08-17 adalah hari Senin (Hari Kemerdekaan RI)
    exit_code = main(["gate", "--date", "2026-08-17"])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "LIBUR"
    assert payload["status"] == "LIBUR"
    assert "Kemerdekaan" in payload["reason"]


def test_cli_gate_with_custom_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_file = tmp_path / "custom_config.yaml"
    config_file.write_text(
        """
workdays: [mon, tue, wed, thu]
personal_holidays:
  "2026-10-28": "Cuti Pribadi Khusus"
""",
        encoding="utf-8",
    )

    # 2026-10-30 adalah hari Jumat, yang bukan hari kerja di config custom ini
    exit_code = main(["gate", "--date", "2026-10-30", "--config", str(config_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "LIBUR"
    assert "Jumat" in payload["reason"]

    # 2026-10-28 adalah hari Rabu, hari kerja tapi ada override cuti pribadi
    exit_code = main(["gate", "--date", "2026-10-28", "--config", str(config_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "LIBUR"
    assert "Cuti Pribadi Khusus" in payload["reason"]


def test_cli_gate_with_already_submitted_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from datetime import date

    from magang_log.models import EntryRecord, Status
    from magang_log.store import LedgerStore

    db_path = tmp_path / "custom_state.db"
    store = LedgerStore(db_path=db_path)
    store.save_entry(
        EntryRecord(
            work_date=date(2026, 10, 27),
            draft_json='{"aktivitas": "Submit tested"}',
            approved_json='{"aktivitas": "Submit tested"}',
            portal_status=Status.SUDAH_TERKIRIM,
        )
    )

    # Menjalankan gate biasa pada tanggal yang sudah submit
    exit_code = main(["gate", "--date", "2026-10-27", "--db", str(db_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["decision"] == "SUDAH_TERKIRIM"
    assert payload["status"] == "SUDAH_TERKIRIM"
    assert payload["run_id"] is not None

    # Menjalankan gate dengan --force: guardrail tidak boleh menembus SUDAH_TERKIRIM
    exit_code_force = main(["gate", "--date", "2026-10-27", "--db", str(db_path), "--force"])
    assert exit_code_force == 0
    captured_force = capsys.readouterr()
    payload_force = json.loads(captured_force.out)
    assert payload_force["decision"] == "SUDAH_TERKIRIM"
    assert payload_force["status"] == "SUDAH_TERKIRIM"
