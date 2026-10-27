"""Gatekeeper kalender & hari libur: mengevaluasi kelayakan tanggal eksekusi sebelum downstream dijalankan."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .models import EXIT_CODES, RunRecord, Status
from .settings import AppConfig, normalize_workdays
from .store import LedgerStore

INDONESIAN_DAY_NAMES = [
    "Senin",
    "Selasa",
    "Rabu",
    "Kamis",
    "Jumat",
    "Sabtu",
    "Minggu",
]


class GateDecision(StrEnum):
    """Keputusan pre-flight gate kalender & ledger."""

    WORKDAY = "WORKDAY"
    LIBUR = "LIBUR"
    SUDAH_TERKIRIM = "SUDAH_TERKIRIM"

    @property
    def is_workday(self) -> bool:
        return self in (GateDecision.WORKDAY, GateDecision.SUDAH_TERKIRIM)

    @property
    def can_proceed(self) -> bool:
        return self == GateDecision.WORKDAY


@dataclass(frozen=True)
class GateResult:
    """Hasil evaluasi mendalam oleh CalendarGate dan PreflightGate."""

    decision: GateDecision
    reason: str
    target_date: date
    run_id: str | None = None

    @property
    def is_workday(self) -> bool:
        return self.decision in (GateDecision.WORKDAY, GateDecision.SUDAH_TERKIRIM)

    @property
    def exit_code(self) -> int:
        if self.decision == GateDecision.LIBUR:
            return EXIT_CODES[Status.LIBUR]
        if self.decision == GateDecision.SUDAH_TERKIRIM:
            return EXIT_CODES[Status.SUDAH_TERKIRIM]
        return 0


def generate_run_id(target_date: date) -> str:
    """Menghasilkan run_id unik untuk setiap eksekusi pipeline."""
    unique_suffix = uuid.uuid4().hex[:8]
    now_str = datetime.now().strftime("%H%M%S")
    return f"run-{target_date.strftime('%Y%m%d')}-{now_str}-{unique_suffix}"


class HolidayProvider:
    """Penyedia daftar hari libur nasional dan override cuti / libur pribadi."""

    def __init__(
        self,
        national_holidays: dict[date, str] | None = None,
        personal_holidays: dict[date, str] | None = None,
    ) -> None:
        self.national_holidays = national_holidays or {}
        self.personal_holidays = personal_holidays or {}

    def is_national_holiday(self, d: date) -> tuple[bool, str | None]:
        """Memeriksa apakah tanggal merupakan hari libur nasional."""
        if d in self.national_holidays:
            return True, self.national_holidays[d]
        return False, None

    def is_personal_holiday(self, d: date) -> tuple[bool, str | None]:
        """Memeriksa apakah tanggal merupakan cuti atau libur pribadi."""
        if d in self.personal_holidays:
            return True, self.personal_holidays[d]
        return False, None

    def is_holiday(self, d: date) -> tuple[bool, str | None]:
        """Memeriksa apakah tanggal merupakan hari libur (pribadi didahulukan, lalu nasional)."""
        is_pers, name_pers = self.is_personal_holiday(d)
        if is_pers:
            return True, name_pers
        is_nat, name_nat = self.is_national_holiday(d)
        if is_nat:
            return True, name_nat
        return False, None


def _parse_date_dict(raw: Any) -> dict[date, str]:
    result: dict[date, str] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            d = date.fromisoformat(str(k).strip()) if not isinstance(k, date) else k
            result[d] = str(v).strip()
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "date" in item and "name" in item:
                d = (
                    date.fromisoformat(str(item["date"]).strip())
                    if not isinstance(item["date"], date)
                    else item["date"]
                )
                result[d] = str(item["name"]).strip()
    return result


def load_holidays(path: Path | str | None = None) -> HolidayProvider:
    """Memuat daftar hari libur nasional dan personal dari file YAML."""
    if path is None:
        return HolidayProvider()

    p = Path(path)
    if not p.exists():
        return HolidayProvider()

    try:
        content = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return HolidayProvider()

    national = _parse_date_dict(content.get("national_holidays"))
    personal = _parse_date_dict(content.get("personal_holidays"))
    return HolidayProvider(national_holidays=national, personal_holidays=personal)


class CalendarGate:
    """Gatekeeper pre-flight: memverifikasi hari kerja, libur nasional, dan cuti pribadi."""

    def __init__(
        self,
        workdays: list[str] | set[int] | None = None,
        holidays: HolidayProvider | None = None,
    ) -> None:
        if workdays is None:
            self._workdays = {0, 1, 2, 3, 4}  # Default Senin - Jumat
        elif isinstance(workdays, set):
            self._workdays = workdays
        else:
            self._workdays = normalize_workdays(list(workdays))

        self.holidays = holidays or HolidayProvider()

    @classmethod
    def from_config(cls, cfg: AppConfig) -> CalendarGate:
        """Membuat instance CalendarGate dari konfigurasi aplikasi."""
        provider = load_holidays(cfg.holidays_file)
        if cfg.personal_holidays:
            extra_personal = _parse_date_dict(cfg.personal_holidays)
            provider.personal_holidays.update(extra_personal)
        return cls(workdays=cfg.active_workdays(), holidays=provider)

    def evaluate(self, target_date: date) -> GateDecision:
        """Mengembalikan GateDecision (WORKDAY vs LIBUR)."""
        return self.inspect(target_date).decision

    def inspect(self, target_date: date) -> GateResult:
        """Mengevaluasi target_date secara menyeluruh dan mengembalikan GateResult dengan alasan."""
        weekday_idx = target_date.weekday()
        day_name = INDONESIAN_DAY_NAMES[weekday_idx]

        # 1. Cek apakah hari tersebut ada dalam jadwal hari kerja aktif
        if weekday_idx not in self._workdays:
            return GateResult(
                decision=GateDecision.LIBUR,
                reason=f"Bukan hari kerja aktif ({day_name})",
                target_date=target_date,
            )

        # 2. Cek libur pribadi / cuti override
        is_pers, pers_name = self.holidays.is_personal_holiday(target_date)
        if is_pers:
            return GateResult(
                decision=GateDecision.LIBUR,
                reason=f"Libur pribadi / cuti: {pers_name}",
                target_date=target_date,
            )

        # 3. Cek hari libur nasional
        is_nat, nat_name = self.holidays.is_national_holiday(target_date)
        if is_nat:
            return GateResult(
                decision=GateDecision.LIBUR,
                reason=f"Hari libur nasional: {nat_name}",
                target_date=target_date,
            )

        # 4. Tanggal lolos sebagai hari kerja aktif
        return GateResult(
            decision=GateDecision.WORKDAY,
            reason=f"Hari kerja aktif ({day_name})",
            target_date=target_date,
        )


class PreflightGate:
    """Pre-flight execution gate yang mengintegrasikan CalendarGate dan LedgerStore untuk menjamin idempotensi."""

    def __init__(self, calendar_gate: CalendarGate, store: LedgerStore) -> None:
        self.calendar_gate = calendar_gate
        self.store = store

    @classmethod
    def from_config_and_store(cls, cfg: AppConfig, store: LedgerStore) -> PreflightGate:
        calendar_gate = CalendarGate.from_config(cfg)
        return cls(calendar_gate=calendar_gate, store=store)

    def evaluate(
        self,
        target_date: date,
        content_hash: str | None = None,
        force: bool = False,
    ) -> GateDecision:
        return self.inspect(target_date, content_hash=content_hash, force=force).decision

    def inspect(
        self,
        target_date: date,
        content_hash: str | None = None,
        force: bool = False,
        run_id: str | None = None,
    ) -> GateResult:
        run_id = run_id or generate_run_id(target_date)
        start_time = datetime.now()

        # 1. Cek kalender & hari libur
        cal_res = self.calendar_gate.inspect(target_date)
        if cal_res.decision == GateDecision.LIBUR:
            finished = datetime.now()
            duration_ms = int((finished - start_time).total_seconds() * 1000)
            self.store.record_run(
                RunRecord(
                    run_id=run_id,
                    work_date=target_date,
                    stage="GATED",
                    status=Status.LIBUR,
                    started_at=start_time,
                    finished_at=finished,
                    duration_ms=duration_ms,
                )
            )
            return GateResult(
                decision=GateDecision.LIBUR,
                reason=cal_res.reason,
                target_date=target_date,
                run_id=run_id,
            )

        # 2. Cek ledger entri yang sudah ada untuk menjamin idempotensi
        entry = self.store.get_entry(target_date)
        if entry is not None:
            is_finalized = entry.portal_status in (
                Status.SUDAH_TERKIRIM,
                Status.BERHASIL,
                "SUDAH_TERKIRIM",
                "BERHASIL",
            )
            if is_finalized:
                # Guardrail: --force TIDAK BOLEH menembus entri yang sudah terkirim ke portal
                finished = datetime.now()
                duration_ms = int((finished - start_time).total_seconds() * 1000)
                reason = (
                    f"Tanggal {target_date} sudah berstatus {entry.portal_status} di ledger; "
                    "pengiriman ulang dicegah"
                )
                self.store.record_run(
                    RunRecord(
                        run_id=run_id,
                        work_date=target_date,
                        stage="GATED",
                        status=Status.SUDAH_TERKIRIM,
                        started_at=start_time,
                        finished_at=finished,
                        duration_ms=duration_ms,
                    )
                )
                return GateResult(
                    decision=GateDecision.SUDAH_TERKIRIM,
                    reason=reason,
                    target_date=target_date,
                    run_id=run_id,
                )

            # Jika belum finalized, cek apakah content_hash sama dan tidak dipaksa (--force)
            if content_hash is not None and entry.content_hash == content_hash and not force:
                finished = datetime.now()
                duration_ms = int((finished - start_time).total_seconds() * 1000)
                reason = (
                    f"Tanggal {target_date} memiliki draf dengan content_hash identik ({content_hash}); "
                    "gunakan --force jika ingin membuat ulang"
                )
                self.store.record_run(
                    RunRecord(
                        run_id=run_id,
                        work_date=target_date,
                        stage="GATED",
                        status=Status.BERHASIL,
                        started_at=start_time,
                        finished_at=finished,
                        duration_ms=duration_ms,
                    )
                )
                return GateResult(
                    decision=GateDecision.WORKDAY,
                    reason=reason,
                    target_date=target_date,
                    run_id=run_id,
                )

        # 3. Lolos gate pre-flight - catat initial run state
        finished = datetime.now()
        duration_ms = int((finished - start_time).total_seconds() * 1000)
        self.store.record_run(
            RunRecord(
                run_id=run_id,
                work_date=target_date,
                stage="GATED",
                status=Status.BERHASIL,
                started_at=start_time,
                finished_at=finished,
                duration_ms=duration_ms,
            )
        )
        return GateResult(
            decision=GateDecision.WORKDAY,
            reason=f"Layak diproses: {cal_res.reason}",
            target_date=target_date,
            run_id=run_id,
        )
