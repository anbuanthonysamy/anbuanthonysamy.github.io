"""Live/offline mode toggle + per-module source status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DbSession
from app.shared.api_mode import MODE_KEY, Mode, mode_status, set_mode
from app.shared.source_status import MODULE_SOURCES, TRACKER

router = APIRouter(prefix="/api/v2", tags=["mode"])


@router.get("/mode")
def get_api_mode(db: DbSession) -> dict:
    """Return the currently stored mode plus the auto-resolved effective value."""
    return mode_status(db)


@router.post("/mode")
def set_api_mode(payload: dict, db: DbSession) -> dict:
    """Set API mode.

    Body: ``{"mode": "live" | "offline" | "auto"}``
    """
    mode = payload.get("mode")
    if mode not in ("live", "offline", "auto"):
        raise HTTPException(400, "mode must be one of: live, offline, auto")
    effective = set_mode(db, mode)  # type: ignore[arg-type]
    return {"stored_mode": mode, "effective_mode": effective}


@router.get("/scan/source-status")
def scan_source_status(
    module: str | None = Query(None, description="Filter to one module (origination|carve_outs|post_deal|working_capital)"),
) -> dict:
    """Per-module source health (populated by most recent scan).

    Each row includes ``status`` (``ok`` | ``error`` | ``skipped`` | ``unknown``),
    ``last_attempt_at``, ``detail`` (error message if failed), and ``mode``.
    """
    if module is not None:
        if module not in MODULE_SOURCES:
            raise HTTPException(404, f"unknown module: {module}")
        return {"modules": [TRACKER.module_report(module)]}
    return {"modules": TRACKER.all_modules_report()}
