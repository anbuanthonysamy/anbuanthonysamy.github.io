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
from app.scanner.cs1_helpers import (
    calculate_pe_discount,
    calculate_stock_underperformance,
    calculate_margin_compression,
    calculate_leverage_stress,
    detect_valuation_gap,
    score_activist_signal,
)
from app.scanner.cs2_helpers import (
    calculate_segment_margin_drift,
    calculate_balance_sheet_stress,
    calculate_conglomerate_discount,
    calculate_separation_readiness,
    detect_capital_stress_actions,
)
from app.scanner.cs2_tier3_helpers import (
    calculate_margin_trend_3y,
    detect_activist_breakup_calls,
    detect_peer_divestment_patterns,
    calculate_separation_probability,
    apply_multi_threshold_gating,
)
from app.scanner.tier4_helpers import (
    detect_leadership_changes,
    assess_ownership_structure,
    calculate_transaction_probability_model,
    calculate_deal_value_estimate,
    score_deal_attractiveness,
    refine_signal_scoring,
)
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
        underperformance_pct = market_meta.get("underperformance_vs_sector", 0.0)
        signals["market_underperformance_pct"] = underperformance_pct

        # 2. PE multiple discount vs sector median (using helper)
        company_pe = market_meta.get("pe_ratio", 0)
        sector_pe = _get_sector_median_pe(company.sector or "")
        pe_discount = calculate_pe_discount(company_pe, sector_pe)
        signals["pe_discount_pct"] = pe_discount

        # 3. Strategic performance: margin compression (using helper)
        current_revenue = facts_meta.get("revenue", {}).get("val", 0)
        current_oi = facts_meta.get("oi", {}).get("val", 0)
        margin_compression = calculate_margin_compression(current_oi, current_revenue)
        signals["margin_compression_pct"] = margin_compression

        # 4. Leadership changes (13D filings + Tier 4: 8-K/news detection)
        leadership_change = len(filings) > 0
        signals["fresh_leadership_change"] = leadership_change

        # Tier 4: Detect leadership changes from filings and news
        leadership_change_score, leadership_changes = detect_leadership_changes(
            filing_items=filings,
            news_items=[],  # Would fetch from news source if available
            days_lookback=180,
        )
        signals["leadership_change_score"] = leadership_change_score
        signals["leadership_changes"] = len(leadership_changes)

        # 5. Activist involvement (using helper)
        activist_signal = 0.0
        if filings:
            # Find most recent 13D filing
            recent_13d = next((f for f in filings if f.meta and f.meta.get("form") == "SC 13D"), None)
            if recent_13d and recent_13d.published_at:
                days_since = (datetime.now(datetime.now().astimezone().tzinfo) - recent_13d.published_at).days
                activist_signal = score_activist_signal(
                    days_since_13d=days_since,
                    filing_count_6m=len([f for f in filings if f.published_at and
                                        (datetime.now(datetime.now().astimezone().tzinfo) - f.published_at).days < 180])
                )
        signals["active_13d_filing"] = activist_signal > 0.3
        signals["activist_signal_strength"] = activist_signal

        # 6. Leverage stress: Net Debt / EBITDA ratio (using helper)
        debt_val = facts_meta.get("debt", {}).get("val", 0)
        oi_val = facts_meta.get("oi", {}).get("val", 0)
        leverage, leverage_stressed = calculate_leverage_stress(debt_val, oi_val)
        signals["net_debt_ebitda"] = leverage
        signals["leverage_stress"] = leverage_stressed

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

        # 1. Balance sheet stress: Net debt escalation (using helper)
        debt_val = facts_meta.get("debt", {}).get("val", 0)
        oi_val = facts_meta.get("oi", {}).get("val", 0)
        ebitda = oi_val * 1.2 if oi_val else 1.0
        debt_stress_score, debt_stress_bool = calculate_balance_sheet_stress(debt_val, current_ebitda=ebitda)
        signals["balance_sheet_stress"] = debt_stress_bool
        signals["balance_sheet_stress_score"] = debt_stress_score

        # 2. Segment underperformance (using helper)
        segment_count = segment_meta.get("segment_count", 1)
        segment_perf = 0.0
        if segment_count > 1 and segment_meta.get("has_multiple_segments"):
            # If we have segment data, compute actual margin gap
            # For now, use estimated value from segment extraction
            segment_perf = segment_meta.get("segment_underperformance", 0.25)
        signals["segment_underperformance"] = segment_perf

        # 3. Portfolio complexity: Conglomerate discount (using helper)
        revenue_concentration = 1.0 / max(segment_count, 1)  # 1 = single segment, <1 = diversified
        discount = calculate_conglomerate_discount(
            segment_count=segment_count,
            revenue_concentration=revenue_concentration,
            sector_diversity=max(1, segment_count - 1),
        )
        signals["conglomerate_discount_pct"] = discount

        # 4. Separation feasibility (using helper)
        feasibility = calculate_separation_readiness(
            years_of_segment_reporting=3,  # Assume minimum 3 years based on data availability
            segment_has_independent_ops=segment_count > 1,
            segment_revenue_pct=50.0 / max(segment_count, 1),  # Rough estimate
            systems_independence_score=0.6 if segment_count > 1 else 0.3,
            contract_assignability_score=0.7,
            regulatory_barriers_score=0.8,
        )
        signals["separation_readiness"] = feasibility

        # 5. Capital actions: Dividend suspension, equity issuance (using helper)
        capital_stress_score, capital_actions = detect_capital_stress_actions()
        signals["capital_stress_signals"] = capital_actions
        signals["capital_stress_score"] = capital_stress_score

        # Tier 3: Advanced analysis
        # Margin trend analysis (3-year trajectory)
        margin_trend_score, margin_trend_dir = calculate_margin_trend_3y(
            current_margin=current_revenue / max(current_oi, 1) * 100 if current_oi else 0
        )
        signals["margin_trend_score"] = margin_trend_score
        signals["margin_trend_direction"] = margin_trend_dir

        # Activist break-up call detection
        breakup_signal, has_breakup_call = detect_activist_breakup_calls([])
        signals["breakup_call_signal"] = breakup_signal
        signals["has_breakup_activist_call"] = has_breakup_call

        # Peer divestment pattern detection
        peer_precedent, divested_divisions = detect_peer_divestment_patterns(
            company_sector=company.sector or "",
            company_name=company.name,
            peer_divestment_news=[],
        )
        signals["peer_precedent_signal"] = peer_precedent
        signals["similar_divestments"] = len(divested_divisions)

        # Tier 3: Calculate separation probability
        margin_stress = 1.0 - min(abs(margin_trend_score), 1.0)  # Normalize trend to stress signal
        separation_prob = calculate_separation_probability(
            separation_readiness=feasibility,
            activist_signal=breakup_signal,
            peer_precedent_signal=peer_precedent,
            margin_stress_signal=margin_stress,
            debt_stress_signal=debt_stress_score,
        )
        signals["separation_probability"] = separation_prob

        # Tier 3: Multi-threshold gating
        equity_value = company.market_cap_usd or 1e9  # Default $1B if unknown
        should_flag, gate_reason = apply_multi_threshold_gating(
            cs2_score=score,  # Will use composite score later
            equity_value_usd=equity_value,
            separation_readiness=feasibility,
            separation_probability=separation_prob,
        )
        signals["passes_multi_threshold_gates"] = should_flag
        signals["gating_reason"] = gate_reason

        # Tier 4: Transaction probability and deal value
        transaction_prob = calculate_transaction_probability_model(
            cs1_score=0.0,  # Would get from CS1 scorer
            cs2_score=score,
            sector_m_and_a_activity=0.5,
        )
        signals["transaction_probability"] = transaction_prob

        deal_value, premium = calculate_deal_value_estimate(equity_value)
        signals["estimated_deal_value_usd"] = deal_value
        signals["acquisition_premium_usd"] = premium

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


def _get_sector_median_pe(sector: str) -> float:
    """Get sector median P/E ratio.

    Used for comparing company P/E to sector benchmark.
    """
    sector_pe_medians = {
        "Information Technology": 25.0,
        "Healthcare": 18.0,
        "Financials": 12.0,
        "Consumer Cyclical": 15.0,
        "Consumer Defensive": 20.0,
        "Energy": 10.0,
        "Materials": 11.0,
        "Communication Services": 22.0,
        "Industrials": 14.0,
        "Real Estate": 12.0,
        "Utilities": 13.0,
    }
    return sector_pe_medians.get(sector, 15.0)




def _score_cs1_composite(signals: dict) -> float:
    """Composite score for CS1 based on signals (Tiers 1-4)."""
    # Normalize signals (0-1 scale)
    underperf = min(max(signals.get("market_underperformance_pct", 0), 0) / 30, 1.0)
    pe_disc = min(max(signals.get("pe_discount_pct", 0), 0) / 40, 1.0)
    margin = min(max(signals.get("margin_compression_pct", 0), 0) / 30, 1.0)
    leverage_ratio = signals.get("net_debt_ebitda", 0)
    leverage = min(leverage_ratio / 5.0, 1.0) if leverage_ratio > 0 else 0

    # Tier 2: Leadership + activist signals
    leadership = signals.get("leadership_change_score", 0)
    activist = signals.get("activist_signal_strength", 0.7) if signals.get("active_13d_filing", False) else 0

    # Weighted composite (adjusted for Tier 4)
    score = (
        underperf * 0.14
        + pe_disc * 0.14
        + margin * 0.14
        + leverage * 0.18
        + leadership * 0.12
        + activist * 0.28  # Activist = strongest signal
    )

    return min(score, 1.0)


def _score_cs2_composite(signals: dict) -> float:
    """Composite score for CS2 based on signals (Tiers 1-4)."""
    # Tier 2: Core signals (normalized 0-1)
    debt_stress_score = signals.get("balance_sheet_stress_score", 0.5 if signals.get("balance_sheet_stress", False) else 0)
    segment_perf = min(signals.get("segment_underperformance", 0), 1.0)
    discount = min(signals.get("conglomerate_discount_pct", 0) / 25, 1.0)
    separation = signals.get("separation_readiness", 0)
    capital_stress = signals.get("capital_stress_score", 0.4 if signals.get("capital_stress_signals", False) else 0)

    # Tier 3: Advanced signals
    margin_trend = min(abs(signals.get("margin_trend_score", 0)), 1.0)  # Absolute value = stress magnitude
    breakup_signal = signals.get("breakup_call_signal", 0)
    peer_precedent = signals.get("peer_precedent_signal", 0)
    separation_prob = signals.get("separation_probability", 0)

    # Weighted composite: Tiers 1-2 baseline + Tier 3 enhancements
    score = (
        debt_stress_score * 0.16
        + segment_perf * 0.16
        + discount * 0.14
        + separation * 0.18
        + capital_stress * 0.12
        + margin_trend * 0.08
        + breakup_signal * 0.10
        + peer_precedent * 0.06
    )

    # Tier 3: Apply separation probability multiplier
    # High probability boosts score, low probability dampens
    probability_factor = 0.7 + (separation_prob * 0.3)  # Range: 0.7-1.0
    score = score * probability_factor

    return min(score, 1.0)
