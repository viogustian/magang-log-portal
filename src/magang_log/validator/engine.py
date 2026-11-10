"""Mesin validasi deterministik multi-tahap draf entri logbook."""

from __future__ import annotations

import re
from typing import Any, Sequence

from magang_log.drafter.models import LogEntryDraft
from magang_log.validator.models import ValidationReport
from magang_log.validator.rules import (
    MAX_FIELD_LENGTH,
    MIN_FIELD_LENGTH,
    TARGET_TEXT_FIELDS,
    compute_grounding_score,
    compute_lexical_diversity,
    compute_repetition_ratio,
    detect_canned_fillers,
    detect_format_violations,
)


class MultiStageValidator:
    """Validator murni tanpa I/O untuk memeriksa kepatuhan aturan portal MagangHub."""

    def validate(
        self,
        draft: LogEntryDraft,
        evidence: Sequence[Any] | None = None,
    ) -> ValidationReport:
        """Memvalidasi LogEntryDraft terhadap aturan karakter, sanitasi, anti-filler, dan grounding.

        Args:
            draft: Draf entri logbook harian terstruktur.
            evidence: Koleksi bukti aktivitas yang telah diverifikasi (opsional).

        Returns:
            ValidationReport dengan status validitas, daftar error, warning, dan grounding score.
        """
        errors: list[str] = []
        warnings: list[str] = []
        detected_filler: list[str] = []

        # Ekstraksi ID bukti yang terverifikasi
        valid_evidence_ids: set[str] = set()
        if evidence:
            for item in evidence:
                if isinstance(item, dict):
                    item_id = item.get("id")
                else:
                    item_id = getattr(item, "id", None)
                if item_id:
                    valid_evidence_ids.add(str(item_id).strip())

        for field_name in TARGET_TEXT_FIELDS:
            val = getattr(draft, field_name, "")
            text_len = len(val.strip())

            # 1. Validasi batas panjang karakter portal (100 - 5000 karakter)
            if text_len < MIN_FIELD_LENGTH:
                errors.append(
                    f"Field '{field_name}' memiliki {text_len} karakter, kurang dari batas minimum 100 karakter."
                )
            elif text_len > MAX_FIELD_LENGTH:
                errors.append(
                    f"Field '{field_name}' memiliki {text_len} karakter, melebihi batas maksimum 5000 karakter."
                )

            # 2. Pemeriksaan sanitasi format teks (markdown, URL, email, HTML)
            format_violations = detect_format_violations(val, field_name)
            errors.extend(format_violations)

            # 3. Pemeriksaan frasa klise / canned template pengisi
            fillers, filler_errors = detect_canned_fillers(val, field_name)
            for f in fillers:
                if f not in detected_filler:
                    detected_filler.append(f)
            errors.extend(filler_errors)

            # 4. Pemeriksaan keragaman leksikal dan perulangan
            words = re.findall(r"\b\w+\b", val.lower())
            if len(words) >= 10:
                diversity = compute_lexical_diversity(val)
                if diversity < 0.4:
                    warnings.append(
                        f"Field '{field_name}' memiliki keragaman leksikal rendah ({diversity:.2f} < 0.4)."
                    )

            if len(val.strip()) >= MIN_FIELD_LENGTH:
                rep_ratio = compute_repetition_ratio(val)
                if rep_ratio > 0.3:
                    errors.append(
                        f"Field '{field_name}' terdeteksi pengulangan kalimat/n-gram berlebihan (rasio {rep_ratio:.2f} > 0.3)."
                    )

        # 5. Perhitungan skor keterhubungan bukti (Grounding Score)
        grounding_score, grounding_warnings = compute_grounding_score(
            aktivitas=draft.aktivitas,
            evidence_refs=draft.evidence_refs,
            valid_evidence_ids=valid_evidence_ids,
        )
        warnings.extend(grounding_warnings)

        is_valid = len(errors) == 0
        return ValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            grounding_score=grounding_score,
            detected_filler=detected_filler,
        )


def validate(
    draft: LogEntryDraft,
    evidence: Sequence[Any] | None = None,
) -> ValidationReport:
    """Fungsi murni untuk memvalidasi draf logbook terhadap aturan portal."""
    validator = MultiStageValidator()
    return validator.validate(draft, evidence)
