"""Settings: per-module weights editable at runtime."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.enums import Module
from app.models.orm import SettingKV
from app.scoring.engine import DEFAULT_WEIGHTS, load_weights, save_weights

router = APIRouter(tags=["settings"])


@router.get("/settings/weights/{module}")
def get_weights(module: str, db: DbSession):
    if module not in DEFAULT_WEIGHTS:
        raise HTTPException(404, "unknown module")
    return {"module": module, "weights": load_weights(db, module),
            "defaults": DEFAULT_WEIGHTS[module]}


@router.put("/settings/weights/{module}")
def set_weights(module: str, body: dict, db: DbSession):
    if module not in DEFAULT_WEIGHTS:
        raise HTTPException(404, "unknown module")
    weights = body.get("weights") or {}
    if not isinstance(weights, dict):
        raise HTTPException(400, "weights must be object")
    # normalise to positive floats
    clean = {k: max(0.0, float(v)) for k, v in weights.items()
             if k in DEFAULT_WEIGHTS[module]}
    if not clean:
        raise HTTPException(400, "no valid keys provided")
    save_weights(db, module, clean)
    db.commit()
    return {"module": module, "weights": load_weights(db, module)}


@router.get("/settings")
def dump_settings(db: DbSession):
    rows = db.scalars(select(SettingKV)).all()
    return [{"key": r.key, "value": r.value, "updated_at": r.updated_at} for r in rows]
