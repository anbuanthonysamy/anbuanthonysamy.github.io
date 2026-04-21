"""CS2 — Distressed carve-out detection.

Public-data only. Segment-level extraction from XBRL when available; falls
back to whole-company signals with lower confidence. Produces Situations
with value-at-stake low/mid/high bands.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Module
from app.models.orm import Company, Segment, Situation
from app.orchestrators.pipeline import ModulePipeline, PipelineRun
from app.signals.registry import load_signals

_SIGNALS_PATH = Path(__file__).parent.parent.parent / "signals" / "signals.yaml"


@dataclass
class CarveOutConfig:
    equity_floor_usd: float = 750_000_000
    elevated_threshold: float = 0.50


def build_pipeline(db: Session) -> ModulePipeline:
    all_sigs = load_signals(_SIGNALS_PATH)
    sigs = [s for s in all_sigs if s.module == Module.CARVE_OUTS.value]
    return ModulePipeline(db, Module.CARVE_OUTS.value, sigs)


def value_at_stake_bands(company: Company, segment: Segment | None) -> tuple[float, float, float]:
    """Crude public-proxy equity-value-at-stake range.

    Uses segment revenue x industry EV/revenue multiple if segment data
    exists, otherwise a fraction of company market cap.
    """
    if segment and segment.revenue_usd:
        mid = segment.revenue_usd * 1.5  # industry median EV/Rev
        return round(mid * 0.6, 0), round(mid, 0), round(mid * 1.5, 0)
    mcap = company.market_cap_usd or 0.0
    return round(mcap * 0.10, 0), round(mcap * 0.15, 0), round(mcap * 0.25, 0)


def run_for_all(
    db: Session, cfg: CarveOutConfig | None = None
) -> list[PipelineRun]:
    cfg = cfg or CarveOutConfig()
    pipeline = build_pipeline(db)
    out: list[PipelineRun] = []
    for co in db.scalars(select(Company)).all():
        segments = list(db.scalars(select(Segment).where(Segment.company_id == co.id)).all())
        if not segments:
            low, mid, high = value_at_stake_bands(co, None)
            run = pipeline.run_for_company(
                co,
                extras={
                    "sector": co.sector,
                    "kind": "company",
                    "value_low_usd": low,
                    "value_mid_usd": mid,
                    "value_high_usd": high,
                    "threshold": cfg.elevated_threshold,
                    "equity_floor_usd": cfg.equity_floor_usd,
                    "horizon_months": "6-18",
                },
                title=f"Carve-out situation: {co.name}",
            )
            # Value filter
            if mid < cfg.equity_floor_usd * 0.1:
                # Below $75m indicative — surface but suppress from top view
                run.situation.caveats = list(run.situation.caveats or []) + [
                    "Indicative value-at-stake below meaningful threshold."
                ]
            out.append(run)
            continue

        # One Situation per segment (more actionable for carve-out)
        for seg in segments:
            low, mid, high = value_at_stake_bands(co, seg)
            run = pipeline.run_for_company(
                co,
                extras={
                    "sector": co.sector,
                    "kind": "segment",
                    "segment_id": seg.id,
                    "segment_name": seg.name,
                    "value_low_usd": low,
                    "value_mid_usd": mid,
                    "value_high_usd": high,
                    "segment_margin": seg.margin,
                    "segment_margin_trend_1y": seg.margin_trend_1y,
                    "break_up_tree": _break_up_tree(co, seg),
                    "threshold": cfg.elevated_threshold,
                    "equity_floor_usd": cfg.equity_floor_usd,
                    "horizon_months": "6-18",
                },
                title=f"Carve-out candidate: {co.name} — {seg.name}",
            )
            # Tag the segment id on the Situation
            run.situation.segment_id = seg.id
            run.situation.kind = "segment"
            out.append(run)
    db.commit()
    return out


def _break_up_tree(co: Company, seg: Segment) -> list[dict]:
    """Simple logic tree from financial stress -> strategic divestment.
    Evidence ids are attached to nodes where available via extras."""
    nodes: list[dict] = [
        {"id": "stress", "label": "Balance-sheet stress", "children": ["refi", "rating"]},
        {"id": "refi", "label": "Refinancing window inside 6-18m"},
        {"id": "rating", "label": "Negative rating action"},
        {"id": "segment", "label": f"Segment underperformance: {seg.name}",
         "children": ["margin"]},
        {"id": "margin", "label": "Margin drift vs company"},
        {"id": "strategic", "label": "Strategic-review language / non-core framing",
         "children": ["divest"]},
        {"id": "divest", "label": "Divestment / carve-out of segment"},
    ]
    return nodes


def list_results(db: Session, module: str = Module.CARVE_OUTS.value) -> list[Situation]:
    return list(
        db.scalars(
            select(Situation)
            .where(Situation.module == module)
            .order_by(Situation.score.desc())
        ).all()
    )
