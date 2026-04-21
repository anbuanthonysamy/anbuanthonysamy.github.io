"""Deterministic signal scorers for v2 continuous scanning.

Each scorer returns (score: float, signals: dict) with no LLM calls.
Signals are deterministic based on public data and simple rules.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.orm import Company


async def cs1_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS1 M&A origination signals (deterministic)."""
    signals = {}

    # Stub implementations - deterministic signals without API calls
    # In offline mode, use seeded/default values
    # In live mode, would fetch real data (not implemented yet)

    # 1. Market & Valuation: stock underperformance vs peers
    underperformance_pct = 12.0  # Stub value
    signals["market_underperformance_pct"] = underperformance_pct

    # 2. PE multiple discount
    pe_discount = 15.0  # Stub value
    signals["pe_discount_pct"] = pe_discount

    # 3. Strategic performance: margin compression
    margin_compression = 8.0  # Stub value
    signals["margin_compression_pct"] = margin_compression

    # 4. Leadership changes (from news/filings)
    leadership_change = False  # Stub value
    signals["fresh_leadership_change"] = leadership_change

    # 5. Activist involvement (13D filings)
    activist = False  # Stub value
    signals["active_13d_filing"] = activist

    # 6. Leverage stress: Net Debt / EBITDA > 3.5x
    leverage = 2.8  # Stub value
    signals["net_debt_ebitda"] = leverage

    # Composite score
    score = _score_cs1_composite(signals)

    return score, signals


async def cs2_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS2 carve-out signals (deterministic)."""
    signals = {}

    # Stub implementations - deterministic signals without API calls
    # In offline mode, use seeded/default values
    # In live mode, would fetch real data (not implemented yet)

    # 1. Balance sheet stress: Net debt escalation
    debt_trend = False  # Stub value
    signals["balance_sheet_stress"] = debt_trend

    # 2. Segment underperformance
    segment_perf = 0.3  # Stub value (0-1 scale)
    signals["segment_underperformance"] = segment_perf

    # 3. Portfolio complexity: Conglomerate discount
    discount = 12.0  # Stub value
    signals["conglomerate_discount_pct"] = discount

    # 4. Separation feasibility (based on segment size, systems, contracts)
    feasibility = 0.65  # Stub value (0-1 scale)
    signals["separation_readiness"] = feasibility

    # 5. Capital actions: Dividend suspension, equity issuance
    capital_actions = False  # Stub value
    signals["capital_stress_signals"] = capital_actions

    # Composite score
    score = _score_cs2_composite(signals)

    return score, signals


async def cs3_signal_scorer(
    company: Company, registry: SourceRegistry, db: Session
) -> tuple[float, dict]:
    """Score CS3 post-deal value creation signals."""
    # CS3 typically uses uploaded data; scanner returns minimal signals
    signals = {}
    return 0.0, signals


async def cs4_signal_scorer(
    company: Company, registry: SourceRegistry, db: Session
) -> tuple[float, dict]:
    """Score CS4 working capital signals."""
    # CS4 typically uses uploaded data; scanner returns minimal signals
    signals = {}
    return 0.0, signals




def _score_cs1_composite(signals: dict) -> float:
    """Composite score for CS1 based on signals."""
    # Normalized signals (0-1)
    underperf = min(signals.get("market_underperformance_pct", 0) / 30, 1.0)
    pe_disc = min(signals.get("pe_discount_pct", 0) / 40, 1.0)
    margin = min(signals.get("margin_compression_pct", 0) / 30, 1.0)
    leverage = min(signals.get("net_debt_ebitda", 0) / 5.0, 1.0)
    leadership = 0.5 if signals.get("fresh_leadership_change", False) else 0
    activist = 0.7 if signals.get("active_13d_filing", False) else 0

    # Weighted composite
    score = (
        underperf * 0.15
        + pe_disc * 0.15
        + margin * 0.15
        + leverage * 0.20
        + leadership * 0.15
        + activist * 0.20
    )

    return min(score, 1.0)


def _score_cs2_composite(signals: dict) -> float:
    """Composite score for CS2 based on signals."""
    # Normalized signals
    debt_stress = 0.5 if signals.get("balance_sheet_stress", False) else 0
    segment_perf = signals.get("segment_underperformance", 0)
    discount = min(signals.get("conglomerate_discount_pct", 0) / 20, 1.0)
    separation = signals.get("separation_readiness", 0)
    capital_stress = 0.4 if signals.get("capital_stress_signals", False) else 0

    # Weighted composite
    score = (
        debt_stress * 0.20
        + segment_perf * 0.20
        + discount * 0.20
        + separation * 0.25
        + capital_stress * 0.15
    )

    return min(score, 1.0)
