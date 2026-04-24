"""SQLAlchemy ORM models — canonical persistence layer.

Every surfaced output is derived from rows in these tables. The Evidence
table is the root of trust: nothing is shown in the UI that is not backed
by at least one Evidence row.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    CurveShape,
    DataScope,
    Geography,
    Module,
    ReviewState,
    SituationKind,
    SourceMode,
    Tier,
    TierColour,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Company(Base):
    __tablename__ = "company"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    cik: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    ticker: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    lei: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    company_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_debt_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    segments: Mapped[list[Segment]] = relationship(back_populates="company")

    @property
    def equity_value(self) -> float:
        """Estimated equity value (market cap or enterprise value - net debt)."""
        return self.market_cap_usd or 0.0


class Segment(Base):
    __tablename__ = "segment"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    reported_since: Mapped[dt.date | None] = mapped_column(DateTime, nullable=True)
    revenue_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_trend_1y: Mapped[float | None] = mapped_column(Float, nullable=True)

    company: Mapped[Company] = relationship(back_populates="segments")


class Filing(Base):
    __tablename__ = "filing"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), index=True)
    form: Mapped[str] = mapped_column(String, index=True)  # 10-K, 10-Q, 8-K, 13D, DEF14A
    accession: Mapped[str] = mapped_column(String, unique=True, index=True)
    filed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    url: Mapped[str] = mapped_column(String)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketDataPoint(Base):
    __tablename__ = "market_data"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("company.id"), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    close_usd: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    market_cap_usd: Mapped[float | None] = mapped_column(Float)


class NewsItem(Base):
    __tablename__ = "news_item"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("company.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    published_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    hash: Mapped[str] = mapped_column(String, unique=True, index=True)


class Source(Base):
    __tablename__ = "source"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. edgar.submissions
    name: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String, default=SourceMode.FIXTURE.value)
    last_refresh_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Evidence(Base):
    """Root of trust. Every score/explanation cites Evidence IDs."""

    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String, index=True)  # e.g. edgar.submissions
    scope: Mapped[str] = mapped_column(String, default=DataScope.PUBLIC.value, index=True)
    mode: Mapped[str] = mapped_column(String, default=SourceMode.LIVE.value)

    company_id: Mapped[str | None] = mapped_column(ForeignKey("company.id"), index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String)
    file_ref: Mapped[str | None] = mapped_column(String)

    retrieved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    parsed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    sha256: Mapped[str] = mapped_column(String, index=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (UniqueConstraint("sha256", name="uq_evidence_sha"),)


class Signal(Base):
    __tablename__ = "signal"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    module: Mapped[str] = mapped_column(String, index=True)
    signal_key: Mapped[str] = mapped_column(String, index=True)  # e.g. activist_13d
    company_id: Mapped[str | None] = mapped_column(ForeignKey("company.id"), index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("segment.id"), index=True)
    strength: Mapped[float] = mapped_column(Float)  # 0..1
    confidence: Mapped[float] = mapped_column(Float)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class Situation(Base):
    """Generic flagged thing — Opportunity (CS1), Carve-out (CS2),
    Deviation (CS3), Recommendation (CS4)."""

    __tablename__ = "situation"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    module: Mapped[str] = mapped_column(String, index=True)  # Module enum
    kind: Mapped[str] = mapped_column(String, default=SituationKind.COMPANY.value)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("company.id"), index=True)
    segment_id: Mapped[str | None] = mapped_column(ForeignKey("segment.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    caveats: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Scoring
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    signal_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Explanation
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_cites: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Module-specific extras (e.g. value_at_stake_low/mid/high, DSO, ...)
    extras: Mapped[dict] = mapped_column(JSON, default=dict)

    # v2 Continuous Scanning Extensions
    tier: Mapped[str | None] = mapped_column(String, nullable=True, index=True)  # Tier enum
    signals: Mapped[dict] = mapped_column(JSON, default=dict)  # Deterministic signals (no LLM)
    score_delta: Mapped[float] = mapped_column(Float, default=0.0)  # Change since last scan
    first_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Review
    review_state: Mapped[str] = mapped_column(String, default=ReviewState.PENDING.value)
    reviewer: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def tier_colour(self) -> str:
        """Return colour based on tier."""
        if self.tier and "p1" in self.tier.lower():
            return TierColour.RED.value
        elif self.tier and "p2" in self.tier.lower():
            return TierColour.AMBER.value
        else:
            return TierColour.GREEN.value


class Review(Base):
    """Audit log of every review decision."""

    __tablename__ = "review"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    situation_id: Mapped[str] = mapped_column(ForeignKey("situation.id"), index=True)
    reviewer: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)  # accept|reject|edit|approve
    reason: Mapped[str] = mapped_column(Text)
    rating_1_to_10: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edit_patch: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SettingKV(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LLMCall(Base):
    __tablename__ = "llm_call"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String)  # extract|synthesize
    model: Mapped[str] = mapped_column(String)
    offline: Mapped[bool] = mapped_column(Boolean, default=True)
    prompt_hash: Mapped[str] = mapped_column(String, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Upload(Base):
    """A client-scoped upload (CS3/CS4)."""

    __tablename__ = "upload"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    module: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # deal_case | ar | ap | inventory | kpi_actual
    filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    rows: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    uploaded_by: Mapped[str | None] = mapped_column(String, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class KPI(Base):
    """A measurable metric — for CS3 (deal-case) and CS4 (working capital)."""

    __tablename__ = "kpi"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    module: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    unit: Mapped[str] = mapped_column(String)
    curve: Mapped[str] = mapped_column(String, default=CurveShape.LINEAR.value)
    target_band_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_band_mid: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_band_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_start: Mapped[dt.date | None] = mapped_column(DateTime, nullable=True)
    target_end: Mapped[dt.date | None] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class KPIActual(Base):
    __tablename__ = "kpi_actual"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kpi_id: Mapped[str] = mapped_column(ForeignKey("kpi.id"), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    value: Mapped[float] = mapped_column(Float)


class Benchmark(Base):
    __tablename__ = "benchmark"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    module: Mapped[str] = mapped_column(String, index=True)
    sector: Mapped[str] = mapped_column(String, index=True)
    metric: Mapped[str] = mapped_column(String, index=True)  # DSO, DPO, DIO, ...
    p40: Mapped[float] = mapped_column(Float)
    p50: Mapped[float] = mapped_column(Float)
    p60: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
