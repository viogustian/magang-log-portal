"""Portal authentication router endpoints (/api/portal/*)."""

from __future__ import annotations

import functools
import logging
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.portal_service import (
    PortalAuthStatus,
    get_portal_auth_service,
    get_portal_auth_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal", tags=["portal"])


class OpenLoginRequest(BaseModel):
    """Request payload for opening interactive login browser."""

    timeout_seconds: int = Field(default=300, ge=10, le=1800, description="Login timeout in seconds")


class OpenLoginResponse(BaseModel):
    """Response payload for login launcher."""

    success: bool
    message: str
    authenticated: bool


@router.get(
    "/auth-status",
    response_model=PortalAuthStatus,
    summary="Check current MagangHub portal authentication session status",
)
def check_auth_status() -> PortalAuthStatus:
    """Inspect portal storage state and return session status without launching browser."""
    return get_portal_auth_status()


@router.post(
    "/open-login",
    response_model=OpenLoginResponse,
    summary="Launch headed browser for interactive MagangHub login",
)
async def open_login(req: OpenLoginRequest) -> dict[str, Any]:
    """Launch headed browser session in background thread, guarded against concurrent attempts."""
    service = get_portal_auth_service()

    if service.is_login_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A portal login session is already in progress.",
        )

    try:
        success, message = await anyio.to_thread.run_sync(
            functools.partial(service.launch_interactive_login, timeout_seconds=req.timeout_seconds),
        )
        return {
            "success": success,
            "message": message,
            "authenticated": success,
        }
    except RuntimeError as exc:
        if "already in progress" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Error running interactive login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {exc}",
        ) from exc


@router.post(
    "/confirm-login",
    response_model=OpenLoginResponse,
    summary="Confirm interactive login completion and capture portal session",
)
async def confirm_login() -> dict[str, Any]:
    """Signal the active login browser to verify authentication and persist state.json."""
    service = get_portal_auth_service()
    success, authenticated, message = await anyio.to_thread.run_sync(service.confirm_interactive_login)
    return {
        "success": success,
        "message": message,
        "authenticated": authenticated,
    }


@router.post(
    "/cancel-login",
    summary="Cancel an active interactive login browser session",
)
def cancel_login() -> dict[str, bool]:
    """Request cleanup and closure of any active headed login browser."""
    service = get_portal_auth_service()
    return {"cancelled": service.cancel_interactive_login()}
