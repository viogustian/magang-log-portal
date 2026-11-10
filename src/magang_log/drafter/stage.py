"""Stage pembuatan draf dengan koordinasi validasi dan self-correcting feedback retry loop."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from magang_log.collectors.base import Evidence
from magang_log.drafter.engine import EvidenceDrafter
from magang_log.drafter.models import LogEntryDraft
from magang_log.models import EvidenceItem, NoteRecord, Status
from magang_log.validator.engine import MultiStageValidator
from magang_log.validator.models import ValidationReport

if TYPE_CHECKING:
    from magang_log.pipeline import PipelineState

logger = logging.getLogger(__name__)


def build_feedback_prompt(
    draft: LogEntryDraft,
    report: ValidationReport,
    attempt: int,
) -> str:
    """Membangun prompt umpan balik terstruktur dengan diagnostik error spesifik untuk perbaikan draf."""
    diagnostics = "\n".join(f"- {err}" for err in report.errors)

    filler_info = ""
    if report.detected_filler:
        fillers = ", ".join(f"'{f}'" for f in report.detected_filler)
        filler_info = (
            f"\n\nPERINGATAN KERAS: Terdeteksi frasa klise/filler: {fillers}.\n"
            "DILARANG KERAS menggunakan frasa pengisi atau boilerplate tersebut!"
        )

    warning_info = ""
    if report.warnings:
        warning_info = "\nCatatan peringatan kualitas:\n" + "\n".join(
            f"- {w}" for w in report.warnings
        )

    prompt = (
        f"PERHATIAN: Draf logbook sebelumnya (percobaan {attempt}) GAGAL VALIDASI otomatis "
        "karena melanggar aturan portal MagangHub dengan diagnostik error berikut:\n"
        f"{diagnostics}"
        f"{filler_info}"
        f"{warning_info}\n\n"
        "Teks draf sebelumnya yang perlu Anda perbaiki secara menyeluruh:\n"
        f"--- AKTIVITAS ({len(draft.aktivitas.strip())} karakter) ---\n{draft.aktivitas}\n"
        f"--- PEMBELAJARAN ({len(draft.pembelajaran.strip())} karakter) ---\n{draft.pembelajaran}\n"
        f"--- KENDALA ({len(draft.kendala.strip())} karakter) ---\n{draft.kendala}\n\n"
        "INSTRUKSI PERBAIKAN WAJIB (SELF-CORRECTION):\n"
        "1. Pastikan setiap kolom (aktivitas, pembelajaran, kendala) memenuhi batas minimal 100 karakter "
        "dan maksimal 5000 karakter.\n"
        "2. JANGAN PERNAH menambahkan teks pengisi klise atau boilerplate buatan ('berjalan lancar tanpa kendala', "
        "dsb). Terangkan rincian teknis pekerjaan nyata secara lebih terperinci.\n"
        "3. HAPUS semua format markdown (code block ```, backtick `, bullet point * - + •), URL mentah, email, "
        "dan tag HTML.\n"
        "4. Pastikan klaim kegiatan tetap mencantumkan ID bukti yang valid pada evidence_refs.\n"
        "5. Kembalikan perbaikan dalam format JSON terstruktur yang valid sesuai skema LogEntryDraft."
    )
    return prompt


@dataclass
class DraftingStageResult:
    """Hasil eksekusi tahap penyusunan draf terkoordinasi validasi."""

    draft: LogEntryDraft
    validation: ValidationReport
    status: Status
    final_state: PipelineState
    exit_code: int
    attempts: int
    retries_used: int
    is_valid: bool
    feedback_history: list[str] = field(default_factory=list)
    artifacts: dict[str, Path] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0


class DraftingStage:
    """Stage yang mengoordinasikan pembuatan draf AI dan validasi multi-tahap dengan retry umpan balik."""

    def __init__(
        self,
        drafter: EvidenceDrafter,
        validator: MultiStageValidator | None = None,
        max_retries: int = 2,
    ) -> None:
        self.drafter = drafter
        self.validator = validator or MultiStageValidator()
        self.max_retries = max_retries

    def draft_and_validate(
        self,
        target_date: date,
        evidence: Sequence[Evidence | EvidenceItem],
        notes: Sequence[NoteRecord] | None = None,
        artifacts_dir: Path | None = None,
    ) -> DraftingStageResult:
        """Menjalankan loop penyusunan draf dan validasi mandiri hingga maksimum retries."""
        from magang_log.pipeline import PipelineState

        date_dir: Path | None = None
        if artifacts_dir:
            date_dir = artifacts_dir / target_date.isoformat()
            date_dir.mkdir(parents=True, exist_ok=True)

        artifacts: dict[str, Path] = {}
        feedback_history: list[str] = []
        feedback: str | None = None
        draft: LogEntryDraft | None = None
        report: ValidationReport | None = None
        attempts = 0

        # Loop percobaan: Percobaan awal (1) + maksimum 2 kali retry umpan balik
        for attempt_num in range(1, self.max_retries + 2):
            attempts += 1
            logger.info(
                "Menjalankan penyusunan draf logbook (percobaan %d/%d)",
                attempt_num,
                self.max_retries + 1,
            )

            # 1. Panggil drafter AI dengan umpan balik bila ada
            draft = self.drafter.draft(
                target_date=target_date,
                evidence=evidence,
                notes=notes,
                feedback=feedback,
            )

            # 2. Validasi deterministik multi-tahap
            report = self.validator.validate(draft, evidence)

            # 3. Simpan artifak sementara per percobaan untuk audit dan debugging
            if date_dir:
                draft_path = date_dir / f"draft_attempt_{attempt_num}.json"
                draft_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
                artifacts[f"draft_attempt_{attempt_num}"] = draft_path

                rep_path = date_dir / f"validation_attempt_{attempt_num}.json"
                rep_data = {
                    "attempt": attempt_num,
                    "is_valid": report.is_valid,
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "grounding_score": report.grounding_score,
                    "detected_filler": report.detected_filler,
                }
                rep_path.write_text(
                    json.dumps(rep_data, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                artifacts[f"validation_attempt_{attempt_num}"] = rep_path

            # 4. Evaluasi kelulusan validasi
            if report.is_valid:
                logger.info("Draf berhasil divalidasi pada percobaan %d", attempt_num)
                if date_dir:
                    final_draft_path = date_dir / "draft.json"
                    final_draft_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
                    artifacts["draft"] = final_draft_path

                    final_val_path = date_dir / "validated.json"
                    final_val_path.write_text(
                        json.dumps(
                            {
                                "is_valid": True,
                                "errors": report.errors,
                                "warnings": report.warnings,
                                "grounding_score": report.grounding_score,
                                "detected_filler": report.detected_filler,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    artifacts["validation"] = final_val_path

                return DraftingStageResult(
                    draft=draft,
                    validation=report,
                    status=Status.BERHASIL,
                    final_state=PipelineState.VALIDATED,
                    exit_code=0,
                    attempts=attempts,
                    retries_used=attempts - 1,
                    is_valid=True,
                    feedback_history=feedback_history,
                    artifacts=artifacts,
                )

            # Jika belum valid dan masih tersedia jatah retry:
            if attempt_num <= self.max_retries:
                feedback = build_feedback_prompt(draft, report, attempt_num)
                feedback_history.append(feedback)
                if date_dir:
                    fb_path = date_dir / f"feedback_attempt_{attempt_num}.txt"
                    fb_path.write_text(feedback, encoding="utf-8")
                    artifacts[f"feedback_attempt_{attempt_num}"] = fb_path

        # 5. Seluruh jatah retry habis dan validasi masih gagal
        logger.warning(
            "Percobaan retry habis (%d kali). Menghentikan eksekusi ke PERLU_REVIEW", attempts
        )
        assert draft is not None
        assert report is not None

        # PENTING: Draf tidak pernah disuntik atau di-pad dengan kalimat filler otomatis
        if date_dir:
            failed_draft_path = date_dir / "failed_draft.json"
            failed_draft_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
            artifacts["failed_draft"] = failed_draft_path

            val_rep_path = date_dir / "validation_report.json"
            val_data = {
                "status": "PERLU_REVIEW",
                "exit_code": 10,
                "attempts": attempts,
                "is_valid": False,
                "errors": report.errors,
                "warnings": report.warnings,
                "grounding_score": report.grounding_score,
                "detected_filler": report.detected_filler,
            }
            val_rep_path.write_text(
                json.dumps(val_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            artifacts["validation_report"] = val_rep_path

        return DraftingStageResult(
            draft=draft,
            validation=report,
            status=Status.PERLU_REVIEW,
            final_state=PipelineState.PERLU_REVIEW,
            exit_code=10,
            attempts=attempts,
            retries_used=attempts - 1,
            is_valid=False,
            feedback_history=feedback_history,
            artifacts=artifacts,
        )
