"""Source health + manual refresh."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.orm import Source as SourceRow
from app.models.schemas import SourceHealthOut
from app.shared.ingest import ingest
from app.sources.registry import BY_ID as SOURCES

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceHealthOut])
def list_sources(db: DbSession):
    rows = db.scalars(select(SourceRow)).all()
    known = {r.id for r in rows}
    out = [
        SourceHealthOut(
            id=r.id,
            name=r.name,
            mode=r.mode,
            last_refresh_at=r.last_refresh_at,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
    ]
    # include registered but never-refreshed sources
    for sid, src in SOURCES.items():
        if sid in known:
            continue
        out.append(
            SourceHealthOut(
                id=sid, name=src.name, mode="never_refreshed",
                last_refresh_at=None, last_status=None, last_error=None,
            )
        )
    return out


@router.post("/sources/{source_id}/refresh")
def refresh_source(source_id: str, db: DbSession, payload: dict | None = None):
    src = SOURCES.get(source_id)
    if src is None:
        raise HTTPException(404, "source not found")
    payload = payload or {}
    try:
        items = src.fetch(**payload)
    except Exception as e:
        raise HTTPException(400, f"fetch failed: {e}") from e
    n = ingest(db, src, items)
    db.commit()
    return {"source": source_id, "ingested": n, "ts": dt.datetime.now(dt.timezone.utc).isoformat()}
