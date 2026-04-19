"""CS3 API — upload, compute and inspect."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import DbSession, Reviewer
from app.api.situations import to_out
from app.config import get_settings
from app.models.enums import Module
from app.models.orm import KPI, Situation, Upload
from app.models.schemas import KPIWithActualsOut, SituationOut, UploadOut
from app.modules.post_deal.service import (
    band_view,
    compute_deviations,
    ingest_actuals,
    ingest_deal_case,
)

router = APIRouter(prefix="/post-deal", tags=["post_deal"])


@router.post("/upload/deal-case", response_model=UploadOut)
async def upload_deal_case(
    db: DbSession, reviewer: Reviewer, file: UploadFile = File(...)
):
    s = get_settings()
    Path(s.upload_dir).mkdir(parents=True, exist_ok=True)
    target = Path(s.upload_dir) / f"deal_case_{dt.datetime.utcnow().timestamp():.0f}_{file.filename}"
    raw = await file.read()
    target.write_bytes(raw)

    try:
        case = json.loads(raw)
    except Exception as e:
        raise HTTPException(400, f"deal case must be JSON: {e}") from e

    kpis = ingest_deal_case(db, case, upload_id=str(target))
    up = Upload(
        module=Module.POST_DEAL.value,
        kind="deal_case",
        filename=file.filename or "deal_case.json",
        file_path=str(target),
        rows=len(kpis),
        uploaded_by=reviewer,
        meta={"kpis": [k.name for k in kpis]},
    )
    db.add(up)
    db.commit()
    return UploadOut(
        id=up.id, module=up.module, kind=up.kind, filename=up.filename,
        rows=up.rows, uploaded_at=up.uploaded_at, uploaded_by=up.uploaded_by,
    )


@router.post("/upload/actuals", response_model=UploadOut)
async def upload_actuals(
    db: DbSession,
    reviewer: Reviewer,
    kpi_name: str = Form(...),
    file: UploadFile = File(...),
):
    s = get_settings()
    Path(s.upload_dir).mkdir(parents=True, exist_ok=True)
    target = Path(s.upload_dir) / f"actuals_{kpi_name}_{dt.datetime.utcnow().timestamp():.0f}_{file.filename}"
    raw = await file.read()
    target.write_bytes(raw)
    payload = json.loads(raw)
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    n = ingest_actuals(db, kpi_name, rows)
    up = Upload(
        module=Module.POST_DEAL.value,
        kind="kpi_actual",
        filename=file.filename or f"actuals_{kpi_name}.json",
        file_path=str(target),
        rows=n,
        uploaded_by=reviewer,
        meta={"kpi_name": kpi_name},
    )
    db.add(up)
    db.commit()
    return UploadOut(
        id=up.id, module=up.module, kind=up.kind, filename=up.filename,
        rows=up.rows, uploaded_at=up.uploaded_at, uploaded_by=up.uploaded_by,
    )


@router.post("/compute", response_model=list[SituationOut])
def compute(db: DbSession):
    sits = compute_deviations(db)
    return [to_out(db, s) for s in sits]


@router.get("/kpis", response_model=list[KPIWithActualsOut])
def list_kpis(db: DbSession):
    kpis = db.scalars(select(KPI).where(KPI.module == Module.POST_DEAL.value)).all()
    out: list[KPIWithActualsOut] = []
    for k in kpis:
        view = band_view(db, k.id)
        out.append(
            KPIWithActualsOut(
                id=k.id, module=k.module, name=k.name, unit=k.unit, curve=k.curve,
                target_band_low=k.target_band_low, target_band_mid=k.target_band_mid,
                target_band_high=k.target_band_high,
                target_start=k.target_start, target_end=k.target_end,
                actuals=[(a["ts"], a["value"]) for a in view.get("actuals", [])],
                target_curve=[(b["ts"], b["low"], b["mid"], b["high"]) for b in view.get("band", [])],
            )
        )
    return out


@router.get("/kpis/{kpi_id}/band")
def kpi_band(kpi_id: str, db: DbSession):
    return band_view(db, kpi_id)


@router.get("/deviations", response_model=list[SituationOut])
def list_deviations(db: DbSession, limit: int = 100):
    rows = db.scalars(
        select(Situation)
        .where(Situation.module == Module.POST_DEAL.value)
        .order_by(Situation.score.desc())
        .limit(limit)
    ).all()
    return [to_out(db, s) for s in rows]
