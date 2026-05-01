"""Pydantic schemas for the API boundary.

Keep these in sync with SQLAlchemy ORM in orm.py. These are what the UI
consumes. All money is USD. Every surfaced item carries `evidence[]` and
`review{}` — the shared output contract from the wrapper prompt.
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class EvidenceOut(BaseModel):
    id: str
    source_id: str
    scope: str
    mode: str
    kind: str
    title: str
    snippet: str | None = None
    url: str | None = None
    file_ref: str | None = None
    retrieved_at: dt.datetime
    parsed_at: dt.datetime | None = None
    published_at: dt.datetime | None = None
    ok: bool = True
    fallback_reason: str | None = None
    meta: dict = Field(default_factory=dict)


class ReviewOut(BaseModel):
    state: str
    reviewer: str | None = None
    ts: dt.datetime | None = None
    reason: str | None = None


class SignalOut(BaseModel):
    id: str
    module: str
    signal_key: str
    strength: float
    confidence: float
    detected_at: dt.datetime
    evidence_ids: list[str] = Field(default_factory=list)
    detail: dict = Field(default_factory=dict)


class SituationOut(BaseModel):
    id: str
    module: str
    kind: str
    company_id: str | None = None
    segment_id: str | None = None
    title: str
    summary: str | None = None
    next_action: str | None = None
    caveats: list[str] = Field(default_factory=list)

    score: float
    dimensions: dict = Field(default_factory=dict)
    weights: dict = Field(default_factory=dict)
    confidence: float

    signal_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)

    explanation: str | None = None
    explanation_cites: list[str] = Field(default_factory=list)

    extras: dict = Field(default_factory=dict)
    review: ReviewOut

    created_at: dt.datetime


class ReviewRequest(BaseModel):
    reviewer: str
    action: str  # accept|reject|edit|approve
    reason: str
    rating_1_to_10: int | None = None
    edit_patch: dict = Field(default_factory=dict)


class CompanyOut(BaseModel):
    id: str
    cik: str | None = None
    ticker: str | None = None
    name: str
    sector: str | None = None
    country: str | None = None
    market_cap_usd: float | None = None


class SectorHeatCell(BaseModel):
    sector: str
    count: int
    avg_score: float
    top_situation_ids: list[str] = Field(default_factory=list)


class SourceHealthOut(BaseModel):
    id: str
    name: str
    mode: str
    last_refresh_at: dt.datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    is_stub: bool = False
    description: str = ""
    homepage_url: str | None = None
    last_fallback_reason: str | None = None


class SourceTestOut(BaseModel):
    """Result of GET /sources/{id}/test — forces a live fetch attempt."""
    source_id: str
    success: bool
    mode: str  # "live" if real data, "fixture" / "stub" if not
    duration_ms: int
    item_count: int
    sample_title: str | None = None
    sample_url: str | None = None
    sample_snippet: str | None = None
    sample_published_at: dt.datetime | None = None
    error: str | None = None
    fallback_reason: str | None = None
    tested_at: dt.datetime


class SettingOut(BaseModel):
    key: str
    value: dict
    updated_at: dt.datetime


class UploadOut(BaseModel):
    id: str
    module: str
    kind: str
    filename: str
    rows: int
    uploaded_at: dt.datetime
    uploaded_by: str | None = None


class KPIOut(BaseModel):
    id: str
    module: str
    name: str
    unit: str
    curve: str
    target_band_low: float | None = None
    target_band_mid: float | None = None
    target_band_high: float | None = None
    target_start: dt.datetime | None = None
    target_end: dt.datetime | None = None


class KPIWithActualsOut(KPIOut):
    actuals: list[tuple[dt.datetime, float]] = Field(default_factory=list)
    target_curve: list[tuple[dt.datetime, float, float, float]] = Field(
        default_factory=list,
        description="(ts, low, mid, high) at each point",
    )
