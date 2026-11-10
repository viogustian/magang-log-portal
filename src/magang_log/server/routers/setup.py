"""SetupWizard API endpoints for Gemini validation, preset library, role prediction, workspace scanning, config persistence, and task scheduler."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...settings import (
    AppConfig,
    LLMSettings,
    NotifySettings,
    PortalSettings,
    RetentionDaysSettings,
    ReviewSettings,
    RulesSettings,
    SourcesSettings,
    find_repo_root,
    load_config,
    normalize_workdays,
)
from ...workprofile import WorkProfile, load_presets
from ..services.setup_service import (
    DEFAULT_MODEL,
    FolderValidationResult,
    PredictProfileResponse,
    RequirementItem,
    WizardProgressState,
    inspect_scheduler_status,
    load_wizard_progress,
    predict_work_profile,
    recheck_system_requirement,
    register_task_scheduler,
    save_app_configuration,
    save_wizard_progress,
    scan_system_requirements,
    scan_workspace_repos,
    unregister_task_scheduler,
    validate_folder_paths,
    verify_gemini_connection,
    fetch_available_gemini_models,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


class TestGeminiRequest(BaseModel):
    """Request payload for Gemini API key validation."""

    api_key: str = Field(..., description="Google AI Studio Gemini API Key")


class TestGeminiResponse(BaseModel):
    """Response payload for Gemini API key validation."""

    valid: bool
    model: str


class GeminiModelItem(BaseModel):
    """Available Gemini model item description."""

    id: str
    display_name: str
    is_recommended: bool = False


class GeminiModelsResponse(BaseModel):
    """Response payload for available live Gemini models."""

    models: list[GeminiModelItem]
    active_model: str
    source: str


class PredictProfileRequest(BaseModel):
    """Request payload for role prediction."""

    description: str = Field(..., description="Natural language description of internship tasks")
    api_key: str | None = Field(default=None, description="Optional Google AI Studio Gemini API Key")


class ScanReposRequest(BaseModel):
    """Request payload for scanning Git repositories in a workspace folder."""

    root_path: str = Field(..., description="Root workspace directory path")
    only_git: bool = Field(default=True, description="Filter for Git repositories only")


class DiscoveredRepoResponse(BaseModel):
    """Information on a discovered repository."""

    name: str
    path: str
    is_git: bool


class SaveConfigLLMSettings(BaseModel):
    """LLM configuration payload matching LLMSettings with optional api_key."""

    model_config = ConfigDict(extra="ignore")

    provider: str = "gemini"
    model: str = "gemini-3.5-flash"
    api_key: str | None = None
    temperature: float = 0.2
    max_input_tokens: int = 6000
    daily_token_budget: int = 20000


class SaveConfigRequest(BaseModel):
    """Unified configuration payload matching AppConfig schema."""

    model_config = ConfigDict(extra="ignore")

    timezone: str = "Asia/Jakarta"
    workdays: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])
    holidays_file: Path = Path("config/holidays.yaml")
    personal_holidays: dict[str, str] = Field(default_factory=dict)
    portal: PortalSettings = Field(default_factory=PortalSettings)
    rules: RulesSettings = Field(default_factory=RulesSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    llm: SaveConfigLLMSettings = Field(default_factory=SaveConfigLLMSettings)
    sources: SourcesSettings = Field(default_factory=SourcesSettings)
    notify: NotifySettings = Field(default_factory=NotifySettings)
    retention_days: RetentionDaysSettings = Field(default_factory=RetentionDaysSettings)

    work_profile: WorkProfile | None = None
    config_path: str | None = None

    @field_validator("workdays")
    @classmethod
    def validate_workdays(cls, v: list[str]) -> list[str]:
        normalize_workdays(v)
        return v


class SaveConfigResponse(BaseModel):
    """Response payload after saving configuration."""

    success: bool
    saved_at: str


class RegisterSchedulerRequest(BaseModel):
    """Request payload for Windows Task Scheduler registration."""

    trigger_time: str | None = Field(default=None, description="Legacy daily trigger time")
    review_time: str = Field(default="16:30", description="Afternoon review trigger time in HH:MM format (e.g. '16:30')")
    resume_time: str = Field(default="20:00", description="Evening resume trigger time in HH:MM format (e.g. '20:00')")
    active_days: list[str] | None = Field(default=None, description="Active working days for the schedule")
    task_prefix: str = Field(default="MagangLog", description="Prefix for scheduled tasks")

    @field_validator("review_time", "resume_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        s = v.strip()
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", s):
            raise ValueError(f"Invalid time format: {v!r}. Expected 24-hour HH:MM format (e.g. '16:30').")
        return s


class RegisterSchedulerResponse(BaseModel):
    """Response payload after registering task scheduler."""

    success: bool
    task_name: str
    review_time: str = "16:30"
    resume_time: str = "20:00"


class SchedulerStatusResponse(BaseModel):
    """Status information of registered background tasks."""

    status: str = Field(..., description="Registration state: registered | needs_update | unregistered")
    is_registered: bool
    review_task_name: str
    resume_task_name: str
    review_time: str | None = None
    resume_time: str | None = None
    diagnostic_message: str


class UnregisterSchedulerRequest(BaseModel):
    """Request payload for unregistering background tasks."""

    task_prefix: str = Field(default="MagangLog", description="Task prefix to unregister")


class UnregisterSchedulerResponse(BaseModel):
    """Response payload after unregistering background tasks."""

    success: bool
    message: str


class RecheckRequirementRequest(BaseModel):
    """Request payload for single requirement re-evaluation."""

    name: str = Field(..., description="Name of the requirement to re-check")


class ValidateFoldersRequest(BaseModel):
    """Request payload for folder path validation."""

    paths: list[str] = Field(..., description="List of directory paths to validate")


class SaveProgressResponse(BaseModel):
    """Response payload after persisting wizard progress."""

    success: bool
    saved_at: str


@router.post(
    "/test-gemini",
    response_model=TestGeminiResponse,
    summary="Validate Google AI Studio Gemini API key",
)
def test_gemini(req: TestGeminiRequest) -> dict[str, Any]:
    """Test connectivity and validation for Gemini API key."""
    clean_key = req.api_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key must not be empty.",
        )

    try:
        result = verify_gemini_connection(clean_key, model=DEFAULT_MODEL)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        msg = str(exc)
        if any(marker in msg for marker in ("HTTP 400", "HTTP 401", "HTTP 403", "not valid", "API key")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=msg,
        ) from exc


@router.get(
    "/gemini-models",
    response_model=GeminiModelsResponse,
    summary="Fetch live available Gemini Flash models from Google AI Studio",
)
def get_gemini_models(
    api_key: str | None = Query(default=None, description="Optional Google AI Studio API key"),
) -> dict[str, Any]:
    """Retrieve available active Gemini flash models for logbook drafting."""
    return fetch_available_gemini_models(api_key=api_key)


@router.get(
    "/presets",
    response_model=list[WorkProfile],
    summary="Fetch bundled offline WorkProfile presets",
)
def get_presets() -> list[WorkProfile]:
    """Retrieve all standard bundled role presets."""
    try:
        return load_presets()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load bundled presets: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load presets: {exc}",
        ) from exc


@router.post(
    "/predict-profile",
    response_model=PredictProfileResponse,
    summary="Predict tailored WorkProfile with offline preset fallback",
)
def predict_profile(req: PredictProfileRequest) -> PredictProfileResponse:
    """Predict WorkProfile from natural language description with fallback."""
    try:
        return predict_work_profile(
            description=req.description,
            api_key=req.api_key,
            model=DEFAULT_MODEL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error in predict_profile: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile prediction failed: {exc}",
        ) from exc


@router.post(
    "/scan-repos",
    response_model=list[DiscoveredRepoResponse],
    summary="Scan workspace child directories for Git repositories",
)
def scan_repos(req: ScanReposRequest) -> list[dict[str, Any]]:
    """Scan root_path for child Git repositories."""
    try:
        return scan_workspace_repos(req.root_path, only_git=req.only_git)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/save",
    response_model=SaveConfigResponse,
    summary="Atomically validate and persist application settings to config.yaml",
)
def save_config(req: SaveConfigRequest) -> dict[str, Any]:
    """Validate and atomically persist configuration to disk."""
    try:
        # Build clean AppConfig
        llm_clean = LLMSettings(
            provider=req.llm.provider,
            model=req.llm.model,
            temperature=req.llm.temperature,
            max_input_tokens=req.llm.max_input_tokens,
            daily_token_budget=req.llm.daily_token_budget,
        )

        cfg = AppConfig(
            timezone=req.timezone,
            workdays=req.workdays,
            holidays_file=req.holidays_file,
            personal_holidays=req.personal_holidays,
            portal=req.portal,
            rules=req.rules,
            review=req.review,
            llm=llm_clean,
            sources=req.sources,
            notify=req.notify,
            retention_days=req.retention_days,
        )

        if req.work_profile is not None:
            cfg.sources.app.work_profile = req.work_profile

        # Persist GEMINI_API_KEY to environment and .env if non-empty
        if req.llm.api_key and req.llm.api_key.strip():
            clean_key = req.llm.api_key.strip()
            os.environ["GEMINI_API_KEY"] = clean_key
            try:
                root = find_repo_root()
                env_path = root / ".env"
                existing_lines = []
                if env_path.exists():
                    existing_lines = [
                        line for line in env_path.read_text(encoding="utf-8").splitlines()
                        if not line.strip().startswith("GEMINI_API_KEY=")
                    ]
                existing_lines.append(f"GEMINI_API_KEY={clean_key}")
                env_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
            except Exception as env_exc:  # noqa: BLE001
                logger.warning("Could not persist GEMINI_API_KEY to .env: %s", env_exc)

        return save_app_configuration(cfg, target_path=req.config_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist configuration: {exc}",
        ) from exc


@router.get(
    "/config",
    response_model=dict[str, Any],
    summary="Get active application configuration",
)
def get_config(
    config_path: str | None = Query(default=None, description="Optional custom config.yaml path"),
) -> dict[str, Any]:
    """Retrieve full active application configuration."""
    try:
        cfg = load_config(path=Path(config_path) if config_path else None)
        return cfg.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load active configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load configuration: {exc}",
        ) from exc


@router.post(
    "/register-scheduler",
    response_model=RegisterSchedulerResponse,
    summary="Register daily background automation via Windows Task Scheduler",
)
def register_scheduler(req: RegisterSchedulerRequest) -> dict[str, Any]:
    """Register Task Scheduler job with review and resume trigger times."""
    try:
        return register_task_scheduler(
            trigger_time=req.trigger_time,
            review_time=req.review_time,
            resume_time=req.resume_time,
            active_days=req.active_days,
            task_prefix=req.task_prefix,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Task Scheduler registration failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "/scheduler-status",
    response_model=SchedulerStatusResponse,
    summary="Check Windows Task Scheduler registration status",
)
def get_scheduler_status(
    task_prefix: str = Query(default="MagangLog", description="Prefix for scheduled tasks"),
) -> dict[str, Any]:
    """Inspect whether background review and resume tasks are registered in host system."""
    try:
        return inspect_scheduler_status(task_prefix=task_prefix)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to inspect scheduler status: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scheduler inspection error: {exc}",
        ) from exc


@router.post(
    "/unregister-scheduler",
    response_model=UnregisterSchedulerResponse,
    summary="Remove scheduled background automation tasks from Windows Task Scheduler",
)
def unregister_scheduler(req: UnregisterSchedulerRequest) -> dict[str, Any]:
    """Unregister scheduled tasks from Windows Task Scheduler."""
    try:
        return unregister_task_scheduler(task_prefix=req.task_prefix)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to unregister task scheduler: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister scheduler: {exc}",
        ) from exc


@router.get(
    "/requirements",
    response_model=list[RequirementItem],
    summary="Scan and inspect host system requirements from repository configuration",
)
def get_requirements() -> list[RequirementItem]:
    """Scan repository declarative files and evaluate requirement statuses."""
    try:
        return scan_system_requirements()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to scan system requirements: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan requirements: {exc}",
        ) from exc


@router.post(
    "/recheck-requirement",
    response_model=RequirementItem,
    summary="Re-check status of a single system requirement",
)
def recheck_requirement(req: RecheckRequirementRequest) -> RequirementItem:
    """Re-check a single requirement by name."""
    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requirement name must not be empty.",
        )
    try:
        return recheck_system_requirement(clean_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to recheck requirement '%s': %s", clean_name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recheck failed: {exc}",
        ) from exc


@router.post(
    "/validate-folders",
    response_model=list[FolderValidationResult],
    summary="Validate project directories for existence, readability, and Git marker",
)
def validate_folders(req: ValidateFoldersRequest) -> list[FolderValidationResult]:
    """Inspect directory paths for accessibility and Git repository presence."""
    try:
        return validate_folder_paths(req.paths)
    except Exception as exc:  # noqa: BLE001
        logger.error("Folder validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Folder validation failed: {exc}",
        ) from exc


@router.get(
    "/wizard-progress",
    response_model=WizardProgressState,
    summary="Retrieve saved partial wizard progress",
)
def get_wizard_progress() -> WizardProgressState:
    """Retrieve saved wizard progress or initial default state."""
    try:
        return load_wizard_progress()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load wizard progress: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load wizard progress: {exc}",
        ) from exc


@router.post(
    "/save-progress",
    response_model=SaveProgressResponse,
    summary="Persist partial wizard progress state to disk",
)
def save_progress(state: WizardProgressState) -> dict[str, Any]:
    """Persist partial wizard progress state to config/wizard-progress.yaml."""
    try:
        return save_wizard_progress(state)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save wizard progress: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save wizard progress: {exc}",
        ) from exc
