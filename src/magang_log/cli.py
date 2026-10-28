"""CLI modul portal: login | check | fill (dry-run) | submit."""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .collectors.factory import collect_and_sanitize_evidence
from .collectors.strength import build_drafting_payload, evaluate_evidence_strength
from .drafter.models import LogEntryDraft
from .exporter import export_logbook
from .gates import INDONESIAN_DAY_NAMES, GateDecision, PreflightGate
from .models import EXIT_CODES, ApprovedEntry, NoteRecord, RunRecord, Status, get_exit_code
from .notify import send_system_notification
from .pipeline import ArtifactStore, DraftResult, PipelineCoordinator, ValidationResult
from .portal import NotApproved, PlaywrightPortal, PortalConfig
from .portal import selectors as sel
from .reviewer import ReviewSession
from .settings import load_config
from .store import LedgerStore

CONFIRM_WORD = "SETUJU"


def calculate_percentile(values: list[float], percentile: float) -> float:
    """Menghitung persentil dari daftar nilai numerik dengan interpolasi linier."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = int(k)
    c = f + 1
    if c < len(sorted_values):
        d0 = sorted_values[f] * (c - k)
        d1 = sorted_values[c] * (k - f)
        return round(float(d0 + d1), 2)
    return round(float(sorted_values[-1]), 2)


def calculate_median(values: list[float]) -> float:
    """Menghitung nilai tengah (median) dari daftar nilai numerik."""
    if not values:
        return 0.0
    return round(float(statistics.median(values)), 2)



def _config(args: argparse.Namespace) -> PortalConfig:
    cfg = PortalConfig()
    if args.base_url:
        cfg.base_url = args.base_url
    cfg.auth_state = Path(args.auth_state)
    cfg.artifacts_dir = Path(args.artifacts_dir)
    cfg.headless = bool(getattr(args, "headless", False))
    cfg.channel = None if args.channel == "chromium" else args.channel
    return cfg


def _load_entry(path: Path) -> ApprovedEntry:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("aktivitas", "pembelajaran", "kendala"):
        if data[key].lstrip().upper().startswith("CONTOH"):
            sys.exit(f"Kolom '{key}' masih berisi teks CONTOH. Ganti dengan isi Anda sendiri.")
    approved_at = data.get("approved_at")
    return ApprovedEntry(
        work_date=date.fromisoformat(data["work_date"]),
        aktivitas=data["aktivitas"],
        pembelajaran=data["pembelajaran"],
        kendala=data["kendala"],
        approved_at=datetime.fromisoformat(approved_at) if approved_at else None,
        kehadiran=data.get("kehadiran", "Hadir"),
    )


def _print(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_login(args: argparse.Namespace) -> int:
    cfg = _config(args)
    from .portal.session import LoginRequired, SessionManager

    mgr = SessionManager(
        auth_state=cfg.auth_state,
        base_url=cfg.base_url,
        channel=cfg.channel,
        timeout_ms=cfg.timeout_ms,
        login_markers=cfg.login_markers,
    )
    try:
        success = mgr.interactive_login()
        return 0 if success else EXIT_CODES[Status.LOGIN_DIPERLUKAN]
    except LoginRequired as exc:
        print(f"Login tidak selesai: {exc}")
        return EXIT_CODES[Status.LOGIN_DIPERLUKAN]
    except Exception as exc:  # noqa: BLE001
        print(f"Terjadi kesalahan saat proses login ({exc.__class__.__name__}): {exc}")
        return EXIT_CODES[Status.LOGIN_DIPERLUKAN]


def cmd_check(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if args.date else date.today()
    from .portal.session import LoginRequired

    try:
        with PlaywrightPortal(_config(args)) as portal:
            report = portal.check(d)
    except LoginRequired as exc:
        report = {
            "date": d.isoformat(),
            "login": False,
            "error": f"LOGIN_DIPERLUKAN ({exc})",
        }
    _print(report)
    if "LOGIN_DIPERLUKAN" in str(report.get("error", "")):
        return EXIT_CODES[Status.LOGIN_DIPERLUKAN]
    return 0 if report.get("login") and "error" not in report else EXIT_CODES[Status.GAGAL]


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnostik kesehatan sistem lokal atau canary selector portal."""
    if getattr(args, "portal", False):
        d = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
        from .portal.session import LoginRequired

        try:
            with PlaywrightPortal(_config(args)) as portal:
                report = portal.check(d)
        except LoginRequired as exc:
            report = {
                "date": d.isoformat(),
                "login": False,
                "error": f"LOGIN_DIPERLUKAN ({exc})",
            }
        except Exception as exc:  # noqa: BLE001
            report = {
                "date": d.isoformat(),
                "login": False,
                "error": f"GAGAL ({exc})",
            }

        if getattr(args, "json", False):
            _print(report)
        else:
            print("=" * 60)
            print(f"CANARY DIAGNOSTIK KESEHATAN PORTAL ({d.isoformat()})")
            print("=" * 60)
            login_status = "TERHUBUNG (VALID)" if report.get("login") else "BELUM LOGIN / SESI HABIS"
            print(f"Status Autentikasi : {login_status}")
            if report.get("status"):
                print(f"Status Hari        : {report['status']} ({report.get('label', '')})")
            if "location" in report:
                print(f"Izin Lokasi        : {'BERHASIL' if report['location'] else 'GAGAL / DITOLAK'}")

            selectors = report.get("selectors_health", {})
            if selectors:
                print("\nSTATUS KESEHATAN SELECTOR SEMANTIK:")
                print("-" * 60)
                for key, info in selectors.items():
                    mark = "[PASS]" if info.get("healthy") else "[FAIL]"
                    desc = info.get("description", key)
                    cnt = info.get("count", 0)
                    print(f"{mark} {desc:<45}: count={cnt}")
                print("-" * 60)

            if report.get("error"):
                print(f"\nCATATAN KESALAHAN : {report['error']}")
                if "LOGIN_DIPERLUKAN" in report["error"]:
                    print("PANDUAN PERBAIKAN : Jalankan 'magang-portal login' untuk login ulang.")
                else:
                    print(
                        "PANDUAN PERBAIKAN : Perbarui src/magang_log/portal/selectors.py sesuai snapshot DOM portal."
                    )

            all_ok = (
                report.get("login")
                and report.get("all_selectors_healthy", True)
                and not report.get("error")
            )
            print(
                "\nHASIL KESELURUHAN  : "
                + ("SEMUA SEHAT & SIAP SUBMIT" if all_ok else "PERLU TINDAKAN")
            )
            print("=" * 60)

        if "LOGIN_DIPERLUKAN" in str(report.get("error", "")):
            return EXIT_CODES[Status.LOGIN_DIPERLUKAN]
        return (
            0
            if report.get("login")
            and "error" not in report
            and report.get("all_selectors_healthy", True)
            else EXIT_CODES[Status.GAGAL]
        )

    # Mode default: System Health Doctor Subsystem
    from .doctor import Doctor, get_default_health_checks

    config_path = getattr(args, "config", None)
    doctor = Doctor(get_default_health_checks(config_path=config_path))
    doc_report = doctor.run_checks()

    if getattr(args, "json", False):
        _print(doc_report.to_dict())
    else:
        print(doc_report.format_terminal())

    return doc_report.exit_code


def cmd_gate(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if args.date else date.today()
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)
    gate = PreflightGate.from_config_and_store(cfg, store)
    result = gate.inspect(
        d,
        content_hash=getattr(args, "content_hash", None),
        force=bool(getattr(args, "force", False)),
    )

    if result.decision == GateDecision.LIBUR:
        status_label = Status.LIBUR
    elif result.decision == GateDecision.SUDAH_TERKIRIM:
        status_label = Status.SUDAH_TERKIRIM
    else:
        status_label = Status.BERHASIL

    payload = {
        "status": status_label,
        "decision": result.decision,
        "reason": result.reason,
        "date": d.isoformat(),
        "run_id": result.run_id,
    }
    _print(payload)
    return result.exit_code


def cmd_fill(args: argparse.Namespace) -> int:
    entry = _load_entry(Path(args.entry))
    with PlaywrightPortal(_config(args)) as portal:
        result = portal.fill(entry)
    _print(
        {
            "status": result.status,
            "note": result.note,
            "screenshots": result.screenshots,
            "traces": result.traces,
        }
    )
    return EXIT_CODES[result.status]


def _confirm_interactively(entry: ApprovedEntry) -> ApprovedEntry | None:
    print(f"\n=== Logbook {entry.work_date.isoformat()} ===")
    for key, label in sel.FIELD_LABELS.items():
        print(f"\n{label}:\n{getattr(entry, key).strip()}")
    print(
        f'\nKetik "{CONFIRM_WORD}" untuk menyatakan Anda telah meninjau dan memastikan isian ini benar.'
    )
    if input("> ").strip() != CONFIRM_WORD:
        print("Dibatalkan: tidak ada yang dikirim.")
        return None
    return replace(entry, approved_at=datetime.now())


def cmd_submit(args: argparse.Namespace) -> int:
    dry_run = getattr(args, "dry_run", False)
    entry_path = getattr(args, "entry", None)

    if entry_path:
        entry = _load_entry(Path(entry_path))
    else:
        d = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
        db_path = getattr(args, "db", None) or "data/state.db"
        store = LedgerStore(db_path=db_path)
        entry_rec = store.get_entry(d)
        if not entry_rec or not entry_rec.approved_json:
            print(
                f"Tidak ditemukan entri yang disetujui untuk tanggal {d.isoformat()}.",
                file=sys.stderr,
            )
            print(
                "Pastikan draf sudah disetujui lewat 'magang-log review' sebelum submit.",
                file=sys.stderr,
            )
            return EXIT_CODES[Status.PERLU_TINDAKAN]
        try:
            data = json.loads(entry_rec.approved_json)
            entry = ApprovedEntry(
                work_date=d,
                aktivitas=data.get("aktivitas", ""),
                pembelajaran=data.get("pembelajaran", ""),
                kendala=data.get("kendala", ""),
                approved_at=entry_rec.approved_at or datetime.now(),
                kehadiran=data.get("kehadiran", "Hadir"),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Gagal memuat entri yang disetujui dari ledger: {exc}", file=sys.stderr)
            return EXIT_CODES[Status.PERLU_TINDAKAN]

    if not dry_run and entry.approved_at is None:
        if not sys.stdin.isatty():
            print("Entri belum disetujui (approved_at kosong) dan tidak ada terminal interaktif.")
            return EXIT_CODES[Status.PERLU_TINDAKAN]
        confirmed = _confirm_interactively(entry)
        if confirmed is None:
            return EXIT_CODES[Status.PERLU_TINDAKAN]
        entry = confirmed
    try:
        with PlaywrightPortal(_config(args)) as portal:
            result = portal.submit(entry, dry_run=dry_run)
    except NotApproved as exc:
        print(exc)
        return EXIT_CODES[Status.PERLU_TINDAKAN]
    _print(
        {
            "status": result.status,
            "note": result.note,
            "screenshots": result.screenshots,
            "traces": result.traces,
        }
    )
    return EXIT_CODES[result.status]



class CliApprovalStage:
    """Implementasi peninjauan dan persetujuan draf untuk CLI."""

    def __init__(self, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve

    def review_and_approve(
        self,
        target_date: date,
        draft: DraftResult,
        validation: ValidationResult,
    ) -> ApprovedEntry | None:
        try:
            parsed = json.loads(draft.draft_json)
            aktivitas = parsed.get("aktivitas", "")
            pembelajaran = parsed.get("pembelajaran", "")
            kendala = parsed.get("kendala", "")
        except (json.JSONDecodeError, TypeError):
            aktivitas = draft.draft_json
            pembelajaran = ""
            kendala = ""

        candidate = ApprovedEntry(
            work_date=target_date,
            aktivitas=aktivitas,
            pembelajaran=pembelajaran,
            kendala=kendala,
            approved_at=datetime.now() if self.auto_approve else None,
        )

        if self.auto_approve:
            return candidate

        if not sys.stdin.isatty():
            print(
                "Draf belum disetujui dan tidak ada terminal interaktif. Menunda persetujuan (PERLU_REVIEW).",
                file=sys.stderr,
            )
            return None

        return _confirm_interactively(candidate)


def cmd_run(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if args.date else date.today()
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)
    gate = PreflightGate.from_config_and_store(cfg, store)

    portal = None
    dry_run = bool(getattr(args, "dry_run", False))
    auth_state_path = Path(args.auth_state)
    if auth_state_path.exists():
        try:
            portal = PlaywrightPortal(_config(args))
        except Exception:  # noqa: BLE001
            portal = None

    auto_approve = bool(getattr(args, "auto_approve", False))
    approval = CliApprovalStage(auto_approve=auto_approve)

    auto_approval_engine = None
    if (
        getattr(cfg.review, "auto_if_confident", False)
        or getattr(cfg.review, "mode", "") == "auto_if_confident"
    ):
        from .reviewer import ConditionalAutoApprovalEngine

        auto_approval_engine = ConditionalAutoApprovalEngine(
            store=store,
            config=cfg,
            artifact_store=ArtifactStore(Path(getattr(args, "artifacts_dir", "data/runs"))),
        )

    notifier = None
    if "toast" in getattr(cfg.notify, "channels", ["toast"]):
        from .notify import WindowsToastNotifier

        notify_on_success = bool(getattr(cfg.notify, "notify_on_success", False))
        notifier = WindowsToastNotifier(notify_on_success=notify_on_success)

    drafter_stage = None
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and "PYTEST_CURRENT_TEST" not in os.environ:
        from .drafter import DraftingStage, EvidenceDrafter, GeminiModelClient
        from .validator import MultiStageValidator

        client = GeminiModelClient(
            api_key=api_key,
            model=getattr(cfg.llm, "model", "gemini-3.5-flash"),
            temperature=getattr(cfg.llm, "temperature", 0.2),
        )
        evidence_drafter = EvidenceDrafter(
            model_client=client,
            model_name=getattr(cfg.llm, "model", "gemini-3.5-flash"),
        )
        drafter_stage = DraftingStage(
            drafter=evidence_drafter,
            validator=MultiStageValidator(),
        )

    class CliCollectorStage:
        def __init__(self, config: Any, store: LedgerStore) -> None:
            self.config = config
            self.store = store

        def collect(self, target_date: date) -> list[EvidenceItem]:
            from .collectors.factory import collect_and_sanitize_evidence
            from .models import EvidenceItem

            sanitized = collect_and_sanitize_evidence(target_date, self.config, self.store)
            items: list[EvidenceItem] = []
            for e in sanitized:
                items.append(
                    EvidenceItem(
                        id=e.id,
                        work_date=target_date,
                        source=e.source,
                        kind=e.kind,
                        ts=e.ts,
                        title=e.title,
                        detail=e.detail,
                        strength=e.strength,
                    )
                )
            return items

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=gate,
        collector=CliCollectorStage(cfg, store),
        drafter=drafter_stage,
        portal=portal,
        approval=approval,
        artifacts_dir=Path(getattr(args, "artifacts_dir", "data/runs")),
        auto_approval_engine=auto_approval_engine,
        notifier=notifier,
    )

    resume_flag = bool(getattr(args, "resume", False)) or (
        getattr(args, "mode", None) == "resume"
    )

    result = coordinator.run(
        target_date=d,
        dry_run=dry_run,
        resume=resume_flag,
        force=bool(getattr(args, "force", False)),
    )

    payload = {
        "run_id": result.run_id,
        "date": result.target_date.isoformat(),
        "state": result.final_state.value,
        "status": result.status.value,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "note": result.note,
        "error_code": result.error_code,
    }
    _print(payload)

    if getattr(args, "mode", None) == "review" and result.status == Status.PERLU_REVIEW:
        review_args = argparse.Namespace(**vars(args))
        return cmd_review(review_args)

    return result.exit_code



def cmd_export(args: argparse.Namespace) -> int:
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)
    from_date = date.fromisoformat(args.from_date) if getattr(args, "from_date", None) else None
    to_date = date.fromisoformat(args.to_date) if getattr(args, "to_date", None) else None
    output_path = getattr(args, "output", None) or "logbook.md"

    out_file, count = export_logbook(
        store=store,
        output_path=output_path,
        from_date=from_date,
        to_date=to_date,
    )

    payload = {
        "status": "BERHASIL",
        "output": str(out_file),
        "entries_count": count,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
    }
    _print(payload)
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)

    note = NoteRecord(
        work_date=d,
        kind=args.kind,
        text=args.text,
        created_at=datetime.now(),
    )
    note_id = store.add_note(note)

    payload = {
        "status": "BERHASIL",
        "note_id": note_id,
        "work_date": d.isoformat(),
        "kind": args.kind,
        "text": args.text,
    }
    _print(payload)
    return 0


def cmd_preview_payload(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)

    # 1. Jalankan kolektor aktif dan sanitasi privasi deterministik (100% offline)
    sanitized_evidence = collect_and_sanitize_evidence(d, cfg, store)

    # 2. Evaluasi kekuatan bukti
    strength_res = evaluate_evidence_strength(sanitized_evidence)

    # 3. Rakit finalized drafting payload dengan filter send_to_llm
    payload = build_drafting_payload(d, sanitized_evidence, cfg)

    # 4. Cetak metadata diagnostik human-readable & payload JSON
    print("=" * 60)
    print("DIAGNOSTIC METADATA - OFFLINE PAYLOAD PREVIEW")
    print("=" * 60)
    print(f"Tanggal Kerja  : {d.isoformat()}")
    print(f"Total Bukti    : {strength_res.total_count}")
    print(f"Bukti Kuat     : {strength_res.strong_count} (strong)")
    print(f"Bukti Lemah    : {strength_res.weak_count} (weak)")
    print(f"Keputusan Gate : {strength_res.decision}")
    print(f"Alasan         : {strength_res.reason}")
    if payload["metadata"]["excluded_sources"]:
        print(
            f"Sumber Dikecualikan: {', '.join(payload['metadata']['excluded_sources'])} "
            "(via send_to_llm: false)"
        )
    print("=" * 60)
    print("FINALIZED DRAFTING PAYLOAD (JSON)")
    print("=" * 60)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    # Jika zero strong evidence, catat status PERLU_INPUT di ledger dan picu notifikasi
    if not strength_res.passed:
        send_system_notification(
            title="Magang Log - Bukti Kurang",
            message=(
                f"Tidak ada bukti berkategori 'strong' untuk tanggal {d.isoformat()}. "
                "Silakan tambahkan catatan manual."
            ),
            channels=cfg.notify.channels,
        )
        run_id = f"run-{d.strftime('%Y%m%d')}-preview"
        store.record_run(
            RunRecord(
                run_id=run_id,
                work_date=d,
                stage="COLLECTED",
                status=Status.PERLU_INPUT,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                error_code="INSUFFICIENT_EVIDENCE",
            )
        )
        return 10

    return 0


def cmd_review(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)
    artifacts_dir = Path(getattr(args, "artifacts_dir", None) or "data/runs")
    artifact_store = ArtifactStore(artifacts_dir=artifacts_dir)

    # 1. Cari draf dari SQLite store atau artifact_store
    draft: LogEntryDraft | None = None
    entry_rec = store.get_entry(d)
    if entry_rec and entry_rec.draft_json:
        try:
            data = json.loads(entry_rec.draft_json)
            if isinstance(data, dict):
                if "work_date" not in data:
                    data["work_date"] = d.isoformat()
                draft = LogEntryDraft.model_validate(data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            draft = None

    if draft is None:
        loaded = artifact_store.load_draft(d)
        if loaded is not None:
            if isinstance(loaded, LogEntryDraft):
                draft = loaded
            elif hasattr(loaded, "draft_json"):
                try:
                    data = json.loads(loaded.draft_json)
                    if isinstance(data, dict):
                        if "work_date" not in data:
                            data["work_date"] = d.isoformat()
                        draft = LogEntryDraft.model_validate(data)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    draft = None

    if draft is None:
        print(f"Tidak ditemukan draf logbook untuk tanggal {d.isoformat()}.", file=sys.stderr)
        print(
            "Pastikan pipeline 'magang-log run' sudah dijalankan untuk menghasilkan draf.",
            file=sys.stderr,
        )
        return EXIT_CODES[Status.PERLU_INPUT]

    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)

    # 2. Ambil bukti pendukung dan catatan
    evidence = store.get_evidence(d)
    notes = store.get_notes(d)
    if not evidence:
        from .collectors.factory import collect_and_sanitize_evidence
        from .models import EvidenceItem

        sanitized = collect_and_sanitize_evidence(d, cfg, store)
        evidence = [
            EvidenceItem(
                id=e.id,
                work_date=d,
                source=e.source,
                kind=e.kind,
                ts=e.ts,
                title=e.title,
                detail=e.detail,
                strength=e.strength,
            )
            for e in sanitized
        ]

    # 3. Ambil laporan validasi jika ada di artifact_store
    validation = artifact_store.load_validation(d)

    # 4. Inisialisasi ReviewSession
    drafter_stage = None
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key and "PYTEST_CURRENT_TEST" not in os.environ:
        from .drafter import DraftingStage, EvidenceDrafter, GeminiModelClient
        from .validator import MultiStageValidator

        client = GeminiModelClient(
            api_key=api_key,
            model=getattr(cfg.llm, "model", "gemini-3.5-flash"),
            temperature=getattr(cfg.llm, "temperature", 0.2),
        )
        evidence_drafter = EvidenceDrafter(
            model_client=client,
            model_name=getattr(cfg.llm, "model", "gemini-3.5-flash"),
        )
        drafter_stage = DraftingStage(
            drafter=evidence_drafter,
            validator=MultiStageValidator(),
        )

    session = ReviewSession(
        store=store,
        artifact_store=artifact_store,
        drafter_stage=drafter_stage,
    )

    approved = session.review(
        target_date=d,
        draft=draft,
        validation=validation,
        evidence=evidence,
        notes=notes,
    )

    if approved is not None:
        return EXIT_CODES[Status.SUDAH_TERKIRIM]
    return EXIT_CODES[Status.PERLU_REVIEW]


def cmd_status(args: argparse.Namespace) -> int:
    """Audit kalender dan status entri logbook beberapa hari terakhir (grid/tabel visual)."""
    d_end = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
    days_count = max(1, getattr(args, "days", 14))
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)

    cfg_path = Path(args.config) if getattr(args, "config", None) else None
    cfg = load_config(cfg_path)
    gate = PreflightGate.from_config_and_store(cfg, store)

    dates = [d_end - timedelta(days=i) for i in reversed(range(days_count))]
    items: list[dict[str, Any]] = []

    badge_counts: dict[str, int] = {
        "[TERKIRIM]": 0,
        "[REVIEW]": 0,
        "[INPUT]": 0,
        "[LIBUR]": 0,
        "[GAGAL]": 0,
        "[BELUM_DIISI]": 0,
    }

    for d in dates:
        day_name = INDONESIAN_DAY_NAMES[d.weekday()]
        entry = store.get_entry(d)
        runs = store.get_runs_for_date(d)

        badge: str
        keterangan: str

        if entry and (
            entry.verified_at
            or entry.submitted_at
            or (
                entry.portal_status
                and entry.portal_status in ("SUDAH_TERKIRIM", "BERHASIL", "TERKIRIM")
            )
        ):
            badge = "[TERKIRIM]"
            keterangan = "Terkirim ke portal"
        elif entry and (entry.approved_at or entry.approved_json):
            badge = "[REVIEW]"
            keterangan = "Disetujui, siap submit"
        elif entry and entry.draft_json:
            badge = "[REVIEW]"
            keterangan = "Draf tersedia, perlu review"
        elif runs:
            latest = runs[-1]
            if latest.status in (Status.SUDAH_TERKIRIM, Status.BERHASIL):
                badge = "[TERKIRIM]"
                keterangan = "Terkirim / Berhasil"
            elif latest.status == Status.PERLU_REVIEW:
                badge = "[REVIEW]"
                keterangan = "Menunggu review manusia"
            elif latest.status == Status.PERLU_INPUT:
                badge = "[INPUT]"
                keterangan = "Bukti kurang, perlu input catatan"
            elif latest.status == Status.LIBUR:
                badge = "[LIBUR]"
                keterangan = "Hari libur / non-kerja"
            elif latest.status in (Status.GAGAL, Status.TERKUNCI, Status.CRASH):
                badge = "[GAGAL]"
                keterangan = f"Gagal ({latest.error_code or latest.status})"
            else:
                badge = f"[{latest.status}]"
                keterangan = str(latest.status)
        else:
            gate_res = gate.calendar_gate.inspect(d)
            if gate_res.decision == GateDecision.LIBUR:
                badge = "[LIBUR]"
                keterangan = gate_res.reason or "Hari libur / non-kerja"
            elif d.weekday() >= 5:
                badge = "[LIBUR]"
                keterangan = "Akhir pekan"
            else:
                badge = "[BELUM_DIISI]"
                keterangan = "Belum ada entri logbook"

        if badge in badge_counts:
            badge_counts[badge] += 1
        elif badge.startswith("["):
            badge_counts[badge] = badge_counts.get(badge, 0) + 1

        items.append(
            {
                "date": d.isoformat(),
                "day": day_name,
                "badge": badge,
                "status": keterangan,
            }
        )

    if getattr(args, "json", False):
        _print(items)
        return 0

    print("=" * 80)
    print(f"AUDIT STATUS KALENDER LOGBOOK ({days_count} HARI TERAKHIR)")
    print(f"Rentang: {dates[0].isoformat()} s/d {dates[-1].isoformat()}")
    print("=" * 80)
    print(f"{'TANGGAL':<12} {'HARI':<10} {'STATUS BADGE':<15} {'KETERANGAN'}")
    print("-" * 80)
    for it in items:
        print(f"{it['date']:<12} {it['day']:<10} {it['badge']:<15} {it['status']}")
    print("=" * 80)
    print(
        f"Ringkasan: {badge_counts['[TERKIRIM]']} Terkirim | "
        f"{badge_counts['[REVIEW]']} Perlu Review | "
        f"{badge_counts['[INPUT]']} Perlu Input | "
        f"{badge_counts['[LIBUR]']} Libur | "
        f"{badge_counts['[GAGAL]']} Gagal | "
        f"{badge_counts['[BELUM_DIISI]']} Belum Diisi"
    )
    print("=" * 80)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Menampilkan metrik keandalan operasional, statistik durasi p95, dan rasio edit."""
    d_end = date.fromisoformat(args.date) if getattr(args, "date", None) else date.today()
    days_count = max(1, getattr(args, "days", 20))
    d_start = d_end - timedelta(days=days_count - 1)
    db_path = getattr(args, "db", None) or "data/state.db"
    store = LedgerStore(db_path=db_path)

    all_runs = store.list_runs()
    runs = [r for r in all_runs if d_start <= r.work_date <= d_end]

    total_runs = len(runs)
    successful_runs = sum(
        1 for r in runs if r.status in (Status.BERHASIL, Status.SUDAH_TERKIRIM)
    )
    failed_runs = sum(
        1 for r in runs if r.status in (Status.GAGAL, Status.CRASH, Status.TERKUNCI)
    )
    success_rate = round((successful_runs / total_runs * 100.0), 1) if total_runs > 0 else 0.0

    durations = [float(r.duration_ms) for r in runs if r.duration_ms > 0]
    avg_duration_ms = round(sum(durations) / len(durations), 1) if durations else 0.0
    p50_duration_ms = calculate_median(durations)
    p95_duration_ms = calculate_percentile(durations, 95.0)

    tokens_in = sum(r.tokens_in for r in runs)
    tokens_out = sum(r.tokens_out for r in runs)
    total_tokens = tokens_in + tokens_out

    with store.connection() as conn:
        rows = conn.execute(
            "SELECT edit_ratio, work_date FROM entries WHERE work_date >= ? AND work_date <= ?;",
            (d_start.isoformat(), d_end.isoformat()),
        ).fetchall()

    edit_ratios = [float(r["edit_ratio"]) for r in rows if r["edit_ratio"] is not None]
    median_edit_ratio = calculate_median(edit_ratios)
    avg_edit_ratio = round(sum(edit_ratios) / len(edit_ratios), 2) if edit_ratios else 0.0

    metrics = {
        "days": days_count,
        "from_date": d_start.isoformat(),
        "to_date": d_end.isoformat(),
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate_pct": success_rate,
        "durations_ms": {
            "avg": avg_duration_ms,
            "p50": p50_duration_ms,
            "p95": p95_duration_ms,
        },
        "tokens": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total": total_tokens,
        },
        "edit_ratio": {
            "median": median_edit_ratio,
            "avg": avg_edit_ratio,
            "count": len(edit_ratios),
        },
        "total_entries": len(rows),
    }

    if getattr(args, "json", False):
        _print(metrics)
        return 0

    print("=" * 80)
    print(f"OPERATIONAL RELIABILITY REPORT ({days_count} HARI TERAKHIR)")
    print(f"Rentang Tanggal: {d_start.isoformat()} s/d {d_end.isoformat()}")
    print("=" * 80)
    print("METRIK EKSEKUSI PIPELINE:")
    print(f"  Total Eksekusi       : {total_runs}")
    print(f"  Berhasil / Terkirim  : {successful_runs}")
    print(f"  Gagal / Terkunci     : {failed_runs}")
    print(f"  Tingkat Keberhasilan : {success_rate:.1f}%")
    print("\nDURASI OPERASIONAL (ms):")
    print(f"  Rata-rata Durasi     : {avg_duration_ms:.1f} ms")
    print(f"  Median (p50)         : {p50_duration_ms:.1f} ms")
    print(f"  95th Percentile (p95): {p95_duration_ms:.1f} ms")
    print("\nKONSUMSI TOKEN LLM:")
    print(f"  Tokens Masuk (Prompt): {tokens_in:,}")
    print(f"  Tokens Keluar (Draft): {tokens_out:,}")
    print(f"  Total Token          : {total_tokens:,}")
    print("\nKUALITAS DRAF (EDIT RATIO):")
    print(f"  Median Edit Ratio    : {median_edit_ratio:.2f}")
    print(f"  Rata-rata Edit Ratio : {avg_edit_ratio:.2f}")
    print(f"  Total Entri Terdok.  : {len(rows)} entri ({len(edit_ratios)} dengan metrik edit)")
    print("=" * 80)
    return 0


@dataclass
class CliResult:
    """Hasil eksekusi terisolasi perintah CLI."""

    exit_code: int
    stdout: str
    stderr: str
    output: str
    exception: BaseException | None = None


class CliRunner:
    """Helper untuk menjalankan dan menguji CLI secara terisolasi tanpa subproses eksternal."""

    def invoke(
        self,
        app: Any = None,
        args: list[str] | None = None,
        input: str | None = None,
        env: dict[str, str] | None = None,
        catch_exceptions: bool = True,
    ) -> CliResult:
        import os
        from unittest.mock import patch

        if isinstance(app, (list, tuple)):
            args = list(app)
            app = main
        elif app is None:
            app = main

        args = list(args) if args is not None else []

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        stdin_buf = io.StringIO(input) if input is not None else io.StringIO()

        exit_code = 0
        caught_exc: BaseException | None = None

        env_patcher = patch.dict(os.environ, env) if env else None
        if env_patcher:
            env_patcher.start()

        orig_stdout, orig_stderr, orig_stdin = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr, sys.stdin = stdout_buf, stderr_buf, stdin_buf

        try:
            if callable(app):
                exit_code = app(args)
            elif isinstance(app, argparse.ArgumentParser):
                parsed = app.parse_args(args)
                if hasattr(parsed, "func"):
                    ret = parsed.func(parsed)
                    if isinstance(ret, (Status, str)):
                        exit_code = get_exit_code(ret)
                    else:
                        exit_code = int(ret or 0)
                else:
                    exit_code = 0
            else:
                exit_code = main(args)
        except SystemExit as exc:
            if isinstance(exc.code, int):
                exit_code = exc.code
            elif exc.code is None:
                exit_code = 0
            else:
                exit_code = 1
                stderr_buf.write(str(exc.code))
        except BaseException as exc:
            caught_exc = exc
            if not catch_exceptions:
                raise
            exit_code = 1
            stderr_buf.write(f"Exception: {exc}\n")
        finally:
            sys.stdout, sys.stderr, sys.stdin = orig_stdout, orig_stderr, orig_stdin
            if env_patcher:
                env_patcher.stop()

        stdout_str = stdout_buf.getvalue()
        stderr_str = stderr_buf.getvalue()
        output_str = stdout_str + stderr_str

        return CliResult(
            exit_code=exit_code if exit_code is not None else 0,
            stdout=stdout_str,
            stderr=stderr_str,
            output=output_str,
            exception=caught_exc,
        )


def build_parser(prog: str = "magang-log") -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", help="default: portal MagangHub (halaman Riwayat)")
    common.add_argument("--auth-state", default="data/auth/state.json")
    common.add_argument("--artifacts-dir", default="data/runs")
    common.add_argument(
        "--channel", default="chrome", choices=["chrome", "msedge", "chromium"],
        help="chrome/msedge = browser terpasang; chromium = bawaan Playwright",
    )  # fmt: skip
    common.add_argument(
        "--headless", action="store_true", help="tanpa jendela (uji dulu lewat `check`)"
    )
    common.add_argument("--config", help="path file konfigurasi YAML (default: config/config.yaml)")
    common.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=argparse.SUPPRESS,
        help="tampilkan detail error & stack trace lengkap saat terjadi kesalahan",
    )

    parser = argparse.ArgumentParser(prog=prog, parents=[common], description=__doc__)



    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", parents=[common], help="login manual sekali, simpan sesi").set_defaults(
        func=cmd_login
    )

    p = sub.add_parser(
        "run",
        parents=[common],
        help="jalankan alur pipeline harian logbook otomatis (coordinator & state machine)",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument(
        "--mode",
        choices=["review", "resume"],
        help="mode eksekusi pipeline: review (buka interaktif review) | resume (pulihkan dari checkpoint)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="jalankan simulasi dry-run tanpa submit final"
    )
    p.add_argument(
        "--resume", action="store_true", help="pulihkan eksekusi dari artifak sebelumnya"
    )
    p.add_argument(
        "--force", action="store_true", help="paksa buat ulang draf (tidak melewati hari terkirim)"
    )
    p.add_argument("--auto-approve", action="store_true", help="setujui draf otomatis (pengetesan)")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser(
        "export",
        parents=[common],
        help="ekspor entri logbook yang disetujui ke file Markdown UTF-8 bersih",
    )
    p.add_argument(
        "--output",
        "-o",
        default="logbook.md",
        help="path output file markdown (default: logbook.md)",
    )
    p.add_argument(
        "--from",
        dest="from_date",
        help="filter batas awal tanggal (YYYY-MM-DD)",
    )
    p.add_argument(
        "--to",
        dest="to_date",
        help="filter batas akhir tanggal (YYYY-MM-DD)",
    )
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser(
        "note",
        parents=[common],
        help="tambahkan catatan refleksi manual harian (aktivitas, pembelajaran, kendala)",
    )
    p.add_argument("text", help="isi catatan refleksi")
    p.add_argument(
        "--type",
        "--kind",
        dest="kind",
        required=True,
        choices=["aktivitas", "pembelajaran", "kendala"],
        help="kategori catatan: aktivitas | pembelajaran | kendala",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser(
        "status",
        parents=[common],
        help="audit kalender dan status entri logbook beberapa hari terakhir (grid/tabel visual)",
    )
    p.add_argument(
        "--days",
        type=int,
        default=14,
        help="jumlah hari ke belakang untuk diaudit (default: 14)",
    )
    p.add_argument("--date", help="YYYY-MM-DD batas akhir audit (default: hari ini)")
    p.add_argument("--json", action="store_true", help="tampilkan hasil dalam format JSON")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser(
        "report",
        parents=[common],
        help="tampilkan metrik keandalan operasional, statistik durasi p95, dan rasio edit",
    )
    p.add_argument(
        "--days",
        type=int,
        default=20,
        help="jumlah hari ke belakang untuk dihitung metriknya (default: 20)",
    )
    p.add_argument("--date", help="YYYY-MM-DD batas akhir metrik (default: hari ini)")
    p.add_argument("--json", action="store_true", help="tampilkan hasil dalam format JSON")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser(
        "gate",
        parents=[common],
        help="pre-flight gate kalender & ledger: hari kerja, libur, dan status terkirim",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument(
        "--force",
        action="store_true",
        help="buat ulang draf (tidak melewati SUDAH_TERKIRIM)",
    )
    p.add_argument("--content-hash", help="hash konten yang dievaluasi")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser(
        "check", parents=[common], help="diagnosis read-only: login, status hari, lokasi, selector"
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser(
        "doctor",
        parents=[common],
        help="diagnostik kesehatan sistem & canary selector portal (doctor --portal)",
    )
    p.add_argument(
        "--portal",
        action="store_true",
        default=False,
        help="uji kesehatan canary selector portal",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--json", action="store_true", help="tampilkan hasil dalam format JSON")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser(
        "fill", parents=[common], help="DRY-RUN: isi kolom, tidak mencentang/mengirim"
    )
    p.add_argument("--entry", required=True, help="file JSON entri")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="flag eksplisit dry-run (selalu aktif pada fill)",
    )
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser(
        "submit",
        parents=[common],
        help="isi, centang pernyataan setelah Anda setuju, kirim, verifikasi",
    )
    p.add_argument(
        "--entry",
        help="file JSON entri (opsional, jika kosong dimuat otomatis dari ledger)",
    )
    p.add_argument(
        "--date",
        help="YYYY-MM-DD (default: hari ini, bila --entry tidak dispesifikasikan)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="DRY-RUN: isi kolom dan verifikasi tanpa mencentang atau mengirim",
    )
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser(
        "preview-payload",
        parents=[common],
        help="preview offline payload JSON yang akan dikirim ke LLM dan diagnostik gate kekuatan bukti",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_preview_payload)

    p = sub.add_parser(
        "review",
        parents=[common],
        help="tinjau draf logbook interaktif (approve [Y], edit di $EDITOR [E], regenerate [R], skip [S])",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_review)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    verbose = bool(getattr(args, "verbose", False))
    try:
        ret = args.func(args)
        if isinstance(ret, (Status, str)):
            return get_exit_code(ret)
        return int(ret or 0)
    except Exception as exc:  # noqa: BLE001
        if verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_CODES[Status.CRASH]


if __name__ == "__main__":
    sys.exit(main())

