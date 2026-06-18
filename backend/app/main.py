"""FastAPI application entrypoint.

Phase 2 skeleton: wires settings, exception handlers, health, and all route
modules. Business logic lands in later phases behind these stable contracts.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_export,
    routes_jobs,
    routes_rates,
    routes_review,
    routes_search,
    routes_upload,
    routes_vendors,
)
from app.config import settings
from app.core.exceptions import FreightError, ReviewBlockedError
from app.core.logging import setup_logging

setup_logging("DEBUG" if settings.debug else "INFO")

app = FastAPI(title=settings.app_name, version="0.1.0", debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- exception handlers (§17) ---------------------------------------------- #
@app.exception_handler(ReviewBlockedError)
async def review_blocked_handler(_: Request, exc: ReviewBlockedError):
    return JSONResponse(status_code=409, content={"error": "review_required", "detail": str(exc)})


@app.exception_handler(FreightError)
async def freight_error_handler(_: Request, exc: FreightError):
    return JSONResponse(
        status_code=422, content={"error": exc.__class__.__name__, "detail": str(exc)}
    )


# --- health ---------------------------------------------------------------- #
@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness — process is up. Used by the container healthcheck."""
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}


@app.get("/health/ready", tags=["meta"])
async def ready() -> dict:
    """Readiness — dependencies reachable. Used by orchestrators before routing."""
    from sqlalchemy import text

    from app.db import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "not_ready", "db": str(exc)})


# --- routers --------------------------------------------------------------- #
for module in (
    routes_upload,
    routes_jobs,
    routes_rates,
    routes_review,
    routes_search,
    routes_export,
    routes_vendors,
):
    app.include_router(module.router)
