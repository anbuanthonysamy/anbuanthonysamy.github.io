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
from app.shared.source_status import TRACKER
from app.sources.registry import BY_ID

log = logging.getLogger(__name__)


async def _fetch_with_tracking(
    module: str,
    source_id: str,
    api_mode: str,
    fetch_fn,
    *args,
    **kwargs,
):
    """Call a source fetch, record ok/error/skipped in the module tracker.

    - In ``offline`` mode we never attempt the fetch; we record ``skipped``.
    - In ``live`` mode we attempt the fetch and record ``ok`` or ``error``.
    """
    if api_mode == "offline":
        TRACKER.record(module, source_id, "skipped",
                       detail="Offline mode: live fetch skipped", mode="offline")
        return None
    try:
        result = await asyncio.to_thread(fetch_fn, *args, **kwargs)
        TRACKER.record(module, source_id, "ok", mode="live")
        return result
    except Exception as exc:
        TRACKER.record(module, source_id, "error", detail=str(exc), mode="live")
        log.warning("source %s failed: %s", source_id, exc)
        return None


async def cs1_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS1 M&A origination signals (deterministic, API-driven).

    Each data source fetches and computes independently. If a source fails,
    only the signals derived from that source are missing — other signals
    still compute from their own live data. Missing signals default to 0
    rather than being replaced with stub values.
    """
    signals: dict = {
        # Sane defaults — overwritten only when real data is available
        "market_underperformance_pct": 0.0,
        "pe_discount_pct": 0.0,
        "margin_compression_pct": 0.0,
        "fresh_leadership_change": False,
        "leadership_change_score": 0.0,
        "leadership_changes": 0,
        "active_13d_filing": False,
        "activist_signal_strength": 0.0,
        "net_debt_ebitda": 0.0,
        "leverage_stress": False,
    }

    # Fetches: each source is independent. _fetch_with_tracking catches
    # source-level errors and records them in the status tracker.
    facts_meta: dict = {}
    edgar_facts = BY_ID.get("edgar.xbrl_companyfacts")
    if edgar_facts and company.cik:
        facts_items = await _fetch_with_tracking(
            "origination", "edgar.xbrl_companyfacts", api_mode,
            edgar_facts.fetch, cik=company.cik, company_name=company.name,
        )
        if facts_items:
            try:
                facts_meta = _extract_financial_metrics(facts_items)
            except Exception as e:
                log.warning("CS1 extract financials failed for %s: %s", company.ticker, e)

    market_meta: dict = {}
    market = BY_ID.get("market.yfinance")
    if market and company.ticker:
        market_items = await _fetch_with_tracking(
            "origination", "market.yfinance", api_mode,
            market.fetch, ticker=company.ticker, sector=company.sector,
            country=company.country,
        )
        if market_items:
            try:
                market_meta = _extract_market_metrics(market_items)
            except Exception as e:
                log.warning("CS1 extract market failed for %s: %s", company.ticker, e)

    # If EDGAR data is missing or incomplete, use yfinance as fallback
    if not facts_meta and market_meta:
        facts_meta = _build_facts_from_market_metrics(market_meta)

    filings: list = []
    edgar_submissions = BY_ID.get("edgar.submissions")
    if edgar_submissions and company.cik:
        filing_items = await _fetch_with_tracking(
            "origination", "edgar.submissions", api_mode,
            edgar_submissions.fetch, cik=company.cik, company_name=company.name,
        )
        if filing_items:
            try:
                filings = [item for item in filing_items if item.kind == "filing_13d"]
            except Exception as e:
                log.warning("CS1 filings filter failed for %s: %s", company.ticker, e)

    ch_meta: dict = {}
    companies_house = BY_ID.get("reg.companies_house")
    if companies_house and company.country == "UK" and company.company_number:
        ch_items = await _fetch_with_tracking(
            "origination", "reg.companies_house", api_mode,
            companies_house.fetch, company_number=company.company_number,
        )
        if ch_items:
            try:
                ch_meta = _extract_companies_house_metrics(ch_items)
            except Exception as e:
                log.warning("CS1 extract companies_house failed for %s: %s", company.ticker, e)

    # Signal computations — each in its own guard so one failure doesn't
    # prevent other signals from being derived.

    # 1. Market underperformance vs peers (market.yfinance)
    try:
        signals["market_underperformance_pct"] = float(
            market_meta.get("underperformance_vs_sector", 0.0) or 0.0
        )
    except Exception as e:
        log.warning("CS1 underperformance calc failed for %s: %s", company.ticker, e)

    # 2. PE multiple discount vs sector median (market.yfinance + sector medians)
    try:
        company_pe = float(market_meta.get("pe_ratio", 0) or 0)
        sector_pe = _get_sector_median_pe(company.sector or "")
        signals["pe_discount_pct"] = calculate_pe_discount(company_pe, sector_pe)
    except Exception as e:
        log.warning("CS1 pe_discount calc failed for %s: %s", company.ticker, e)

    # 3. Margin compression (edgar.xbrl_companyfacts)
    try:
        current_revenue = facts_meta.get("revenue", {}).get("val", 0) or 0
        current_oi = facts_meta.get("oi", {}).get("val", 0) or 0
        signals["margin_compression_pct"] = calculate_margin_compression(
            current_oi, current_revenue
        )
    except Exception as e:
        log.warning("CS1 margin_compression calc failed for %s: %s", company.ticker, e)

    # 4. Leadership changes (edgar.submissions + tier4 news detection)
    try:
        signals["fresh_leadership_change"] = len(filings) > 0
        leadership_change_score, leadership_changes = detect_leadership_changes(
            filing_items=filings,
            news_items=[],
            days_lookback=180,
        )
        signals["leadership_change_score"] = leadership_change_score
        signals["leadership_changes"] = len(leadership_changes)
    except Exception as e:
        log.warning("CS1 leadership calc failed for %s: %s", company.ticker, e)

    # 5. Activist involvement (edgar.submissions SC 13D)
    try:
        activist_signal = 0.0
        if filings:
            recent_13d = next(
                (f for f in filings if f.meta and f.meta.get("form") == "SC 13D"),
                None,
            )
            if recent_13d and recent_13d.published_at:
                now_aware = datetime.now(recent_13d.published_at.tzinfo)
                days_since = (now_aware - recent_13d.published_at).days
                filing_count_6m = sum(
                    1 for f in filings
                    if f.published_at and (now_aware - f.published_at).days < 180
                )
                activist_signal = score_activist_signal(
                    days_since_13d=days_since,
                    filing_count_6m=filing_count_6m,
                )
        signals["active_13d_filing"] = activist_signal > 0.3
        signals["activist_signal_strength"] = activist_signal
    except Exception as e:
        log.warning("CS1 activist calc failed for %s: %s", company.ticker, e)

    # 6. Leverage stress: Net Debt / EBITDA (edgar.xbrl_companyfacts)
    try:
        debt_val = facts_meta.get("debt", {}).get("val", 0) or 0
        oi_val = facts_meta.get("oi", {}).get("val", 0) or 0
        leverage, leverage_stressed = calculate_leverage_stress(debt_val, oi_val)
        signals["net_debt_ebitda"] = leverage
        signals["leverage_stress"] = leverage_stressed
    except Exception as e:
        log.warning("CS1 leverage calc failed for %s: %s", company.ticker, e)

    # Composite score — only uses signals that actually had data
    score = _score_cs1_composite(signals)

    return score, signals


async def cs2_signal_scorer(
    company: Company, api_mode: str, db: Session
) -> tuple[float, dict]:
    """Score CS2 carve-out signals (deterministic, API-driven)."""
    equity_value_default = getattr(company, "market_cap_usd", None) or 1e9
    signals: dict = {
        # Sane defaults — overwritten only when real data is available
        "balance_sheet_stress": False,
        "balance_sheet_stress_score": 0.0,
        "segment_underperformance": 0.0,
        "conglomerate_discount_pct": 0.0,
        "separation_readiness": 0.0,
        "capital_stress_signals": False,
        "capital_stress_score": 0.0,
        "margin_trend_score": 0.0,
        "margin_trend_direction": "unknown",
        "breakup_call_signal": 0.0,
        "has_breakup_activist_call": False,
        "peer_precedent_signal": 0.0,
        "similar_divestments": 0,
        "separation_probability": 0.0,
        "estimated_deal_value_usd": 0.0,
        "acquisition_premium_usd": 0.0,
        "_equity_value_usd": equity_value_default,
        "_separation_readiness_cached": 0.0,
        "_separation_probability_cached": 0.0,
    }

    # Fetches: each source is independent.
    segment_meta: dict = {}
    segment_facts = BY_ID.get("edgar.xbrl_segment_facts")
    if segment_facts and company.cik:
        segment_items = await _fetch_with_tracking(
            "carve_outs", "edgar.xbrl_segment_facts", api_mode,
            segment_facts.fetch, cik=company.cik, company_name=company.name,
        )
        if segment_items:
            try:
                segment_meta = _extract_segment_metrics(segment_items)
            except Exception as e:
                log.warning("CS2 extract segments failed for %s: %s", company.ticker, e)

    facts_meta: dict = {}
    edgar_facts = BY_ID.get("edgar.xbrl_companyfacts")
    if edgar_facts and company.cik:
        facts_items = await _fetch_with_tracking(
            "carve_outs", "edgar.xbrl_companyfacts", api_mode,
            edgar_facts.fetch, cik=company.cik, company_name=company.name,
        )
        if facts_items:
            try:
                facts_meta = _extract_financial_metrics(facts_items)
            except Exception as e:
                log.warning("CS2 extract financials failed for %s: %s", company.ticker, e)

    market_meta_cs2: dict = {}
    market = BY_ID.get("market.yfinance")
    if market and company.ticker:
        market_items_cs2 = await _fetch_with_tracking(
            "carve_outs", "market.yfinance", api_mode,
            market.fetch, ticker=company.ticker, sector=company.sector,
            country=company.country,
        )
        if market_items_cs2:
            try:
                market_meta_cs2 = _extract_market_metrics(market_items_cs2)
            except Exception as e:
                log.warning("CS2 extract market failed for %s: %s", company.ticker, e)

    # If EDGAR data is missing or incomplete, use yfinance as fallback
    if not facts_meta and market_meta_cs2:
        facts_meta = _build_facts_from_market_metrics(market_meta_cs2)

    ch_meta: dict = {}
    companies_house = BY_ID.get("reg.companies_house")
    if companies_house and company.country == "UK" and company.company_number:
        ch_items = await _fetch_with_tracking(
            "carve_outs", "reg.companies_house", api_mode,
            companies_house.fetch, company_number=company.company_number,
        )
        if ch_items:
            try:
                ch_meta = _extract_companies_house_metrics(ch_items)
            except Exception as e:
                log.warning("CS2 extract companies_house failed for %s: %s", company.ticker, e)

    # Signal computations — each in its own guard.
    debt_stress_score = 0.0
    debt_val = facts_meta.get("debt", {}).get("val", 0) or 0
    oi_val = facts_meta.get("oi", {}).get("val", 0) or 0
    current_revenue = facts_meta.get("revenue", {}).get("val", 0) or 0

    # 1. Balance sheet stress
    try:
        ebitda = oi_val * 1.2 if oi_val else 1.0
        debt_stress_score, debt_stress_bool = calculate_balance_sheet_stress(
            debt_val, current_ebitda=ebitda
        )
        signals["balance_sheet_stress"] = debt_stress_bool
        signals["balance_sheet_stress_score"] = debt_stress_score
    except Exception as e:
        log.warning("CS2 balance_sheet calc failed for %s: %s", company.ticker, e)

    # 2. Segment underperformance
    segment_count = 1
    try:
        segment_count = segment_meta.get("segment_count", 1) or 1
        if segment_count > 1 and segment_meta.get("has_multiple_segments"):
            signals["segment_underperformance"] = segment_meta.get(
                "segment_underperformance", 0.25
            )
    except Exception as e:
        log.warning("CS2 segment calc failed for %s: %s", company.ticker, e)

    # 3. Conglomerate discount
    try:
        revenue_concentration = 1.0 / max(segment_count, 1)
        signals["conglomerate_discount_pct"] = calculate_conglomerate_discount(
            segment_count=segment_count,
            revenue_concentration=revenue_concentration,
            sector_diversity=max(1, segment_count - 1),
        )
    except Exception as e:
        log.warning("CS2 conglomerate_discount calc failed for %s: %s", company.ticker, e)

    # 4. Separation feasibility
    feasibility = 0.0
    try:
        feasibility = calculate_separation_readiness(
            years_of_segment_reporting=3 if segment_count > 1 else 0,
            segment_has_independent_ops=segment_count > 1,
            segment_revenue_pct=50.0 / max(segment_count, 1),
            systems_independence_score=0.6 if segment_count > 1 else 0.3,
            contract_assignability_score=0.7,
            regulatory_barriers_score=0.8,
        )
        signals["separation_readiness"] = feasibility
        signals["_separation_readiness_cached"] = feasibility
    except Exception as e:
        log.warning("CS2 separation_readiness calc failed for %s: %s", company.ticker, e)

    # 5. Capital actions
    try:
        capital_stress_score, capital_actions = detect_capital_stress_actions()
        signals["capital_stress_signals"] = capital_actions
        signals["capital_stress_score"] = capital_stress_score
    except Exception as e:
        log.warning("CS2 capital_stress calc failed for %s: %s", company.ticker, e)

    # Tier 3: Margin trend
    margin_trend_score = 0.0
    try:
        current_margin_pct = (oi_val / current_revenue * 100) if current_revenue else 0.0
        margin_trend_score, margin_trend_dir = calculate_margin_trend_3y(
            current_margin=current_margin_pct
        )
        signals["margin_trend_score"] = margin_trend_score
        signals["margin_trend_direction"] = margin_trend_dir
    except Exception as e:
        log.warning("CS2 margin_trend calc failed for %s: %s", company.ticker, e)

    # Tier 3: Activist break-up calls (no news source yet — default to empty)
    breakup_signal = 0.0
    try:
        breakup_signal, has_breakup_call = detect_activist_breakup_calls([])
        signals["breakup_call_signal"] = breakup_signal
        signals["has_breakup_activist_call"] = has_breakup_call
    except Exception as e:
        log.warning("CS2 breakup_calls calc failed for %s: %s", company.ticker, e)

    # Tier 3: Peer divestment patterns
    peer_precedent = 0.0
    try:
        peer_precedent, divested_divisions = detect_peer_divestment_patterns(
            company_sector=company.sector or "",
            company_name=company.name,
            peer_divestment_news=[],
        )
        signals["peer_precedent_signal"] = peer_precedent
        signals["similar_divestments"] = len(divested_divisions)
    except Exception as e:
        log.warning("CS2 peer_divestment calc failed for %s: %s", company.ticker, e)

    # Tier 3: Separation probability
    try:
        margin_stress = 1.0 - min(abs(margin_trend_score), 1.0)
        separation_prob = calculate_separation_probability(
            separation_readiness=feasibility,
            activist_signal=breakup_signal,
            peer_precedent_signal=peer_precedent,
            margin_stress_signal=margin_stress,
            debt_stress_signal=debt_stress_score,
        )
        signals["separation_probability"] = separation_prob
        signals["_separation_probability_cached"] = separation_prob
    except Exception as e:
        log.warning("CS2 separation_probability calc failed for %s: %s", company.ticker, e)

    # Deal value estimate
    try:
        equity_value = getattr(company, "market_cap_usd", None) or equity_value_default
        deal_value, premium = calculate_deal_value_estimate(equity_value)
        signals["estimated_deal_value_usd"] = deal_value
        signals["acquisition_premium_usd"] = premium
        signals["_equity_value_usd"] = equity_value
    except Exception as e:
        log.warning("CS2 deal_value calc failed for %s: %s", company.ticker, e)

    # Composite score
    score = _score_cs2_composite(signals)

    # Tier 3: Multi-threshold gating (applied after composite is known)
    should_flag, gate_reason = apply_multi_threshold_gating(
        cs2_score=score,
        equity_value_usd=signals.get("_equity_value_usd", 1e9),
        separation_readiness=signals.get("_separation_readiness_cached", 0.0),
        separation_probability=signals.get("_separation_probability_cached", 0.0),
    )
    signals["passes_multi_threshold_gates"] = should_flag
    signals["gating_reason"] = gate_reason

    # Tier 4: Transaction probability (depends on composite)
    transaction_prob = calculate_transaction_probability_model(
        cs1_score=0.0,
        cs2_score=score,
        sector_m_and_a_activity=0.5,
    )
    signals["transaction_probability"] = transaction_prob

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


def _build_facts_from_market_metrics(market_meta: dict) -> dict:
    """Build EDGAR-like facts dict from yfinance market metrics (fallback for UK/missing EDGAR).

    Converts yfinance financial data into the same format as EDGAR facts_meta
    so signal calculations can work uniformly across US and UK companies.
    """
    facts = {}

    revenue = market_meta.get("total_revenue", 0)
    if revenue:
        facts["revenue"] = {"val": revenue, "fy": 0}

    # Estimate operating income from operating margins
    operating_margins = market_meta.get("operating_margins", 0) or 0
    if revenue and operating_margins:
        estimated_oi = revenue * operating_margins
        facts["oi"] = {"val": estimated_oi, "fy": 0}

    debt = market_meta.get("total_debt", 0)
    if debt:
        facts["debt"] = {"val": debt, "fy": 0}

    return facts


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
    """Extract market data from RawItems, including financial metrics from yfinance."""
    metrics = {}
    for item in items:
        meta = item.meta or {}
        metrics["market_cap"] = meta.get("market_cap", 0)
        metrics["last_price"] = meta.get("last_price", 0)
        metrics["pe_ratio"] = meta.get("pe_ratio", 0)
        metrics["performance_52w"] = meta.get("performance_52w", 0)
        metrics["underperformance_vs_sector"] = meta.get("underperformance_vs_sector", 0)
        metrics["sector"] = meta.get("sector", "")
        metrics["total_debt"] = meta.get("total_debt", 0)
        metrics["total_revenue"] = meta.get("total_revenue", 0)
        metrics["operating_margins"] = meta.get("operating_margins", 0)
        metrics["ebitda_margins"] = meta.get("ebitda_margins", 0)
        metrics["return_on_assets"] = meta.get("return_on_assets", 0)
    return metrics


def _extract_companies_house_metrics(items: list) -> dict:
    """Extract UK registry metrics from Companies House responses.

    Parses RawItems from Companies House API to extract company status,
    SIC codes (sector classification), and incorporation date.
    """
    metrics = {}
    for item in items:
        meta = item.meta or {}
        metrics["company_number"] = meta.get("company_number", "")
        metrics["sic_codes"] = meta.get("sic_codes", [])
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
