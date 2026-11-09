"""FastAPI application initialization with router configuration and OpenAPI docs."""

from __future__ import annotations

from fastapi import FastAPI

from .routers.health import router as health_router
from .routers.portal import router as portal_router
from .routers.setup import router as setup_router


def create_app() -> FastAPI:
    """Create and configure the local FastAPI application."""
    app = FastAPI(
        title="Magang Log Local Desktop API",
        description="Local REST API backend for Magang Log desktop application.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(setup_router, prefix="/api")
    app.include_router(portal_router, prefix="/api")

    return app

