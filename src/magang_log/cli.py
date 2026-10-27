"""CLI modul portal: login | check | fill (dry-run) | submit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .exporter import export_logbook
from .gates import GateDecision, PreflightGate
from .models import EXIT_CODES, ApprovedEntry, Status
from .pipeline import DraftResult, PipelineCoordinator, ValidationResult
from .portal import NotApproved, PlaywrightPortal, PortalConfig
from .portal import selectors as sel
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
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, channel=cfg.channel)
        context = browser.new_context()
        page = context.new_page()
        page.goto(cfg.base_url)
        print("Login MANUAL di jendela browser (termasuk OTP/captcha bila ada).")
        print("Setelah halaman 'Riwayat Kehadiran' tampil, kembali ke sini dan tekan Enter.")
        input()
        try:
            sel.history_heading(page).wait_for(state="visible", timeout=5_000)
        except Exception as exc:  # noqa: BLE001 - dilaporkan ke pengguna, bukan ditelan
            print(
                f"Halaman Riwayat Kehadiran belum tampil; sesi TIDAK disimpan ({exc.__class__.__name__})."
            )
            browser.close()
            return EXIT_CODES[Status.LOGIN_DIPERLUKAN]
        cfg.auth_state.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(cfg.auth_state))
        try:
            os.chmod(cfg.auth_state, 0o600)
        except OSError:
            pass  # Windows: izin POSIX tidak berlaku; folder data/ tetap di-gitignore
        browser.close()
    print(
        f"Sesi disimpan di {cfg.auth_state}. File ini setara kunci akun: JANGAN di-commit/dibagikan."
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    d = date.fromisoformat(args.date) if args.date else date.today()
    with PlaywrightPortal(_config(args)) as portal:
        report = portal.check(d)
    _print(report)
    return 0 if report.get("login") and "error" not in report else EXIT_CODES[Status.GAGAL]


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
        result = portal.submit(entry, dry_run=True)
    _print({"status": result.status, "note": result.note, "screenshots": result.screenshots})
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
    if entry.approved_at is None:
        if not sys.stdin.isatty():
            print("Entri belum disetujui (approved_at kosong) dan tidak ada terminal interaktif.")
            return EXIT_CODES[Status.PERLU_TINDAKAN]
        confirmed = _confirm_interactively(entry)
        if confirmed is None:
            return EXIT_CODES[Status.PERLU_TINDAKAN]
        entry = confirmed
    try:
        with PlaywrightPortal(_config(args)) as portal:
            result = portal.submit(entry)
    except NotApproved as exc:
        print(exc)
        return EXIT_CODES[Status.PERLU_TINDAKAN]
    _print({"status": result.status, "note": result.note, "screenshots": result.screenshots})
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

    coordinator = PipelineCoordinator(
        store=store,
        preflight_gate=gate,
        portal=portal,
        approval=approval,
        artifacts_dir=Path(getattr(args, "artifacts_dir", "data/runs")),
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
        "fill", parents=[common], help="DRY-RUN: isi kolom, tidak mencentang/mengirim"
    )
    p.add_argument("--entry", required=True, help="file JSON entri")
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser(
        "submit",
        parents=[common],
        help="isi, centang pernyataan setelah Anda setuju, kirim, verifikasi",
    )
    p.add_argument("--entry", required=True, help="file JSON entri")
    p.set_defaults(func=cmd_submit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
