"""Tier 4: Polish and advanced scoring enhancements.

Leadership changes, transaction probability, and signal refinement.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)


def detect_leadership_changes(
    filing_items: list[dict],
    news_items: list[dict],
    days_lookback: int = 180,
) -> tuple[float, list[dict]]:
    """Detect CEO/CFO changes from SEC 8-K filings and news.

    Leadership change from strategic/PE background is M&A signal.

    Args:
        filing_items: List of SEC filing RawItems (8-K, DEF14A)
        news_items: List of news RawItems
        days_lookback: Days to look back for recent changes (default 180)

    Returns:
        (leadership_change_score: 0-1, changes: list[dict])
        Each change: {"executive": str, "date": datetime, "source": str, "background": str}
    """
    leadership_keywords = {
        "chief executive officer", "ceo",
        "chief financial officer", "cfo",
        "chief operating officer", "coo",
        "chief investment officer", "cio",
    }

    pe_keywords = {"private equity", "pe firm", "buyout", "activist", "hedge fund"}
    strategic_keywords = {"strategic", "m&a", "acquisition", "merger", "integration"}

    changes = []
    score = 0.0

    # Check 8-K filings
    for filing in filing_items:
        if filing.get("kind") != "filing_8k":
            continue

        title = (filing.get("title") or "").lower()
        published_at = filing.get("published_at")

        # Check recency
        if published_at:
            days_ago = (datetime.now(published_at.tzinfo) - published_at).days
            if days_ago > days_lookback:
                continue

        # Check for executive change indicators
        has_leadership = any(kw in title for kw in leadership_keywords)
        has_pe_or_strategic = any(kw in title for kw in pe_keywords | strategic_keywords)

        if has_leadership:
            # Extract executive name if possible
            exec_name = _extract_executive_name(title)
            change_entry = {
                "executive": exec_name or "Unknown Executive",
                "date": published_at,
                "source": "8-K Filing",
                "background": "PE/Strategic" if has_pe_or_strategic else "Internal",
            }
            changes.append(change_entry)
            score += 0.3 if has_pe_or_strategic else 0.15

    # Check news items
    for news in news_items:
        title = (news.get("title") or "").lower()
        published_at = news.get("published_at")

        if published_at:
            days_ago = (datetime.now(published_at.tzinfo) - published_at).days
            if days_ago > days_lookback:
                continue

        has_leadership = any(kw in title for kw in leadership_keywords)
        has_appointment = "appoint" in title or "join" in title or "named" in title
        has_pe_or_strategic = any(kw in title for kw in pe_keywords | strategic_keywords)

        if has_leadership and has_appointment:
            exec_name = _extract_executive_name(title)
            change_entry = {
                "executive": exec_name or "Unknown Executive",
                "date": published_at,
                "source": "News",
                "background": "PE/Strategic" if has_pe_or_strategic else "Industry",
            }
            changes.append(change_entry)
            score += 0.25 if has_pe_or_strategic else 0.1

    score = min(score, 1.0)
    return score, changes


def assess_ownership_structure(
    insider_ownership_pct: float,
    institutional_ownership_pct: float,
    activist_ownership_pct: float = 0.0,
) -> tuple[float, str]:
    """Assess ownership concentration (spin readiness indicator).

    Dispersed ownership (low insider, high institutional) = easier spin.
    Concentrated ownership (high insider) = harder spin (founder resistance).

    Args:
        insider_ownership_pct: Insider ownership % (0-100)
        institutional_ownership_pct: Institutional ownership % (0-100)
        activist_ownership_pct: Activist fund ownership % (0-100)

    Returns:
        (spin_readiness_score: 0-1, structure_type: str)
    """
    total_managed = institutional_ownership_pct + activist_ownership_pct

    if insider_ownership_pct > 30:
        # Concentrated ownership = founder/family control
        readiness = 0.3  # Hard to spin against founder wishes
        structure = "founder_controlled"
    elif insider_ownership_pct > 10:
        readiness = 0.5
        structure = "insider_significant"
    elif total_managed > 70:
        # Highly institutional = proxy-fighting friendly
        readiness = 0.9 if activist_ownership_pct > 5 else 0.75
        structure = "institutional_friendly" if activist_ownership_pct < 5 else "activist_friendly"
    else:
        readiness = 0.6
        structure = "balanced"

    return readiness, structure


def calculate_transaction_probability_model(
    cs1_score: float,
    cs2_score: float,
    years_since_last_deal: Optional[int] = None,
    acquisition_pace_per_year: float = 0.3,
    sector_m_and_a_activity: float = 0.5,
) -> float:
    """Calculate estimated transaction probability (when will it happen?).

    Uses transaction pace benchmarks and company-specific signals.

    Args:
        cs1_score: M&A origination score (0-1)
        cs2_score: Carve-out score (0-1)
        years_since_last_deal: Years since last M&A activity
        acquisition_pace_per_year: How many targets acquired per year (0-2)
        sector_m_and_a_activity: Sector M&A frequency (0-1, 0.5 = moderate)

    Returns:
        Annualized transaction probability (0-1)
    """
    # Baseline probability from sector activity
    baseline_probability = sector_m_and_a_activity * 0.3

    # Company signal contribution
    signal_probability = max(cs1_score, cs2_score) * 0.5

    # Acquisition pace contribution (recent deals = more likely repeat)
    pace_contribution = 0.0
    if years_since_last_deal:
        if years_since_last_deal < 2:
            pace_contribution = 0.3  # Recent acquirer
        elif years_since_last_deal < 5:
            pace_contribution = 0.15
        else:
            pace_contribution = 0.05  # Dormant

    # Combine factors
    probability = baseline_probability + signal_probability + pace_contribution

    return min(probability, 1.0)


def calculate_deal_value_estimate(
    equity_value_usd: float,
    acquisition_premium_pct: float = 25.0,
) -> tuple[float, float]:
    """Estimate deal value (equity + premium).

    Acquisition premiums typically 20-35%; average ~25%.

    Args:
        equity_value_usd: Current equity value ($)
        acquisition_premium_pct: Expected premium (%, default 25%)

    Returns:
        (deal_value_usd: float, premium_usd: float)
    """
    premium = equity_value_usd * (acquisition_premium_pct / 100)
    deal_value = equity_value_usd + premium

    return deal_value, premium


def score_deal_attractiveness(
    acquisition_cost: float,
    ebitda: float,
    ev_to_ebitda_multiple: float = 10.0,
    sector_median_ev_ebitda: float = 12.0,
) -> tuple[float, str]:
    """Score acquisition attractiveness (valuation vs sector).

    Lower EV/EBITDA relative to peers = more attractive deal.

    Args:
        acquisition_cost: Deal cost ($)
        ebitda: Target EBITDA ($)
        ev_to_ebitda_multiple: Current EV/EBITDA
        sector_median_ev_ebitda: Sector median EV/EBITDA

    Returns:
        (attractiveness_score: 0-1, assessment: str)
    """
    if ebitda <= 0:
        return 0.0, "insufficient_data"

    # Compare to sector
    discount_to_sector = sector_median_ev_ebitda - ev_to_ebitda_multiple
    discount_pct = (discount_to_sector / sector_median_ev_ebitda) * 100

    if discount_pct > 20:
        # Significant discount = very attractive
        attractiveness = 0.85
        assessment = "very_attractive"
    elif discount_pct > 10:
        attractiveness = 0.65
        assessment = "attractive"
    elif discount_pct > 0:
        attractiveness = 0.45
        assessment = "fair_value"
    elif discount_pct > -10:
        attractiveness = 0.25
        assessment = "slight_premium"
    else:
        attractiveness = 0.05
        assessment = "expensive"

    return attractiveness, assessment


def refine_signal_scoring(
    raw_signal_dict: dict,
    data_quality_score: float,  # 0-1, 1 = perfect data
    signal_consistency_score: float,  # 0-1, 1 = all signals agree
) -> dict:
    """Refine signal scores based on data quality and consistency.

    Poor data or conflicting signals should reduce confidence.

    Args:
        raw_signal_dict: Original signals dict
        data_quality_score: How complete/reliable is the data
        signal_consistency_score: How much signals agree

    Returns:
        Refined signals dict with adjusted confidence
    """
    refined = raw_signal_dict.copy()

    # Apply data quality discount
    quality_adjustment = data_quality_score * 1.0 + (1 - data_quality_score) * 0.7
    # quality_adjustment ranges from 0.7 (poor data) to 1.0 (good data)

    # Apply consistency adjustment
    consistency_adjustment = signal_consistency_score * 1.0 + (1 - signal_consistency_score) * 0.6
    # consistency_adjustment ranges from 0.6 (conflicts) to 1.0 (agreement)

    # Reduce primary scores by adjustment factors
    for key in ["market_underperformance_pct", "pe_discount_pct", "margin_compression_pct",
                "net_debt_ebitda", "segment_underperformance", "balance_sheet_stress_score"]:
        if key in refined and isinstance(refined[key], (int, float)):
            if "pct" in key or "score" in key:
                # For percentage/score metrics, apply adjustment
                refined[key] = refined[key] * quality_adjustment * consistency_adjustment

    # Add metadata
    refined["data_quality_score"] = data_quality_score
    refined["signal_consistency_score"] = signal_consistency_score
    refined["refinement_applied"] = True

    return refined


def _extract_executive_name(text: str) -> Optional[str]:
    """Extract executive name from title.

    Simple heuristic: look for capitalized words after title indicators.
    """
    patterns = [
        r"(?:appoints?|names?|joins?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"(?:ceo|cfo|coo|cio)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    return None
