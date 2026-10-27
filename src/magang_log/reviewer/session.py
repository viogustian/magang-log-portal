"""Modul interaktif sesi peninjauan terminal (ReviewSession) dan kontrak ApprovedEntry."""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from magang_log.drafter.models import LogEntryDraft
from magang_log.models import ApprovedEntry, EntryRecord, EvidenceItem, NoteRecord, Status
from magang_log.pipeline import ArtifactStore
from magang_log.store import LedgerStore
from magang_log.validator.engine import MultiStageValidator
from magang_log.validator.models import ValidationReport

logger = logging.getLogger(__name__)


def _extract_text(val: Any) -> str:
    """Mengekstrak dan menormalisasi teks gabungan dari draft, entry, dict, atau string."""
    if isinstance(val, (ApprovedEntry, LogEntryDraft)):
        return f"{val.aktivitas.strip()}\n{val.pembelajaran.strip()}\n{val.kendala.strip()}"
    if isinstance(val, dict):
        akt = val.get("aktivitas", "").strip()
        pemb = val.get("pembelajaran", "").strip()
        kend = val.get("kendala", "").strip()
        return f"{akt}\n{pemb}\n{kend}"
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict) and "aktivitas" in parsed:
                return _extract_text(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        return val.strip()
    return str(val).strip()


def compute_edit_ratio(draft: Any, approved: Any) -> float:
    """Menghitung edit_ratio antara teks draf awal dan teks yang disetujui.

    Formula: 1.0 - difflib.SequenceMatcher(None, draft_text, approved_text).ratio()
    Nilai 0.0 berarti disetujui tanpa perubahan; mendekati 1.0 berarti perubahan drastis.
    """
    draft_text = _extract_text(draft)
    approved_text = _extract_text(approved)
    if not draft_text and not approved_text:
        return 0.0
    ratio = difflib.SequenceMatcher(None, draft_text, approved_text).ratio()
    return round(1.0 - ratio, 4)


def compute_content_hash(text: Any) -> str:
    """Menghitung SHA-256 hexdigest dari konten teks gabungan."""
    norm = _extract_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def parse_editor_text(raw_text: str) -> tuple[str, str, str]:
    """Mem-parsing teks dari editor yang dipisahkan oleh header seksi markdown."""
    sections: dict[str, list[str]] = {"aktivitas": [], "pembelajaran": [], "kendala": []}
    current_section: str | None = None

    for line in raw_text.splitlines():
        trimmed = line.strip()
        lower = trimmed.lower()
        if lower.startswith("#") and "aktivitas" in lower:
            current_section = "aktivitas"
            continue
        elif lower.startswith("#") and "pembelajaran" in lower:
            current_section = "pembelajaran"
            continue
        elif lower.startswith("#") and "kendala" in lower:
            current_section = "kendala"
            continue

        if current_section:
            sections[current_section].append(line)
        elif trimmed and current_section is None:
            # Fallback jika ada teks sebelum header pertama
            current_section = "aktivitas"
            sections["aktivitas"].append(line)

    aktivitas = "\n".join(sections["aktivitas"]).strip()
    pembelajaran = "\n".join(sections["pembelajaran"]).strip()
    kendala = "\n".join(sections["kendala"]).strip()
    return aktivitas, pembelajaran, kendala


def format_prefill_editor(draft: LogEntryDraft | ApprovedEntry | dict[str, Any]) -> str:
    """Menyusun teks awal draf berformat markdown untuk dibuka di $EDITOR."""
    if isinstance(draft, (LogEntryDraft, ApprovedEntry)):
        akt = draft.aktivitas.strip()
        pemb = draft.pembelajaran.strip()
        kend = draft.kendala.strip()
    elif isinstance(draft, dict):
        akt = draft.get("aktivitas", "").strip()
        pemb = draft.get("pembelajaran", "").strip()
        kend = draft.get("kendala", "").strip()
    else:
        akt = str(draft).strip()
        pemb = ""
        kend = ""

    return f"### AKTIVITAS\n{akt}\n\n### PEMBELAJARAN\n{pemb}\n\n### KENDALA\n{kend}\n"


class ReviewSession:
    """Sesi interaktif peninjauan draf logbook terminal (human-in-the-loop)."""

    def __init__(
        self,
        store: LedgerStore | None = None,
        artifact_store: ArtifactStore | None = None,
        validator: MultiStageValidator | None = None,
        drafter_stage: Any | None = None,
        input_func: Callable[[str], str] | None = None,
        print_func: Callable[..., None] | None = None,
        editor_launcher: Callable[[str], str] | None = None,
    ) -> None:
        self.store = store
        self.artifact_store = artifact_store
        self.validator = validator or MultiStageValidator()
        self.drafter_stage = drafter_stage
        self._input = input_func or input
        self._print = print_func or print
        self._editor_launcher = editor_launcher or self._default_editor_launcher

    def _default_editor_launcher(self, text: str) -> str:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            editor = "notepad" if sys.platform == "win32" else "vi"

        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".md", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(text)
            temp_path = Path(tf.name)

        try:
            cmd = shlex.split(editor, posix=(sys.platform != "win32")) + [str(temp_path)]
            subprocess.run(cmd, check=True)
            return temp_path.read_text(encoding="utf-8")
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def format_review_display(
        self,
        target_date: date,
        draft: LogEntryDraft,
        validation: ValidationReport | None = None,
        evidence: Sequence[EvidenceItem] | None = None,
    ) -> str:
        """Membuat representasi string terstruktur dari draf, bukti, dan diagnostik validasi."""
        lines: list[str] = [
            "=" * 60,
            f"LOGBOOK DRAFT REVIEW: {target_date.isoformat()}",
            "=" * 60,
            f"\n--- AKTIVITAS ({len(draft.aktivitas.strip())} karakter) ---",
            draft.aktivitas.strip(),
            f"\n--- PEMBELAJARAN ({len(draft.pembelajaran.strip())} karakter) ---",
            draft.pembelajaran.strip(),
            f"\n--- KENDALA ({len(draft.kendala.strip())} karakter) ---",
            draft.kendala.strip(),
        ]

        if evidence:
            lines.extend(
                [
                    "\n" + "-" * 60,
                    f"BUKTI PENDUKUNG ({len(evidence)} butir):",
                ]
            )
            for item in evidence[:10]:
                title = (
                    getattr(item, "description", None) or getattr(item, "title", None) or item.id
                )
                lines.append(f"  • [{item.source}] {title}")
            if len(evidence) > 10:
                lines.append(f"  ... dan {len(evidence) - 10} butir bukti lainnya.")

        if draft.evidence_refs:
            lines.append("\nSITASI BUKTI DRAF:")
            for field_name, refs in draft.evidence_refs.items():
                if refs:
                    lines.append(f"  • {field_name}: {', '.join(refs)}")

        if validation:
            status_str = "LOLOS (VALID)" if validation.is_valid else "TIDAK LOLOS (INVALID)"
            lines.extend(
                [
                    "\n" + "-" * 60,
                    f"METRIK VALIDASI: {status_str}",
                    f"  • Grounding Score : {validation.grounding_score:.0%}",
                ]
            )
            if validation.errors:
                lines.append("  • Errors:")
                for err in validation.errors:
                    lines.append(f"      - {err}")
            if validation.warnings:
                lines.append("  • Warnings:")
                for warn in validation.warnings:
                    lines.append(f"      - {warn}")
            if validation.detected_filler:
                lines.append("  • Filler Terdeteksi:")
                for filler in validation.detected_filler:
                    lines.append(f"      - '{filler}'")

        lines.append("=" * 60)
        return "\n".join(lines)

    def review(
        self,
        target_date: date,
        draft: LogEntryDraft | dict[str, Any] | str,
        validation: ValidationReport | None = None,
        evidence: Sequence[EvidenceItem] | None = None,
        notes: Sequence[NoteRecord] | None = None,
    ) -> ApprovedEntry | None:
        """Menjalankan loop interaktif peninjauan draf logbook terminal."""
        if isinstance(draft, str):
            try:
                data = json.loads(draft)
                if isinstance(data, dict):
                    if "work_date" not in data:
                        data["work_date"] = target_date.isoformat()
                    cur_draft = LogEntryDraft.model_validate(data)
                else:
                    cur_draft = LogEntryDraft(
                        work_date=target_date,
                        aktivitas=draft,
                        pembelajaran="",
                        kendala="",
                    )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                cur_draft = LogEntryDraft(
                    work_date=target_date,
                    aktivitas=draft,
                    pembelajaran="",
                    kendala="",
                )
        elif isinstance(draft, dict):
            if "work_date" not in draft:
                draft["work_date"] = target_date.isoformat()
            cur_draft = LogEntryDraft.model_validate(draft)
        else:
            cur_draft = draft

        orig_draft = cur_draft
        cur_validation = validation
        if cur_validation is None:
            cur_validation = self.validator.validate(cur_draft, evidence or [])

        while True:
            display_text = self.format_review_display(
                target_date, cur_draft, cur_validation, evidence
            )
            self._print(display_text)

            self._print("\nPilihan tindakan:")
            self._print("  [Y] Approve       - Setujui draf apa adanya dan simpan ApprovedEntry")
            self._print("  [E] Edit          - Buka di $EDITOR dan validasi ulang setelah disimpan")
            self._print("  [R] Regenerate    - Buat ulang draf dengan AI Drafter")
            self._print("  [S] Skip/Postpone - Tunda peninjauan (keluar dengan kode 10)")

            try:
                choice = self._input("\nPilihan [Y/E/R/S]: ").strip().upper()
            except (EOFError, KeyboardInterrupt):
                self._print("\nPeninjauan dibatalkan/ditunda. Status tetap PERLU_REVIEW.")
                return None

            if choice in ("Y", "YES", "SETUJU"):
                return self._handle_approve(target_date, orig_draft, cur_draft)

            elif choice in ("E", "EDIT"):
                cur_draft, cur_validation = self._handle_edit(target_date, cur_draft, evidence)

            elif choice in ("R", "REGENERATE"):
                new_draft, new_val = self._handle_regenerate(target_date, evidence, notes)
                if new_draft is not None:
                    orig_draft = new_draft
                    cur_draft = new_draft
                    cur_validation = new_val

            elif choice in ("S", "SKIP", "POSTPONE", "TUNDA"):
                self._print(
                    f"\nPeninjauan ditunda. Status logbook {target_date.isoformat()} "
                    "tetap PERLU_REVIEW."
                )
                return None

            else:
                self._print(f"\nPilihan '{choice}' tidak dikenal. Harap masukkan Y, E, R, atau S.")

    def _handle_approve(
        self,
        target_date: date,
        original_draft: LogEntryDraft,
        current_draft: LogEntryDraft,
    ) -> ApprovedEntry:
        """Menyetujui draf, menghitung edit_ratio dan content_hash, lalu menyimpan entri."""
        draft_text = _extract_text(original_draft)
        approved_text = _extract_text(current_draft)
        edit_ratio = compute_edit_ratio(draft_text, approved_text)
        content_hash = compute_content_hash(approved_text)
        approved_at = datetime.now()

        entry = ApprovedEntry(
            work_date=target_date,
            aktivitas=current_draft.aktivitas,
            pembelajaran=current_draft.pembelajaran,
            kendala=current_draft.kendala,
            approved_at=approved_at,
            kehadiran=current_draft.kehadiran,
            edit_ratio=edit_ratio,
            content_hash=content_hash,
        )

        if self.store is not None:
            draft_json_str = (
                original_draft.model_dump_json()
                if hasattr(original_draft, "model_dump_json")
                else json.dumps(original_draft, ensure_ascii=False)
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
                prompt_version=getattr(original_draft, "prompt_version", "v1"),
                model=getattr(original_draft, "model", "gemini-2.5-flash"),
                edit_ratio=entry.edit_ratio,
                content_hash=entry.content_hash,
                portal_status=Status.PERLU_REVIEW.value,
                approved_at=entry.approved_at,
            )
            self.store.save_entry(record)

        if self.artifact_store is not None:
            self.artifact_store.save_approval(target_date, entry)

        self._print(
            f"\nLogbook {target_date.isoformat()} disetujui:\n"
            f"  • edit_ratio   : {edit_ratio:.4f}\n"
            f"  • content_hash : {content_hash}\n"
            f"  • approved_at  : {approved_at.isoformat()}"
        )
        return entry

    def _handle_edit(
        self,
        target_date: date,
        current_draft: LogEntryDraft,
        evidence: Sequence[EvidenceItem] | None,
    ) -> tuple[LogEntryDraft, ValidationReport]:
        """Membuka draf di editor, mem-parsing teks hasil edit, dan memvalidasi ulang."""
        prefill = format_prefill_editor(current_draft)
        try:
            edited_text = self._editor_launcher(prefill)
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
            self._print(f"\nGagal menjalankan editor: {exc}")
            val = self.validator.validate(current_draft, evidence or [])
            return current_draft, val

        akt, pemb, kend = parse_editor_text(edited_text)
        updated_draft = current_draft.model_copy(
            update={
                "aktivitas": akt,
                "pembelajaran": pemb,
                "kendala": kend,
            }
        )
        val = self.validator.validate(updated_draft, evidence or [])
        if not val.is_valid:
            self._print("\n[PERINGATAN: HASIL EDIT TIDAK LOLOS VALIDASI]")
            for err in val.errors:
                self._print(f"  • {err}")
        else:
            self._print("\n[Hasil edit berhasil disimpan dan lolos validasi.]")

        return updated_draft, val

    def _handle_regenerate(
        self,
        target_date: date,
        evidence: Sequence[EvidenceItem] | None,
        notes: Sequence[NoteRecord] | None,
    ) -> tuple[LogEntryDraft | None, ValidationReport | None]:
        """Memicu regenerasi draf menggunakan drafter AI."""
        if self.drafter_stage is None:
            self._print("\nDrafter stage tidak dikonfigurasi / tidak tersedia.")
            return None, None

        self._print(f"\nMeregenerasi draf AI untuk tanggal {target_date.isoformat()}...")
        try:
            artifacts_dir = getattr(self.artifact_store, "artifacts_dir", None)
            res = self.drafter_stage.draft_and_validate(
                target_date=target_date,
                evidence=evidence or [],
                notes=notes or [],
                artifacts_dir=artifacts_dir,
            )
            self._print("Regenerasi draf berhasil diselesaikan.")
            return res.draft, res.validation
        except (RuntimeError, ValueError, OSError) as exc:
            self._print(f"Regenerasi draf gagal: {exc}")
            return None, None
