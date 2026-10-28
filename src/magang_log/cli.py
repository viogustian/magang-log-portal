"""CLI modul portal: login | check | fill (dry-run) | submit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from .collectors.factory import collect_and_sanitize_evidence
from .collectors.strength import build_drafting_payload, evaluate_evidence_strength
from .drafter.models import LogEntryDraft
from .exporter import export_logbook
from .gates import GateDecision, PreflightGate
from .models import EXIT_CODES, ApprovedEntry, NoteRecord, RunRecord, Status, get_exit_code
from .notify import send_system_notification
from .pipeline import ArtifactStore, DraftResult, PipelineCoordinator, ValidationResult
from .portal import NotApproved, PlaywrightPortal, PortalConfig
from .portal import selectors as sel
from .reviewer import ReviewSession
from .settings import load_config
from .store import LedgerStore

CONFIRM_WORD = "SETUJU"


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
    entry = _load_entry(Path(args.entry))
    dry_run = getattr(args, "dry_run", False)
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

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=gate,
        portal=portal,
        approval=approval,
        artifacts_dir=Path(getattr(args, "artifacts_dir", "data/runs")),
        auto_approval_engine=auto_approval_engine,
        notifier=notifier,
    )

    result = coordinator.run(
        target_date=d,
        dry_run=dry_run,
        resume=bool(getattr(args, "resume", False)),
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

    # 2. Ambil bukti pendukung dan catatan
    evidence = store.get_evidence(d)
    notes = store.get_notes(d)

    # 3. Ambil laporan validasi jika ada di artifact_store
    validation = artifact_store.load_validation(d)

    # 4. Inisialisasi ReviewSession
    session = ReviewSession(
        store=store,
        artifact_store=artifact_store,
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


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(prog="magang-portal", description=__doc__)
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
        "--kind",
        required=True,
        choices=["aktivitas", "pembelajaran", "kendala"],
        help="kategori catatan: aktivitas | pembelajaran | kendala",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--db", help="path database SQLite (default: data/state.db)")
    p.set_defaults(func=cmd_note)

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
        default=True,
        help="uji kesehatan canary selector portal",
    )
    p.add_argument("--date", help="YYYY-MM-DD (default: hari ini)")
    p.add_argument("--json", action="store_true", help="tampilkan hasil dalam format JSON")
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
    p.add_argument("--entry", required=True, help="file JSON entri")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="DRY-RUN: isi kolom dan verifikasi tanpa mencentang atau mengirim",
    )
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
    try:
        ret = args.func(args)
        if isinstance(ret, (Status, str)):
            return get_exit_code(ret)
        return int(ret or 0)
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}", file=sys.stderr)
        return EXIT_CODES[Status.CRASH]


if __name__ == "__main__":
    sys.exit(main())
