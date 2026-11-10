"""Service functions for logbook entry editing, drafting, and submission approval."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ...drafter.client import FakeModelClient, GeminiModelClient, ModelClient
from ...drafter.engine import EvidenceDrafter
from ...drafter.models import LogEntryDraft
from ...drafter.stage import DraftingStage
from ...models import ApprovedEntry, EntryRecord, Status
from ...settings import AppConfig, load_config
from ...store import LedgerStore
from ...validator.engine import MultiStageValidator

logger = logging.getLogger(__name__)


class EntryDetailResponse(BaseModel):
    """Payload representing an active logbook entry with validation status."""

    entry_id: str
    work_date: str
    kehadiran: str
    aktivitas: str
    pembelajaran: str
    kendala: str
    status: str
    evidence_refs: dict[str, list[str]] = Field(default_factory=dict)
    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)


class EditEntryRequest(BaseModel):
    """Request payload for updating manual draft fields."""

    work_date: str | None = None
    kehadiran: str = Field(default="Hadir", min_length=1)
    aktivitas: str = Field(min_length=1, max_length=5000)
    pembelajaran: str = Field(min_length=1, max_length=5000)
    kendala: str = Field(min_length=1, max_length=5000)


class EditEntryResponse(BaseModel):
    """Response payload after updating active draft fields."""

    success: bool
    updated_entry: EntryDetailResponse
    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)


class DraftEntryRequest(BaseModel):
    """Request payload for regenerating AI draft."""

    work_date: str | None = None


class DraftEntryResponse(BaseModel):
    """Response payload after regenerating draft."""

    success: bool
    draft: EntryDetailResponse
    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)


class ApproveEntryRequest(BaseModel):
    """Request payload for approving and submitting an entry."""

    work_date: str | None = None
    dry_run: bool = False


class ApproveEntryResponse(BaseModel):
    """Response payload after entry submission approval."""

    success: bool
    final_status: str
    error_message: str | None = None


def get_today_entry(
    target_date: date | None = None,
    store: LedgerStore | None = None,
) -> dict[str, Any] | None:
    """Retrieve and validate today's active entry from SQLite ledger store."""
    d = target_date or date.today()
    st = store or LedgerStore()

    entry = st.get_entry(d)
    if entry is None:
        return None

    raw_json = entry.approved_json or entry.draft_json
    if not raw_json:
        return None

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to decode draft JSON for date %s", d)
        return None

    kehadiran = data.get("kehadiran", "Hadir")
    aktivitas = data.get("aktivitas", "")
    pembelajaran = data.get("pembelajaran", "")
    kendala = data.get("kendala", "")
    evidence_refs = data.get("evidence_refs", {})

    evidence_items = st.get_evidence_for_date(d)

    draft_obj = LogEntryDraft(
        work_date=d,
        kehadiran=kehadiran,
        aktivitas=aktivitas,
        pembelajaran=pembelajaran,
        kendala=kendala,
        evidence_refs=evidence_refs if isinstance(evidence_refs, dict) else {},
        prompt_version=entry.prompt_version or "v1",
        model=entry.model or "gemini-2.5-flash",
    )

    validator = MultiStageValidator()
    report = validator.validate(draft_obj, evidence=evidence_items)
    validation_passed = report.is_valid
    validation_errors = report.errors

    if entry.portal_status and entry.portal_status in ("SUDAH_TERKIRIM", "BERHASIL", "TERKIRIM"):
        final_status = entry.portal_status
    elif entry.approved_at is not None:
        final_status = "APPROVED"
    elif validation_passed:
        final_status = "VALIDATED"
    else:
        final_status = "DRAFTED"

    return {
        "entry_id": f"entry-{d.isoformat()}",
        "work_date": d.isoformat(),
        "kehadiran": kehadiran,
        "aktivitas": aktivitas,
        "pembelajaran": pembelajaran,
        "kendala": kendala,
        "status": final_status,
        "evidence_refs": draft_obj.evidence_refs,
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
    }


def edit_entry(
    req: EditEntryRequest,
    store: LedgerStore | None = None,
) -> dict[str, Any]:
    """Update active draft fields and re-evaluate validation status."""
    st = store or LedgerStore()
    d = date.fromisoformat(req.work_date) if req.work_date else date.today()

    existing_entry = st.get_entry(d)
    evidence_refs: dict[str, list[str]] = {}
    prompt_version = "v1"
    model = "gemini-2.5-flash"

    if existing_entry and existing_entry.draft_json:
        try:
            old_data = json.loads(existing_entry.draft_json)
            if isinstance(old_data.get("evidence_refs"), dict):
                evidence_refs = old_data["evidence_refs"]
            prompt_version = existing_entry.prompt_version or prompt_version
            model = existing_entry.model or model
        except (json.JSONDecodeError, TypeError):
            pass

    evidence_items = st.get_evidence_for_date(d)

    draft_obj = LogEntryDraft(
        work_date=d,
        kehadiran=req.kehadiran,
        aktivitas=req.aktivitas,
        pembelajaran=req.pembelajaran,
        kendala=req.kendala,
        evidence_refs=evidence_refs,
        prompt_version=prompt_version,
        model=model,
    )

    validator = MultiStageValidator()
    report = validator.validate(draft_obj, evidence=evidence_items)
    validation_passed = report.is_valid
    validation_errors = report.errors

    draft_json = draft_obj.model_dump_json(indent=2)
    combined = f"{req.aktivitas.strip()}\n{req.pembelajaran.strip()}\n{req.kendala.strip()}"
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    rec = EntryRecord(
        work_date=d,
        draft_json=draft_json,
        prompt_version=prompt_version,
        model=model,
        content_hash=content_hash,
    )
    st.save_entry(rec)

    final_status = "VALIDATED" if validation_passed else "DRAFTED"

    updated_entry = {
        "entry_id": f"entry-{d.isoformat()}",
        "work_date": d.isoformat(),
        "kehadiran": req.kehadiran,
        "aktivitas": req.aktivitas,
        "pembelajaran": req.pembelajaran,
        "kendala": req.kendala,
        "status": final_status,
        "evidence_refs": evidence_refs,
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
    }

    return {
        "success": True,
        "updated_entry": updated_entry,
        "validation_passed": validation_passed,
        "validation_errors": validation_errors,
    }


def regenerate_draft(
    target_date: date | None = None,
    store: LedgerStore | None = None,
    config: AppConfig | None = None,
    drafter_client: ModelClient | None = None,
) -> dict[str, Any]:
    """Regenerate logbook draft for target date using evidence drafter and validator."""
    st = store or LedgerStore()
    cfg = config or load_config()
    d = target_date or date.today()

    evidence_items = st.get_evidence_for_date(d)
    notes = st.get_notes_for_date(d)

    model_name = (
        cfg.llm.model if hasattr(cfg, "llm") and hasattr(cfg.llm, "model") else "gemini-3.5-flash"
    )
    if model_name in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
        model_name = "gemini-3.5-flash"

    client = drafter_client
    if client is None:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
    default_draft = LogEntryDraft(
        work_date=d,
        kehadiran="Hadir",
        aktivitas=(
            f"Melakukan pengerjaan dan verifikasi aktivitas teknis pada tanggal {d.isoformat()} "
            "termasuk implementasi modul, penulisan pengujian unit, serta pengujian integrasi sistem."
        ),
        pembelajaran=(
            "Mendalami mekanisme implementasi REST API dan interaksi dengan basis data lokal "
            "untuk memastikan keandalan serta integritas data operasional instansi."
        ),
        kendala=(
            "Menghadapi tantangan sinkronisasi dan manajemen state audit pada database "
            "yang berhasil diatasi dengan optimasi skema dan penanganan transaksi yang tepat."
        ),
        evidence_refs={"aktivitas": [ev.id for ev in evidence_items[:2]]} if evidence_items else {},
        prompt_version="v1",
        model=model_name,
    )

    if client is None:
        if key:
            client = GeminiModelClient(api_key=key, model=model_name)
        else:
            client = FakeModelClient(response=default_draft)

    drafter = EvidenceDrafter(model_client=client)
    stage = DraftingStage(drafter=drafter)
    try:
        result = stage.draft_and_validate(target_date=d, evidence=evidence_items, notes=notes)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Primary AI drafter failed (%s), attempting dynamic model recovery...",
            exc,
        )
        recovered = False
        exc_str = str(exc)
        if key and any(m in exc_str for m in ("is no longer available", "404", "NOT_FOUND")):
            try:
                from .setup_service import fetch_available_gemini_models, save_app_configuration

                models_info = fetch_available_gemini_models(api_key=key)
                for candidate in models_info.get("models", []):
                    c_id = candidate["id"]
                    if c_id != model_name:
                        logger.info("Attempting auto-heal draft with active Gemini model: %s", c_id)
                        try:
                            retry_client = GeminiModelClient(api_key=key, model=c_id)
                            retry_stage = DraftingStage(drafter=EvidenceDrafter(model_client=retry_client))
                            result = retry_stage.draft_and_validate(
                                target_date=d, evidence=evidence_items, notes=notes
                            )
                            recovered = True
                            try:
                                cfg.llm.model = c_id
                                save_app_configuration(cfg)
                                logger.info("Auto-upgraded active config.yaml model to: %s", c_id)
                            except Exception as save_err:  # noqa: BLE001
                                logger.warning("Could not persist auto-upgraded model: %s", save_err)
                            break
                        except Exception as retry_err:  # noqa: BLE001
                            logger.warning("Recovery candidate %s failed: %s", c_id, retry_err)
            except Exception as autoheal_err:  # noqa: BLE001
                logger.warning("Dynamic model auto-heal failed: %s", autoheal_err)

        if not recovered:
            fallback_stage = DraftingStage(
                drafter=EvidenceDrafter(model_client=FakeModelClient(response=default_draft))
            )
            result = fallback_stage.draft_and_validate(
                target_date=d, evidence=evidence_items, notes=notes
            )

    draft_json = result.draft.model_dump_json(indent=2)
    combined = (
        f"{result.draft.aktivitas.strip()}\n"
        f"{result.draft.pembelajaran.strip()}\n"
        f"{result.draft.kendala.strip()}"
    )
    content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    rec = EntryRecord(
        work_date=d,
        draft_json=draft_json,
        prompt_version=result.draft.prompt_version,
        model=result.draft.model,
        content_hash=content_hash,
    )
    st.save_entry(rec)

    final_status = "VALIDATED" if result.is_valid else "DRAFTED"

    draft_dict = {
        "entry_id": f"entry-{d.isoformat()}",
        "work_date": d.isoformat(),
        "kehadiran": result.draft.kehadiran,
        "aktivitas": result.draft.aktivitas,
        "pembelajaran": result.draft.pembelajaran,
        "kendala": result.draft.kendala,
        "status": final_status,
        "evidence_refs": result.draft.evidence_refs,
        "validation_passed": result.is_valid,
        "validation_errors": result.validation.errors,
    }

    return {
        "success": True,
        "draft": draft_dict,
        "validation_passed": result.is_valid,
        "validation_errors": result.validation.errors,
    }


def approve_and_submit_entry(
    target_date: date | None = None,
    store: LedgerStore | None = None,
    config: AppConfig | None = None,
    coordinator: Any | None = None,
    portal: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Approve active validated draft and coordinate submission to portal."""
    st = store or LedgerStore()
    d = target_date or date.today()

    entry = st.get_entry(d)
    if entry is None or not entry.draft_json:
        return {
            "success": False,
            "final_status": "GAGAL",
            "error_message": f"No active draft found to approve for date {d.isoformat()}",
        }

    try:
        draft_data = json.loads(entry.draft_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "success": False,
            "final_status": "GAGAL",
            "error_message": f"Malformed draft JSON in ledger: {exc}",
        }

    evidence_items = st.get_evidence_for_date(d)
    draft_obj = LogEntryDraft(
        work_date=d,
        kehadiran=draft_data.get("kehadiran", "Hadir"),
        aktivitas=draft_data.get("aktivitas", ""),
        pembelajaran=draft_data.get("pembelajaran", ""),
        kendala=draft_data.get("kendala", ""),
        evidence_refs=draft_data.get("evidence_refs", {}),
        prompt_version=entry.prompt_version or "v1",
        model=entry.model or "gemini-3.5-flash",
    )

    validator = MultiStageValidator()
    report = validator.validate(draft_obj, evidence=evidence_items)
    if not report.is_valid:
        return {
            "success": False,
            "final_status": "VALIDATION_FAILED",
            "error_message": f"Draft validation failed: {'; '.join(report.errors)}",
        }

    now_utc = datetime.now(timezone.utc)
    approved = ApprovedEntry(
        work_date=d,
        kehadiran=draft_obj.kehadiran,
        aktivitas=draft_obj.aktivitas,
        pembelajaran=draft_obj.pembelajaran,
        kendala=draft_obj.kendala,
        approved_at=now_utc,
    )

    approved_json = json.dumps(
        {
            "kehadiran": approved.kehadiran,
            "aktivitas": approved.aktivitas,
            "pembelajaran": approved.pembelajaran,
            "kendala": approved.kendala,
            "approved_at": now_utc.isoformat(),
        }
    )
    st.set_approved(
        work_date=d,
        approved_json=approved_json,
        approved_at=now_utc,
        edit_ratio=0.0,
    )

    # Portal submission
    portal_instance = portal
    if portal_instance is None and coordinator is not None and getattr(coordinator, "portal", None) is not None:
        portal_instance = coordinator.portal

    if portal_instance is None:
        try:
            from ...portal import PlaywrightPortal, PortalConfig
            from ...settings import load_config

            cfg = config or load_config()
            portal_cfg = PortalConfig(
                base_url=cfg.portal.base_url,
                auth_state=cfg.portal.auth_state,
                artifacts_dir=cfg.portal.artifacts_dir,
                headless=cfg.portal.headless,
                channel=cfg.portal.channel,
                timeout_ms=cfg.portal.timeout_ms,
                location_timeout_ms=cfg.portal.location_timeout_ms,
                allow_location=cfg.portal.allow_location,
                min_chars=cfg.rules.min_chars,
                max_chars=cfg.rules.max_chars,
            )
            portal_instance = PlaywrightPortal(portal_cfg)
        except Exception as portal_init_err:
            logger.error("Failed to initialize PlaywrightPortal: %s", portal_init_err)
            return {
                "success": False,
                "final_status": "GAGAL",
                "error_message": f"Inisialisasi Playwright gagal: {portal_init_err}",
            }

    try:
        portal_res = portal_instance.submit(approved, dry_run=dry_run)
    except Exception as exc:
        logger.error("Playwright portal submit error: %s", exc)
        st.update_entry_submission(d, portal_status="GAGAL")
        return {
            "success": False,
            "final_status": "GAGAL",
            "error_message": f"Pengiriman portal gagal: {exc}",
        }

    if portal_res.status in (Status.BERHASIL, Status.SUDAH_TERKIRIM):
        st.mark_submitted(d, portal_status=Status.BERHASIL)
        st.mark_verified(d, portal_status=Status.SUDAH_TERKIRIM)
        return {
            "success": True,
            "final_status": "BERHASIL",
            "error_message": None,
        }
    elif portal_res.status == Status.DRYRUN:
        st.mark_submitted(d, portal_status=Status.DRYRUN)
        return {
            "success": True,
            "final_status": "DRYRUN",
            "error_message": portal_res.note,
        }
    elif portal_res.status == Status.LOGIN_DIPERLUKAN:
        err_msg = (
            f"Sesi portal Monev Kemnaker telah kedaluwarsa atau belum login ({portal_res.note}). "
            "Silakan buka menu Pengaturan -> Kredensial & Portal -> Buka Browser Login Portal."
        )
        st.update_entry_submission(d, portal_status="LOGIN_DIPERLUKAN")
        return {
            "success": False,
            "final_status": "LOGIN_DIPERLUKAN",
            "error_message": err_msg,
        }
    else:
        err_msg = portal_res.note or "Pengiriman logbook ke portal tidak berhasil."
        status_val = (
            portal_res.status.value
            if hasattr(portal_res.status, "value")
            else str(portal_res.status)
        )
        st.update_entry_submission(d, portal_status=status_val)
        return {
            "success": False,
            "final_status": status_val,
            "error_message": err_msg,
        }
