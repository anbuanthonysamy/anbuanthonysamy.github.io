"""Evidence store — upsert, fetch and expand."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import DataScope, SourceMode
from app.models.orm import Evidence
from app.shared.hashing import evidence_hash


def upsert_evidence(
    db: Session,
    *,
    source_id: str,
    scope: DataScope,
    mode: SourceMode,
    kind: str,
    title: str,
    snippet: str | None = None,
    url: str | None = None,
    file_ref: str | None = None,
    company_id: str | None = None,
    published_at: dt.datetime | None = None,
    meta: dict | None = None,
    ok: bool = True,
) -> Evidence:
    sha = evidence_hash(
        source_id,
        title,
        url,
        published_at.isoformat() if published_at else None,
    )
    existing = db.scalar(select(Evidence).where(Evidence.sha256 == sha))
    if existing:
        existing.retrieved_at = dt.datetime.now(dt.timezone.utc)
        existing.parsed_at = existing.parsed_at or existing.retrieved_at
        return existing

    ev = Evidence(
        source_id=source_id,
        scope=scope.value,
        mode=mode.value,
        kind=kind,
        title=title[:2000],
        snippet=(snippet or "")[:4000] or None,
        url=url,
        file_ref=file_ref,
        company_id=company_id,
        published_at=published_at,
        parsed_at=dt.datetime.now(dt.timezone.utc),
        sha256=sha,
        ok=ok,
        meta=meta or {},
    )
    db.add(ev)
    db.flush()
    return ev


def expand_evidence(db: Session, ids: list[str]) -> list[Evidence]:
    if not ids:
        return []
    rows = db.scalars(select(Evidence).where(Evidence.id.in_(ids))).all()
    order = {i: n for n, i in enumerate(ids)}
    return sorted(rows, key=lambda e: order.get(e.id, 999))
