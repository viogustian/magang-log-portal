"""SetupWizard API endpoints for Gemini validation, preset library, role prediction, workspace scanning, config persistence, and task scheduler."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
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
    normalize_workdays,
)
from ...workprofile import WorkProfile, load_presets
from ..services.setup_service import (
    DEFAULT_MODEL,
    PredictProfileResponse,
    predict_work_profile,
    register_task_scheduler,
    save_app_configuration,
    scan_workspace_repos,
    verify_gemini_connection,
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
    llm: LLMSettings = Field(default_factory=LLMSettings)
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

    trigger_time: str = Field(..., description="Daily trigger time in HH:MM format (e.g. '17:00')")
    task_prefix: str = Field(default="MagangLog", description="Prefix for scheduled tasks")


class RegisterSchedulerResponse(BaseModel):
    """Response payload after registering task scheduler."""

    success: bool
    task_name: str


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
        cfg = AppConfig(
            timezone=req.timezone,
            workdays=req.workdays,
            holidays_file=req.holidays_file,
            personal_holidays=req.personal_holidays,
            portal=req.portal,
            rules=req.rules,
            review=req.review,
            llm=req.llm,
            sources=req.sources,
            notify=req.notify,
            retention_days=req.retention_days,
        )

        if req.work_profile is not None:
            cfg.sources.app.work_profile = req.work_profile

        return save_app_configuration(cfg, target_path=req.config_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist configuration: {exc}",
        ) from exc


@router.post(
    "/register-scheduler",
    response_model=RegisterSchedulerResponse,
    summary="Register daily background automation via Windows Task Scheduler",
)
def register_scheduler(req: RegisterSchedulerRequest) -> dict[str, Any]:
    """Register Task Scheduler job with given trigger time."""
    try:
        return register_task_scheduler(
            trigger_time=req.trigger_time,
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
