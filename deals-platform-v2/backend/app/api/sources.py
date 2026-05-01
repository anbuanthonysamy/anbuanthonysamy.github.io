"""Source health + manual refresh + verification."""
from __future__ import annotations

import datetime as dt
import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.orm import Company, Source as SourceRow
from app.models.schemas import SourceHealthOut, SourceTestOut
from app.shared.ingest import ingest
from app.sources.registry import BY_ID as SOURCES

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SourceHealthOut])
def list_sources(db: DbSession):
    rows = db.scalars(select(SourceRow)).all()
    by_db_id = {r.id: r for r in rows}
    out: list[SourceHealthOut] = []
    # Emit one row per registered source so stubs and never-refreshed sources appear.
    for sid, src in SOURCES.items():
        db_row = by_db_id.get(sid)
        if db_row:
            mode = "stub" if src.is_stub else db_row.mode
            out.append(
                SourceHealthOut(
                    id=db_row.id,
                    name=db_row.name,
                    mode=mode,
                    last_refresh_at=db_row.last_refresh_at,
                    last_status=db_row.last_status,
                    last_error=db_row.last_error,
                    is_stub=src.is_stub,
                    description=src.description,
                    homepage_url=src.homepage_url,
                    last_fallback_reason=db_row.last_fallback_reason,
                )
            )
        else:
            mode = "stub" if src.is_stub else "never_refreshed"
            out.append(
                SourceHealthOut(
                    id=sid,
                    name=src.name,
                    mode=mode,
                    last_refresh_at=None,
                    last_status=None,
                    last_error=None,
                    is_stub=src.is_stub,
                    description=src.description,
                    homepage_url=src.homepage_url,
                    last_fallback_reason=None,
                )
            )
    # Sort: real adapters first, then stubs
    out.sort(key=lambda s: (s.is_stub, s.id))
    return out


@router.post("/sources/{source_id}/refresh")
def refresh_source(source_id: str, db: DbSession, payload: dict | None = None):
    src = SOURCES.get(source_id)
    if src is None:
        raise HTTPException(404, "source not found")
    payload = payload or {}

    n = 0
    errors = []

    if payload:
        try:
            items = src.fetch(**payload)
            n = ingest(db, src, items)
        except Exception as e:
            raise HTTPException(400, f"fetch failed: {e}") from e
    else:
        companies = db.scalars(select(Company)).all()
        for co in companies:
            try:
                if source_id.startswith("edgar"):
                    items = src.fetch(cik=co.cik, company_name=co.name)
                elif source_id == "news.google_rss":
                    items = src.fetch(query=co.name)
                elif source_id == "market.yfinance":
                    items = src.fetch(ticker=co.ticker)
                elif source_id == "macro.fred":
                    items = src.fetch()
                elif src.is_stub:
                    items = src.fetch()
                else:
                    continue
                n += ingest(db, src, items)
            except Exception as e:
                errors.append(f"{co.name}: {e}")

        if errors:
            raise HTTPException(400, f"partial fetch: {'; '.join(errors[:3])}")

    db.commit()
    return {
        "source": source_id,
        "ingested": n,
        "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@router.post("/sources/{source_id}/test", response_model=SourceTestOut)
def test_source(source_id: str, db: DbSession, payload: dict | None = None):
    """Force a live fetch attempt for a single source and return the raw result.

    This bypasses the database — it doesn't ingest anything, just tries to fetch
    and reports back exactly what came back. Lets the user verify whether a source
    is actually working live.
    """
    src = SOURCES.get(source_id)
    if src is None:
        raise HTTPException(404, "source not found")

    payload = payload or {}
    if src.is_stub:
        # Stubs always return placeholder. Skip the real call and report it clearly.
        return SourceTestOut(
            source_id=source_id,
            success=False,
            mode="stub",
            duration_ms=0,
            item_count=0,
            error="This source is a stub — adapter is not implemented.",
            fallback_reason=f"{src.name} adapter not yet implemented (stub)",
            tested_at=dt.datetime.now(dt.timezone.utc),
        )

    # Provide sensible default args per source for a quick smoke test
    test_payload = dict(payload)
    if not test_payload:
        if source_id.startswith("edgar"):
            # Microsoft as a known-good live test case
            test_payload = {"cik": "789019", "company_name": "MICROSOFT CORP", "api_mode": "offline"}
        elif source_id == "news.google_rss":
            test_payload = {"query": "mergers acquisitions"}
        elif source_id == "market.yfinance":
            test_payload = {"ticker": "MSFT", "api_mode": "offline"}
        elif source_id == "macro.fred":
            test_payload = {"series": "DGS10"}
        elif source_id == "reg.companies_house":
            test_payload = {"company_number": "00445790"}  # HSBC

    started = time.perf_counter()
    error: str | None = None
    items: list = []
    try:
        items = src.fetch(**test_payload)
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:500]}"
    duration_ms = int((time.perf_counter() - started) * 1000)

    if not items:
        return SourceTestOut(
            source_id=source_id,
            success=False,
            mode="blocked" if error else "live",
            duration_ms=duration_ms,
            item_count=0,
            error=error,
            fallback_reason=error,
            tested_at=dt.datetime.now(dt.timezone.utc),
        )

    first = items[0]
    actual_mode = first.mode.value if hasattr(first.mode, "value") else str(first.mode)
    success = actual_mode == "live" and error is None
    return SourceTestOut(
        source_id=source_id,
        success=success,
        mode=actual_mode,
        duration_ms=duration_ms,
        item_count=len(items),
        sample_title=first.title,
        sample_url=first.url,
        sample_snippet=first.snippet,
        sample_published_at=first.published_at,
        error=error,
        fallback_reason=getattr(first, "fallback_reason", None),
        tested_at=dt.datetime.now(dt.timezone.utc),
    )
