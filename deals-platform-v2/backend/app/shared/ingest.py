"""Ingestion — map RawItems from sources into Evidence rows and update
Source health."""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Company, Source as SourceRow
from app.shared.evidence import upsert_evidence
from app.sources.base import RawItem, Source

log = logging.getLogger(__name__)


def ingest(db: Session, source: Source, items: list[RawItem]) -> int:
    count = 0
    company_cache: dict[tuple[str | None, str | None], Company | None] = {}
    # Aggregate the most informative mode and fallback_reason across items
    # so the Source health row reflects the actual fetch result.
    modes_seen: set[str] = set()
    fallback_reasons: list[str] = []
    for it in items:
        co = None
        key = (it.company_cik, it.company_ticker)
        if key not in company_cache:
            q = select(Company)
            if it.company_cik:
                q = q.where(Company.cik == it.company_cik)
            elif it.company_ticker:
                q = q.where(Company.ticker == it.company_ticker)
            elif it.company_name:
                q = q.where(Company.name == it.company_name)
            else:
                q = None
            company_cache[key] = db.scalar(q) if q is not None else None
        co = company_cache[key]
        if co is None and (it.company_name or it.company_cik or it.company_ticker):
            co = Company(
                cik=it.company_cik,
                ticker=it.company_ticker,
                name=it.company_name or it.company_ticker or it.company_cik or "Unknown",
                market_cap_usd=(it.meta or {}).get("market_cap"),
            )
            db.add(co)
            db.flush()
            company_cache[key] = co

        upsert_evidence(
            db,
            source_id=it.source_id,
            scope=it.scope,
            mode=it.mode,
            kind=it.kind,
            title=it.title,
            snippet=it.snippet,
            url=it.url,
            company_id=co.id if co else None,
            published_at=it.published_at,
            meta=it.meta or {},
            fallback_reason=it.fallback_reason,
        )
        modes_seen.add(it.mode.value)
        if it.fallback_reason and it.fallback_reason not in fallback_reasons:
            fallback_reasons.append(it.fallback_reason)
        count += 1

    # Pick the worst mode seen for source-level reporting. Order: live > fixture > stub > blocked
    aggregate_mode = "live"
    if "blocked" in modes_seen:
        aggregate_mode = "blocked"
    elif "stub" in modes_seen:
        aggregate_mode = "stub"
    elif "fixture" in modes_seen:
        aggregate_mode = "fixture"
    elif "live" in modes_seen:
        aggregate_mode = "live"

    _update_source_health(
        db,
        source.id,
        source.name,
        status="ok",
        count=count,
        mode=aggregate_mode,
        fallback_reason="; ".join(fallback_reasons[:3]) if fallback_reasons else None,
    )
    return count


def _update_source_health(
    db: Session,
    source_id: str,
    name: str,
    *,
    status: str,
    count: int,
    mode: str = "live",
    fallback_reason: str | None = None,
) -> None:
    row = db.scalar(select(SourceRow).where(SourceRow.id == source_id))
    if row is None:
        row = SourceRow(id=source_id, name=name, mode=mode)
        db.add(row)
    row.last_refresh_at = dt.datetime.now(dt.timezone.utc)
    row.last_status = f"{status} ({count} items)"
    row.last_error = None
    row.mode = mode
    row.last_fallback_reason = fallback_reason
    db.flush()


def record_source_error(db: Session, source_id: str, err: str) -> None:
    row = db.scalar(select(SourceRow).where(SourceRow.id == source_id))
    if row is None:
        row = SourceRow(id=source_id, name=source_id, mode="fixture")
        db.add(row)
    row.last_refresh_at = dt.datetime.now(dt.timezone.utc)
    row.last_status = "error"
    row.last_error = err[:2000]
    row.last_fallback_reason = err[:500]
    db.flush()
