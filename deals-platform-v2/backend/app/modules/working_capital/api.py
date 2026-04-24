"""CS4 API."""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import DbSession, Reviewer
from app.api.situations import to_out
from app.config import get_settings
from app.models.enums import Module
from app.models.orm import Situation, Upload
from app.models.schemas import SituationOut, UploadOut
from app.modules.post_deal.client_data import get_client_data_manager
from app.modules.working_capital.service import WCInputs, diagnose

router = APIRouter(prefix="/working-capital", tags=["working_capital"])


def _read(file: UploadFile, raw: bytes) -> pd.DataFrame:
    name = (file.filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(raw))
    return pd.read_csv(io.BytesIO(raw))


@router.post("/diagnose", response_model=list[SituationOut])
async def diagnose_endpoint(
    db: DbSession,
    reviewer: Reviewer,
    subject_name: str = Form(...),
    sector: str = Form("Generic"),
    revenue_annual_usd: float = Form(...),
    cogs_annual_usd: float = Form(...),
    ar: UploadFile = File(...),
    ap: UploadFile = File(...),
    inv: UploadFile = File(...),
):
    s = get_settings()
    upload_dir = Path(s.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    tag = f"{dt.datetime.utcnow().timestamp():.0f}"
    raws = {}
    for key, f in [("ar", ar), ("ap", ap), ("inv", inv)]:
        raw = await f.read()
        (upload_dir / f"wc_{key}_{tag}_{f.filename}").write_bytes(raw)
        raws[key] = raw

    try:
        ar_df = _read(ar, raws["ar"])
        ap_df = _read(ap, raws["ap"])
        inv_df = _read(inv, raws["inv"])
    except Exception as e:
        raise HTTPException(400, f"failed to parse AR/AP/inventory: {e}") from e

    for col in ("invoice_date", "due_date", "paid_date"):
        if col in ar_df.columns:
            ar_df[col] = pd.to_datetime(ar_df[col], errors="coerce", utc=True)
        if col in ap_df.columns:
            ap_df[col] = pd.to_datetime(ap_df[col], errors="coerce", utc=True)

    inp = WCInputs(
        revenue_annual_usd=revenue_annual_usd,
        cogs_annual_usd=cogs_annual_usd,
        ar_df=ar_df,
        ap_df=ap_df,
        inv_df=inv_df,
        as_of=dt.datetime.now(dt.timezone.utc),
        sector=sector,
    )
    situations = diagnose(db, inp=inp, subject_name=subject_name)

    up = Upload(
        module=Module.WORKING_CAPITAL.value,
        kind="diagnostic",
        filename=f"wc_{subject_name}_{tag}",
        file_path=str(upload_dir),
        rows=len(situations),
        uploaded_by=reviewer,
        meta={"subject_name": subject_name, "sector": sector},
    )
    db.add(up)
    db.commit()
    return [to_out(db, s) for s in situations]


@router.post("/diagnose-inline", response_model=list[SituationOut])
def diagnose_inline(
    db: DbSession,
    subject_name: str,
    sector: str,
    revenue_annual_usd: float,
    cogs_annual_usd: float,
    ar: list[dict],
    ap: list[dict],
    inv: list[dict],
):
    """Same as /diagnose but with JSON body for automation/tests."""
    ar_df = pd.DataFrame(ar)
    ap_df = pd.DataFrame(ap)
    inv_df = pd.DataFrame(inv)
    for col in ("invoice_date", "due_date", "paid_date"):
        if col in ar_df.columns:
            ar_df[col] = pd.to_datetime(ar_df[col], errors="coerce", utc=True)
        if col in ap_df.columns:
            ap_df[col] = pd.to_datetime(ap_df[col], errors="coerce", utc=True)
    inp = WCInputs(
        revenue_annual_usd=revenue_annual_usd,
        cogs_annual_usd=cogs_annual_usd,
        ar_df=ar_df, ap_df=ap_df, inv_df=inv_df,
        as_of=dt.datetime.now(dt.timezone.utc),
        sector=sector,
    )
    situations = diagnose(db, inp=inp, subject_name=subject_name)
    return [to_out(db, s) for s in situations]


@router.get("/history", response_model=list[SituationOut])
def history(db: DbSession, limit: int = 100):
    rows = db.scalars(
        select(Situation)
        .where(Situation.module == Module.WORKING_CAPITAL.value)
        .order_by(Situation.created_at.desc())
        .limit(limit)
    ).all()
    return [to_out(db, s) for s in rows]


# CS4 Mock Client Data Management
@router.get("/mock-client-data")
def get_cs4_mock_data():
    """Get default or uploaded CS4 client data (working capital metrics)."""
    manager = get_client_data_manager()
    return manager.get_cs4_data()


@router.post("/mock-client-data")
def set_cs4_mock_data(data: dict):
    """Upload/update CS4 client data for testing."""
    manager = get_client_data_manager()
    result = manager.set_cs4_data(data)
    return {**result, "data": manager.get_cs4_data()}
