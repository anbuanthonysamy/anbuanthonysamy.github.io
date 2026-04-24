"""CS1 — M&A Origination service.

Public-data only. Universe filter by market-cap > $1bn (configurable).
Elevated-likelihood threshold controls the pipeline cut.

This module imports ONLY from shared/public helpers. The segregation
test walks imports and fails CI if a client-only module is imported
here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Module
from app.models.orm import Company
from app.orchestrators.pipeline import ModulePipeline, PipelineRun
from app.signals.registry import load_signals

_SIGNALS_PATH = Path(__file__).parent.parent.parent / "signals" / "signals.yaml"


@dataclass
class OriginationConfig:
    market_cap_floor_usd: float = 1_000_000_000
    elevated_threshold: float = 0.55


def build_pipeline(db: Session) -> ModulePipeline:
    all_sigs = load_signals(_SIGNALS_PATH)
    sigs = [s for s in all_sigs if s.module == Module.ORIGINATION.value]
    return ModulePipeline(db, Module.ORIGINATION.value, sigs)


def universe(db: Session, floor: float) -> list[Company]:
    return list(
        db.scalars(
            select(Company).where(Company.market_cap_usd.isnot(None)).where(
                Company.market_cap_usd >= floor
            )
        ).all()
    )


def run_for_all(
    db: Session, cfg: OriginationConfig | None = None
) -> list[PipelineRun]:
    cfg = cfg or OriginationConfig()
    pipeline = build_pipeline(db)
    results: list[PipelineRun] = []
    for co in universe(db, cfg.market_cap_floor_usd):
        run = pipeline.run_for_company(
            co,
            extras={
                "sector": co.sector,
                "threshold": cfg.elevated_threshold,
                "mcap_floor": cfg.market_cap_floor_usd,
                "horizon_months": "12-24",
            },
            title=f"M&A opportunity: {co.name}",
        )
        results.append(run)
    db.commit()
    return results
