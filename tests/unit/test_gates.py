from datetime import date
from pathlib import Path

from magang_log.gates import (
    CalendarGate,
    GateDecision,
    GateResult,
    HolidayProvider,
    load_holidays,
)
from magang_log.models import EXIT_CODES, Status


def test_holiday_provider_from_yaml(tmp_path: Path) -> None:
    holidays_file = tmp_path / "holidays.yaml"
    holidays_file.write_text(
        """
national_holidays:
  "2026-08-17": "Hari Kemerdekaan RI"
  "2026-12-25": "Hari Natal"
personal_holidays:
  "2026-10-24": "Cuti Pribadi"
""",
        encoding="utf-8",
    )

    provider = load_holidays(holidays_file)
    assert provider.is_holiday(date(2026, 8, 17)) == (True, "Hari Kemerdekaan RI")
    assert provider.is_holiday(date(2026, 10, 24)) == (True, "Cuti Pribadi")
    assert provider.is_holiday(date(2026, 10, 27)) == (False, None)


def test_holiday_provider_with_runtime_overrides() -> None:
    provider = HolidayProvider(
        national_holidays={date(2026, 8, 17): "Hari Kemerdekaan RI"},
        personal_holidays={date(2026, 11, 2): "Izin Khusus"},
    )
    assert provider.is_holiday(date(2026, 8, 17)) == (True, "Hari Kemerdekaan RI")
    assert provider.is_holiday(date(2026, 11, 2)) == (True, "Izin Khusus")
    assert provider.is_holiday(date(2026, 11, 3)) == (False, None)


def test_calendar_gate_workday() -> None:
    provider = HolidayProvider(
        national_holidays={date(2026, 8, 17): "Hari Kemerdekaan RI"},
    )
    gate = CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"], holidays=provider)

    # 2026-10-27 adalah hari Selasa (hari kerja)
    d = date(2026, 10, 27)
    assert gate.evaluate(d) == GateDecision.WORKDAY

    result = gate.inspect(d)
    assert isinstance(result, GateResult)
    assert result.decision == GateDecision.WORKDAY
    assert result.is_workday is True
    assert "Hari kerja" in result.reason


def test_calendar_gate_weekend() -> None:
    gate = CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"])

    # 2026-10-24 adalah hari Sabtu
    d_sat = date(2026, 10, 24)
    assert gate.evaluate(d_sat) == GateDecision.LIBUR
    res_sat = gate.inspect(d_sat)
    assert res_sat.decision == GateDecision.LIBUR
    assert res_sat.is_workday is False
    assert "Sabtu" in res_sat.reason

    # 2026-10-25 adalah hari Minggu
    d_sun = date(2026, 10, 25)
    assert gate.evaluate(d_sun) == GateDecision.LIBUR
    res_sun = gate.inspect(d_sun)
    assert res_sun.decision == GateDecision.LIBUR
    assert res_sun.is_workday is False
    assert "Minggu" in res_sun.reason


def test_calendar_gate_national_holiday() -> None:
    provider = HolidayProvider(
        national_holidays={date(2026, 8, 17): "Hari Kemerdekaan RI"},
    )
    gate = CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"], holidays=provider)

    # 2026-08-17 adalah hari Senin, tapi hari libur nasional
    d = date(2026, 8, 17)
    assert gate.evaluate(d) == GateDecision.LIBUR
    result = gate.inspect(d)
    assert result.decision == GateDecision.LIBUR
    assert result.is_workday is False
    assert "Hari Kemerdekaan RI" in result.reason


def test_calendar_gate_personal_override() -> None:
    provider = HolidayProvider(
        personal_holidays={date(2026, 10, 28): "Cuti Tahunan Pribadi"},
    )
    gate = CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"], holidays=provider)

    # 2026-10-28 adalah hari Rabu
    d = date(2026, 10, 28)
    assert gate.evaluate(d) == GateDecision.LIBUR
    result = gate.inspect(d)
    assert result.decision == GateDecision.LIBUR
    assert result.is_workday is False
    assert "Cuti Tahunan Pribadi" in result.reason


def test_calendar_gate_custom_workdays() -> None:
    # Perusahaan dengan hari kerja Minggu s.d. Kamis
    gate = CalendarGate(workdays=["sun", "mon", "tue", "wed", "thu"])

    # 2026-10-25 adalah hari Minggu -> hari kerja
    assert gate.evaluate(date(2026, 10, 25)) == GateDecision.WORKDAY

    # 2026-10-30 adalah hari Jumat -> libur
    assert gate.evaluate(date(2026, 10, 30)) == GateDecision.LIBUR


def test_calendar_gate_exit_code_on_libur() -> None:
    gate = CalendarGate(workdays=["mon", "tue", "wed", "thu", "fri"])
    d_sat = date(2026, 10, 24)
    result = gate.inspect(d_sat)
    assert result.decision == GateDecision.LIBUR
    # Status LIBUR memiliki exit code 0 sesuai spesifikasi PRD dan models.py
    assert EXIT_CODES[Status.LIBUR] == 0
    assert result.exit_code == 0
