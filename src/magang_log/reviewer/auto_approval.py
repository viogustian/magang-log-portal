"""Modul engine conditional auto-approval berbasis verifikasi metrik historis."""

from __future__ import annotations

import json
import logging
import statistics
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from magang_log.drafter.models import LogEntryDraft
from magang_log.models import ApprovedEntry, EntryRecord, EvidenceItem, RunRecord, Status
from magang_log.notify import send_system_notification
from magang_log.pipeline import ArtifactStore
from magang_log.settings import AppConfig
from magang_log.store import LedgerStore
from magang_log.validator.models import ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class AutoApprovalDecision:
    """Hasil evaluasi gate persetujuan otomatis kondisional."""

    eligible: bool
    reason: str
    median_edit_ratio: float | None = None
    history_count: int = 0
    grounding_score: float = 0.0
    warnings_count: int = 0
    entry: ApprovedEntry | None = None


class ConditionalAutoApprovalEngine:
    """Mesin penilai kelayakan auto-approval berdasarkan validasi dan metrik historis."""

    def __init__(
        self,
        store: LedgerStore,
        config: AppConfig | None = None,
        artifact_store: ArtifactStore | None = None,
        min_history: int = 10,
        max_median_edit_ratio: float = 0.15,
        min_grounding_score: float = 0.8,
    ) -> None:
        self.store = store
        self.config = config
        self.artifact_store = artifact_store
        self.min_history = min_history
        self.max_median_edit_ratio = max_median_edit_ratio
        self.min_grounding_score = min_grounding_score

    def is_enabled(self) -> bool:
        """Memeriksa apakah fitur auto_if_confident aktif di konfigurasi aplikasi."""
        if self.config is None:
            return False
        return bool(
            getattr(self.config.review, "auto_if_confident", False)
            or getattr(self.config.review, "mode", "") == "auto_if_confident"
        )

    def assess(
        self,
        target_date: date,
        draft: LogEntryDraft | Any,
        validation: ValidationReport | Any,
        evidence: Sequence[EvidenceItem] | None = None,
    ) -> AutoApprovalDecision:
        """Mengevaluasi seluruh kriteria prasyarat ketat untuk auto-approval logbook."""
        # 1. Periksa apakah konfigurasi mengaktifkan auto_if_confident
        if not self.is_enabled():
            return AutoApprovalDecision(
                eligible=False,
                reason="Auto-approval dinonaktifkan di konfigurasi (review.auto_if_confident=False)",
            )

        # 2. Periksa status validasi draf: harus is_valid == True
        is_valid = bool(getattr(validation, "is_valid", False))
        errors = list(getattr(validation, "errors", []))
        if not is_valid:
            return AutoApprovalDecision(
                eligible=False,
                reason=f"Validasi draf tidak lolos: {'; '.join(errors)}",
            )

        # 3. Periksa peringatan validasi: len(warnings) harus 0
        warnings = list(getattr(validation, "warnings", []))
        if len(warnings) > 0:
            return AutoApprovalDecision(
                eligible=False,
                reason=f"Validasi draf memiliki {len(warnings)} peringatan: {'; '.join(warnings)}",
                warnings_count=len(warnings),
            )

        # 4. Periksa grounding score: harus >= min_grounding_score (0.8)
        grounding_score = float(getattr(validation, "grounding_score", 1.0))
        if grounding_score < self.min_grounding_score:
            return AutoApprovalDecision(
                eligible=False,
                reason=(
                    f"Grounding score ({grounding_score:.2f}) di bawah ambang batas minimal "
                    f"{self.min_grounding_score:.2f}"
                ),
                grounding_score=grounding_score,
            )

        # 5. Periksa jumlah riwayat entri disetujui di ledger: harus >= min_history (10)
        historical_ratios = self.store.get_historical_edit_ratios(
            limit=self.min_history,
            before_date=target_date,
        )
        history_count = len(historical_ratios)
        if history_count < self.min_history:
            return AutoApprovalDecision(
                eligible=False,
                reason=(
                    f"Riwayat entri disetujui kurang dari {self.min_history} "
                    f"(ditemukan: {history_count})"
                ),
                history_count=history_count,
                grounding_score=grounding_score,
            )

        # 6. Periksa median edit_ratio historis: harus <= max_median_edit_ratio (0.15)
        median_ratio = statistics.median(historical_ratios[: self.min_history])
        if median_ratio > self.max_median_edit_ratio:
            return AutoApprovalDecision(
                eligible=False,
                reason=(
                    f"Median edit_ratio historis ({median_ratio:.4f}) melebihi batas "
                    f"maksimal {self.max_median_edit_ratio:.2f}"
                ),
                median_edit_ratio=median_ratio,
                history_count=history_count,
                grounding_score=grounding_score,
            )

        # Seluruh kondisi terpenuhi: Buat ApprovedEntry yang disetujui otomatis
        approved_at = datetime.now(timezone.utc)
        entry = ApprovedEntry(
            work_date=target_date,
            aktivitas=draft.aktivitas,
            pembelajaran=draft.pembelajaran,
            kendala=draft.kendala,
            approved_at=approved_at,
            kehadiran=getattr(draft, "kehadiran", "Hadir"),
            edit_ratio=0.0,
        )

        # Simpan ke tabel entries SQLite
        draft_json_str = (
            draft.model_dump_json()
            if hasattr(draft, "model_dump_json")
            else json.dumps(draft, ensure_ascii=False)
        )
        approved_json_str = json.dumps(
            {
                "aktivitas": entry.aktivitas,
                "pembelajaran": entry.pembelajaran,
                "kendala": entry.kendala,
                "kehadiran": entry.kehadiran,
                "approved_at": approved_at.isoformat(),
            },
            ensure_ascii=False,
        )
        record = EntryRecord(
            work_date=target_date,
            draft_json=draft_json_str,
            approved_json=approved_json_str,
            prompt_version=getattr(draft, "prompt_version", "v1"),
            model=getattr(draft, "model", "gemini-2.5-flash"),
            edit_ratio=0.0,
            content_hash=entry.content_hash,
            portal_status=Status.PERLU_REVIEW.value,
            approved_at=approved_at,
        )
        self.store.save_entry(record)

        # Rekam audit run di tabel runs SQLite
        run_id = f"auto-approve-{target_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        self.store.record_run(
            RunRecord(
                run_id=run_id,
                work_date=target_date,
                stage="APPROVED",
                status=Status.BERHASIL,
                started_at=approved_at,
                finished_at=approved_at,
                duration_ms=0,
                error_code=None,
            )
        )

        # Simpan persetujuan ke artifak disk jika artifact_store tersedia
        if self.artifact_store is not None:
            self.artifact_store.save_approval(target_date, entry)

        # Kirim notifikasi sistem langsung kepada pengguna
        channels = (
            getattr(self.config.notify, "channels", ["toast"])
            if self.config is not None
            else ["toast"]
        )
        send_system_notification(
            title="Magang Log - Auto-Approved",
            message=(
                f"Draf logbook {target_date.isoformat()} disetujui otomatis "
                f"(grounding: {grounding_score:.0%}, median edit_ratio: {median_ratio:.2f})."
            ),
            channels=channels,
        )

        logger.info(
            "Auto-approval berhasil untuk %s (median edit_ratio: %.4f, grounding: %.2f)",
            target_date.isoformat(),
            median_ratio,
            grounding_score,
        )

        return AutoApprovalDecision(
            eligible=True,
            reason="Semua kriteria auto-approval terpenuhi secara otomatis",
            median_edit_ratio=median_ratio,
            history_count=history_count,
            grounding_score=grounding_score,
            warnings_count=0,
            entry=entry,
        )

    evaluate = assess
