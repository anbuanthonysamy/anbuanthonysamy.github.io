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
from app.sources.registry import SourceRegistry


async def cs1_signal_scorer(
    company: Company, registry: SourceRegistry, db: Session
) -> tuple[float, dict]:
    """Score CS1 M&A origination signals (deterministic)."""
    signals = {}

    # 1. Market & Valuation: stock underperformance vs peers
    market_data = await registry.get_source("market").fetch(company.ticker)
    peer_perf = _get_peer_performance(company.sector, registry)
    underperformance_pct = _calculate_underperformance(market_data, peer_perf)
    signals["market_underperformance_pct"] = underperformance_pct

    # 2. PE multiple discount
    pe_discount = _calculate_pe_discount(company, registry)
    signals["pe_discount_pct"] = pe_discount

    # 3. Strategic performance: margin compression
    margin_data = await registry.get_source("edgar").fetch(company.ticker, "10-K")
    margin_compression = _calculate_margin_compression(margin_data, company.sector)
    signals["margin_compression_pct"] = margin_compression

    # 4. Leadership changes (from news/filings)
    news = await registry.get_source("news").fetch(company.ticker)
    leadership_change = _detect_leadership_change(news)
    signals["fresh_leadership_change"] = leadership_change

    # 5. Activist involvement (13D filings)
    activist = _detect_activist_involvement(margin_data)
    signals["active_13d_filing"] = activist

    # 6. Leverage stress: Net Debt / EBITDA > 3.5x
    leverage = _calculate_leverage_ratio(company, margin_data)
    signals["net_debt_ebitda"] = leverage

    # Composite score
    score = _score_cs1_composite(signals)

    return score, signals


async def cs2_signal_scorer(
    company: Company, registry: SourceRegistry, db: Session
) -> tuple[float, dict]:
    """Score CS2 carve-out signals (deterministic)."""
    signals = {}

    # 1. Balance sheet stress: Net debt escalation
    edgar_data = await registry.get_source("edgar").fetch(company.ticker, "10-K")
    debt_trend = _detect_debt_escalation(edgar_data)
    signals["balance_sheet_stress"] = debt_trend

    # 2. Segment underperformance
    segment_perf = _analyze_segment_performance(edgar_data, company.sector)
    signals["segment_underperformance"] = segment_perf

    # 3. Portfolio complexity: Conglomerate discount
    discount = _estimate_conglomerate_discount(edgar_data)
    signals["conglomerate_discount_pct"] = discount

    # 4. Separation feasibility (based on segment size, systems, contracts)
    feasibility = _estimate_separation_feasibility(edgar_data, company)
    signals["separation_readiness"] = feasibility

    # 5. Capital actions: Dividend suspension, equity issuance
    capital_actions = _detect_capital_actions(edgar_data)
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


def _get_peer_performance(sector: str, registry: SourceRegistry) -> float:
    """Get median peer stock performance (3-month return)."""
    # Stub: in reality, fetch peer list from market data
    return 0.05  # 5% baseline


def _calculate_underperformance(market_data: dict, peer_perf: float) -> float:
    """Return percentage underperformance vs peers."""
    company_perf = market_data.get("return_3m", 0.0)
    return max(0, (peer_perf - company_perf) * 100)


def _calculate_pe_discount(company: Company, registry: SourceRegistry) -> float:
    """Return PE discount vs sector median."""
    company_pe = company.current_pe_ratio or 0
    sector_pe = _get_sector_median_pe(company.sector)
    if sector_pe == 0:
        return 0
    return max(0, (1 - company_pe / sector_pe) * 100)


def _get_sector_median_pe(sector: str) -> float:
    """Get sector median PE ratio."""
    # Stub: return hardcoded sector medians
    sector_pes = {
        "Technology": 28,
        "Healthcare": 25,
        "Industrials": 18,
        "Consumer": 20,
    }
    return sector_pes.get(sector, 20)


def _calculate_margin_compression(edgar_data: dict, sector: str) -> float:
    """Return EBITDA margin compression vs sector."""
    company_margin = edgar_data.get("ebitda_margin", 0.15)
    sector_margin = _get_sector_median_margin(sector)
    return max(0, (sector_margin - company_margin) * 100)


def _get_sector_median_margin(sector: str) -> float:
    """Get sector median EBITDA margin."""
    margins = {
        "Technology": 0.30,
        "Healthcare": 0.28,
        "Industrials": 0.18,
        "Consumer": 0.15,
    }
    return margins.get(sector, 0.20)


def _detect_leadership_change(news: list[dict]) -> bool:
    """Detect if CEO/CFO appointed in last 6 months."""
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    for item in news:
        pub_date = item.get("published_at", datetime.utcnow())
        if pub_date > six_months_ago and any(
            x in item.get("title", "").lower() for x in ["ceo", "cfo", "appointed"]
        ):
            return True
    return False


def _detect_activist_involvement(edgar_data: dict) -> bool:
    """Detect 13D filing or activist mention in filings."""
    # Check for activist investor mentions, break-up narratives
    full_text = edgar_data.get("full_text", "").lower()
    activist_keywords = ["13d", "activist", "break-up", "strategic alternatives"]
    return any(kw in full_text for kw in activist_keywords)


def _calculate_leverage_ratio(company: Company, edgar_data: dict) -> float:
    """Calculate Net Debt / EBITDA ratio."""
    net_debt = edgar_data.get("net_debt", 0)
    ebitda = edgar_data.get("ebitda", 1)
    return net_debt / ebitda if ebitda > 0 else 0


def _detect_debt_escalation(edgar_data: dict) -> bool:
    """Detect increasing net debt over 3 years."""
    debt_trend = edgar_data.get("net_debt_3y_trend", [])
    if len(debt_trend) < 2:
        return False
    # Check if latest 2 years show increase
    return debt_trend[-1] > debt_trend[-2]


def _analyze_segment_performance(edgar_data: dict, sector: str) -> float:
    """Return segment underperformance score (0-1)."""
    # Check segment data for margin lag vs peers
    segments = edgar_data.get("segments", [])
    underperf_count = 0
    for seg in segments:
        seg_margin = seg.get("ebitda_margin", 0)
        peer_margin = _get_sector_median_margin(seg.get("sector", sector))
        if seg_margin < peer_margin:
            underperf_count += 1
    return underperf_count / len(segments) if segments else 0


def _estimate_conglomerate_discount(edgar_data: dict) -> float:
    """Estimate sum-of-parts valuation discount (%)."""
    # Simplified: if >3 segments with different margins, likely discount
    segments = edgar_data.get("segments", [])
    if len(segments) <= 1:
        return 0
    # Stub: return 15% discount for multi-segment conglomerates
    return 15.0


def _estimate_separation_feasibility(edgar_data: dict, company: Company) -> float:
    """Estimate separation readiness (0-1)."""
    # Check for: independent P&L, separate systems, contract assignability
    segments = edgar_data.get("segments", [])
    if not segments:
        return 0

    # Feasibility components
    systems_independent = edgar_data.get("separate_it_systems", False)
    standalone_revenue_pct = edgar_data.get("largest_segment_pct", 0)
    contracts_assignable = not edgar_data.get("shared_contracts", True)

    score = 0
    if standalone_revenue_pct > 0.15:
        score += 0.33
    if systems_independent:
        score += 0.33
    if contracts_assignable:
        score += 0.34

    return score


def _detect_capital_actions(edgar_data: dict) -> bool:
    """Detect dividend suspension, equity issuance, or asset sales."""
    text = edgar_data.get("full_text", "").lower()
    capital_keywords = [
        "dividend suspended",
        "equity issuance",
        "asset sale",
        "debt amendment",
    ]
    return any(kw in text for kw in capital_keywords)


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
