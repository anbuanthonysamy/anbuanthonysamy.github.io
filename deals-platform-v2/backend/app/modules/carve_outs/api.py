"""CS2 API."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.situations import to_out
from app.models.enums import Module
from app.models.schemas import SituationOut
from app.modules.carve_outs.service import CarveOutConfig, run_for_all

router = APIRouter(prefix="/carve-outs", tags=["carve_outs"])


@router.post("/run", response_model=list[SituationOut])
def run(db: DbSession, floor_usd: float | None = None, threshold: float | None = None):
    cfg = CarveOutConfig()
    if floor_usd is not None:
        cfg.equity_floor_usd = floor_usd
    if threshold is not None:
        cfg.elevated_threshold = threshold
    runs = run_for_all(db, cfg)
    return [to_out(db, r.situation) for r in runs]


@router.get("/pipeline", response_model=list[SituationOut])
def pipeline(db: DbSession, threshold: float = 0.0, limit: int = 100):
    from sqlalchemy import select

    from app.models.orm import Situation

    q = (
        select(Situation)
        .where(Situation.module == Module.CARVE_OUTS.value)
        .where(Situation.score >= threshold)
        .order_by(Situation.score.desc())
        .limit(limit)
    )
    rows = db.scalars(q).all()
    return [to_out(db, s) for s in rows]
