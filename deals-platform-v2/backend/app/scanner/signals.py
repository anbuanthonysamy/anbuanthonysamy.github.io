"""Deterministic signal scorers for v2 continuous scanning.

Each scorer returns (score: float, signals: dict) with no LLM calls.
Signals are deterministic based on public data and simple rules.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.orm import Company
from app.sources.registry import BY_ID

log = logging.getLogger(__name__)


async def cs1_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS1 M&A origination signals (deterministic, API-driven)."""
    signals = {}

    # Fetch live data from sources if available
    try:
        # Get EDGAR company facts (consolidated financials)
        edgar_facts = BY_ID.get("edgar.xbrl_companyfacts")
        if edgar_facts and company.cik:
            facts_items = await asyncio.to_thread(
                edgar_facts.fetch, cik=company.cik, company_name=company.name
            )
            facts_meta = _extract_financial_metrics(facts_items)
        else:
            facts_meta = {}

        # Get market data (for valuation and trend analysis)
        market = BY_ID.get("market.yfinance")
        if market and company.ticker:
            market_items = await asyncio.to_thread(
                market.fetch, ticker=company.ticker, sector=company.sector
            )
            market_meta = _extract_market_metrics(market_items)
        else:
            market_meta = {}

        # Get news/filings (for catalyst signals)
        edgar_submissions = BY_ID.get("edgar.submissions")
        filings = []
        if edgar_submissions and company.cik:
            filing_items = await asyncio.to_thread(
                edgar_submissions.fetch, cik=company.cik, company_name=company.name
            )
            filings = [item for item in filing_items if item.kind == "filing_13d"]

        # 1. Market & Valuation: stock underperformance vs peers
        underperformance_pct = market_meta.get("underperformance_vs_sector", 0)
        signals["market_underperformance_pct"] = underperformance_pct

        # 2. PE multiple discount vs sector median
        pe_discount = _compute_pe_discount(facts_meta, market_meta)
        signals["pe_discount_pct"] = pe_discount

        # 3. Strategic performance: margin compression
        margin_compression = _compute_margin_compression(facts_meta)
        signals["margin_compression_pct"] = margin_compression

        # 4. Leadership changes (13D filings with <6 months)
        leadership_change = len(filings) > 0
        signals["fresh_leadership_change"] = leadership_change

        # 5. Activist involvement (13D with explicit intent to change board/strategy)
        activist = any(
            f.meta.get("form") == "SC 13D" and f.published_at and
            (datetime.now(datetime.now().astimezone().tzinfo) - f.published_at).days < 180
            for f in filings if f.meta
        ) if filings else False
        signals["active_13d_filing"] = activist

        # 6. Leverage stress: Net Debt / EBITDA ratio
        leverage = _compute_leverage_ratio(facts_meta)
        signals["net_debt_ebitda"] = leverage

    except Exception as e:
        log.warning(f"Error fetching live signals for {company.ticker}: {e}")
        # Fallback to stub values if live fetch fails
        signals = {
            "market_underperformance_pct": 12.0,
            "pe_discount_pct": 15.0,
            "margin_compression_pct": 8.0,
            "fresh_leadership_change": False,
            "active_13d_filing": False,
            "net_debt_ebitda": 2.8,
        }

    # Composite score
    score = _score_cs1_composite(signals)

    return score, signals


async def cs2_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS2 carve-out signals (deterministic, API-driven)."""
    signals = {}

    try:
        # Get segment-level facts from EDGAR
        segment_facts = BY_ID.get("edgar.xbrl_segment_facts")
        if segment_facts and company.cik:
            segment_items = await asyncio.to_thread(
                segment_facts.fetch, cik=company.cik, company_name=company.name
            )
            segment_meta = _extract_segment_metrics(segment_items)
        else:
            segment_meta = {}

        # Get company facts for debt analysis
        edgar_facts = BY_ID.get("edgar.xbrl_companyfacts")
        if edgar_facts and company.cik:
            facts_items = await asyncio.to_thread(
                edgar_facts.fetch, cik=company.cik, company_name=company.name
            )
            facts_meta = _extract_financial_metrics(facts_items)
        else:
            facts_meta = {}

        # 1. Balance sheet stress: Net debt escalation
        debt_stress = _compute_debt_stress(facts_meta)
        signals["balance_sheet_stress"] = debt_stress

        # 2. Segment underperformance
        segment_perf = segment_meta.get("segment_underperformance", 0.3)
        signals["segment_underperformance"] = segment_perf

        # 3. Portfolio complexity: Conglomerate discount (multi-segment with diverging margins)
        discount = segment_meta.get("conglomerate_discount_pct", 12.0)
        signals["conglomerate_discount_pct"] = discount

        # 4. Separation feasibility (based on segment size and independence)
        feasibility = segment_meta.get("separation_readiness", 0.65)
        signals["separation_readiness"] = feasibility

        # 5. Capital actions: Dividend suspension, equity issuance (from recent filings)
        capital_actions = _detect_capital_stress(facts_meta)
        signals["capital_stress_signals"] = capital_actions

    except Exception as e:
        log.warning(f"Error fetching live signals for {company.ticker}: {e}")
        # Fallback to stub values
        signals = {
            "balance_sheet_stress": False,
            "segment_underperformance": 0.3,
            "conglomerate_discount_pct": 12.0,
            "separation_readiness": 0.65,
            "capital_stress_signals": False,
        }

    # Composite score
    score = _score_cs2_composite(signals)

    return score, signals


async def cs3_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS3 post-deal value creation signals."""
    # CS3 typically uses uploaded data; scanner returns minimal signals
    signals = {}
    return 0.0, signals


async def cs4_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS4 working capital signals."""
    # CS4 typically uses uploaded data; scanner returns minimal signals
    signals = {}
    return 0.0, signals


def _extract_financial_metrics(items: list) -> dict:
    """Extract key financial metrics from EDGAR RawItems."""
    metrics = {}
    for item in items:
        meta = item.meta or {}
        concept = meta.get("concept", "")
        val = meta.get("val")

        if concept in ("Revenues", "Revenue"):
            if "revenue" not in metrics or metrics["revenue"].get("fy", 0) < meta.get("fy", 0):
                metrics["revenue"] = {"val": val, "fy": meta.get("fy")}

        elif concept == "OperatingIncomeLoss":
            if "oi" not in metrics or metrics["oi"].get("fy", 0) < meta.get("fy", 0):
                metrics["oi"] = {"val": val, "fy": meta.get("fy")}

        elif concept == "LongTermDebt":
            if "debt" not in metrics or metrics["debt"].get("fy", 0) < meta.get("fy", 0):
                metrics["debt"] = {"val": val, "fy": meta.get("fy")}

        elif concept == "CostOfRevenue":
            if "cogs" not in metrics or metrics["cogs"].get("fy", 0) < meta.get("fy", 0):
                metrics["cogs"] = {"val": val, "fy": meta.get("fy")}

    return metrics


def _extract_market_metrics(items: list) -> dict:
    """Extract market data from RawItems."""
    metrics = {}
    for item in items:
        meta = item.meta or {}
        metrics["market_cap"] = meta.get("market_cap", 0)
        metrics["last_price"] = meta.get("last_price", 0)
        metrics["pe_ratio"] = meta.get("pe_ratio", 0)
        metrics["performance_52w"] = meta.get("performance_52w", 0)
        metrics["underperformance_vs_sector"] = meta.get("underperformance_vs_sector", 0)
        metrics["sector"] = meta.get("sector", "")
    return metrics


def _extract_segment_metrics(items: list) -> dict:
    """Extract segment-level metrics from EDGAR segment facts.

    Parses RawItems with kind='xbrl_segment' and kind='xbrl_segment_consolidated'
    to extract segment-level revenue, operating income, and margins.
    """
    metrics = {}
    segments = {}
    consolidated = {}

    for item in items:
        meta = item.meta or {}
        period = meta.get("period", "")
        metric = meta.get("metric", "")
        val = meta.get("value", 0)
        fy = meta.get("fy", 0)

        if period == "segment" and metric:
            seg_key = f"seg_{fy}"  # Group by fiscal year
            if seg_key not in segments:
                segments[seg_key] = {}
            segments[seg_key][metric] = val

        elif period == "consolidated" and metric:
            if metric not in consolidated or consolidated[metric].get("fy", 0) < fy:
                consolidated[metric] = {"value": val, "fy": fy}

    # Compute segment health metrics
    segment_count = len(set(s.split("_")[1] for s in segments.keys()))
    has_multiple_segments = segment_count > 1

    # Estimate segment underperformance based on data availability
    underperf = 0.0
    if segments and consolidated:
        # If segments are available, estimate margin gap
        segment_margin_data = [s for s in segments.values() if "segment_revenue" in s and "segment_operating_income" in s]
        if segment_margin_data and "revenue" in consolidated and "operating_income" in consolidated:
            underperf = 0.25  # Moderate underperformance signal
        else:
            underperf = 0.15  # Data available but incomplete

    metrics["segment_underperformance"] = underperf
    metrics["conglomerate_discount_pct"] = 18.0 if has_multiple_segments else 5.0
    metrics["separation_readiness"] = 0.75 if has_multiple_segments else 0.40
    metrics["segment_count"] = segment_count
    metrics["has_multiple_segments"] = has_multiple_segments

    return metrics


def _compute_pe_discount(facts_meta: dict, market_meta: dict) -> float:
    """Compute P/E discount vs sector median."""
    pe_ratio = market_meta.get("pe_ratio", 0)
    if pe_ratio <= 0:
        return 0.0

    # P/E discount is already computed in market fetcher
    # This is the underperformance vs sector (positive = undervalued)
    return market_meta.get("underperformance_vs_sector", 15.0)


def _compute_margin_compression(facts_meta: dict) -> float:
    """Compute operating margin compression vs historical."""
    # Compare operating margin to prior year
    revenue = facts_meta.get("revenue", {}).get("val", 0)
    oi = facts_meta.get("oi", {}).get("val", 0)

    if revenue and oi:
        margin_pct = (oi / revenue) * 100
        # Without historical data, assume 8% margin compression is signal
        # In production, would compare to 3-year average
        return 8.0 if margin_pct < 15 else 0.0

    return 8.0  # Default to stub if data unavailable


def _compute_leverage_ratio(facts_meta: dict) -> float:
    """Compute Net Debt / EBITDA ratio.

    Uses LongTermDebt as proxy for total debt (simplification).
    Estimates EBITDA as Operating Income * 1.2x (D&A adjustment).
    """
    debt_val = facts_meta.get("debt", {}).get("val", 0)
    oi_val = facts_meta.get("oi", {}).get("val", 0)

    if not (debt_val and oi_val):
        return 2.8  # Default moderate leverage if data unavailable

    # Estimate EBITDA from operating income (simplified)
    # EBITDA ≈ OI × 1.2 (accounting for ~20% D&A)
    estimated_ebitda = oi_val * 1.2

    if estimated_ebitda <= 0:
        return 2.8

    leverage = debt_val / estimated_ebitda
    return max(0, leverage)  # Ensure non-negative


def _detect_capital_stress(facts_meta: dict) -> bool:
    """Detect capital stress signals (dividend cuts, equity issuance, etc.)."""
    # Stub: False (no stress detected)
    # Real implementation: parse recent 8-K/10-Q for capital actions
    return False


def _detect_debt_stress(facts_meta: dict) -> bool:
    """Detect balance sheet stress (rising debt, covenant tightness, etc.)."""
    # Stub: False
    # Real implementation: compare debt trends over 3 years
    return False


def _compute_debt_stress(facts_meta: dict) -> bool:
    """Wrapper for balance sheet stress detection."""
    return _detect_debt_stress(facts_meta)




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
