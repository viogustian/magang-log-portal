"""Health readiness check endpoint for client polling."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health readiness check")
def get_health() -> dict[str, str]:
    """Return health status ok for client polling."""
    return {"status": "ok"}

