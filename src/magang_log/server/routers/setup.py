"""SetupWizard API endpoints for Gemini validation, preset library, and role prediction."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ...workprofile import WorkProfile, load_presets
from ..services.setup_service import (
    DEFAULT_MODEL,
    PredictProfileResponse,
    predict_work_profile,
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
        # Classify client error vs gateway/network error
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
