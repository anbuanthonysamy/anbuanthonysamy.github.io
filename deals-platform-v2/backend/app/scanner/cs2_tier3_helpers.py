"""Tier 3: CS2 (Carve-out) advanced signal enhancements.

Multi-year trend analysis, peer divestment patterns, and activist calls.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


def calculate_margin_trend_3y(
    current_margin: float,
    prior_year_margin: Optional[float] = None,
    two_year_ago_margin: Optional[float] = None,
) -> tuple[float, str]:
    """Calculate 3-year margin trend trajectory.

    Deteriorating margins indicate operational stress (carve-out signal).

    Args:
        current_margin: Current year operating margin (%)
        prior_year_margin: Prior year margin (%), optional
        two_year_ago_margin: 2-year ago margin (%), optional

    Returns:
        (trend_score: -1 to 1, trend_direction: str)
        Negative = deteriorating, positive = improving
    """
    if not prior_year_margin:
        return 0.0, "no_data"

    # Year-over-year change
    yoy_change = current_margin - prior_year_margin

    if two_year_ago_margin:
        # Multi-year trend
        two_year_change = current_margin - two_year_ago_margin
        avg_annual_decline = two_year_change / 2

        if avg_annual_decline < -2:  # >2% annual decline
            return -0.7, "declining"
        elif avg_annual_decline < 0:
            return -0.3, "slight_decline"
        elif avg_annual_decline > 2:
            return 0.7, "improving"
        else:
            return 0.2, "slight_improve"
    else:
        # Just YoY
        if yoy_change < -3:
            return -0.6, "sharp_decline"
        elif yoy_change < 0:
            return -0.3, "declining"
        elif yoy_change > 3:
            return 0.6, "sharp_improve"
        else:
            return 0.2, "stable"


def detect_activist_breakup_calls(news_items: list[dict]) -> tuple[float, bool]:
    """Detect activist calls for break-up from news/filings.

    Activist pressure for separation is direct carve-out driver.

    Args:
        news_items: List of news RawItems with title/snippet

    Returns:
        (breakup_signal_score: 0-1, has_breakup_call: bool)
    """
    breakup_keywords = {
        "break up", "break-up", "breakup",
        "spin off", "spin-off", "spinoff",
        "carve out", "carve-out", "carveout",
        "separate", "separation",
        "activist", "activist investor", "activist fund",
        "portfolio optimization", "strategic review",
        "focused strategy", "focused portfolio",
    }

    signal_score = 0.0
    found_breakup = False

    for item in news_items:
        title = (item.get("title") or "").lower()
        snippet = (item.get("snippet") or "").lower()
        combined = f"{title} {snippet}"

        # Check for multiple breakup keywords
        keyword_hits = sum(1 for kw in breakup_keywords if kw in combined)

        if keyword_hits >= 2:  # Multiple keywords = stronger signal
            signal_score += 0.3
            found_breakup = True
        elif keyword_hits >= 1:
            signal_score += 0.15

        # Check for explicit activist + break-up combination
        if ("activist" in combined or "activist fund" in combined or "activist investor" in combined):
            if any(bk in combined for bk in ["break", "spin", "carve", "separate"]):
                signal_score += 0.25
                found_breakup = True

    signal_score = min(signal_score, 1.0)
    return signal_score, found_breakup


def detect_peer_divestment_patterns(
    company_sector: str,
    company_name: str,
    peer_divestment_news: list[dict],
) -> tuple[float, list[str]]:
    """Detect peer company divestments in same sector (precedent detection).

    When peers divest similar divisions, it validates separation thesis.

    Args:
        company_sector: Company's industry sector
        company_name: Company name for filtering
        peer_divestment_news: List of recent divestment news items

    Returns:
        (precedent_score: 0-1, divested_division_names: list[str])
    """
    # Keywords indicating divestments/spinoffs
    divestment_keywords = {
        "divest", "divestiture", "divested",
        "spin off", "spun off", "spinoff",
        "carve out", "carved out", "carveout",
        "separate", "separated",
        "acquire", "acquired",
        "sell", "sold", "sale",
    }

    precedent_score = 0.0
    divested_divisions = []

    for item in peer_divestment_news:
        title = (item.get("title") or "").lower()
        snippet = (item.get("snippet") or "").lower()
        combined = f"{title} {snippet}"

        # Skip if it's news about the target company itself
        if company_name.lower() in combined:
            continue

        # Check if sector/industry mentioned
        if company_sector.lower() not in combined:
            continue

        # Check for divestment keywords
        has_divestment = any(kw in combined for kw in divestment_keywords)

        if has_divestment:
            precedent_score += 0.2
            # Try to extract division name
            division = _extract_division_name(title)
            if division:
                divested_divisions.append(division)

    precedent_score = min(precedent_score, 1.0)
    return precedent_score, divested_divisions


def calculate_separation_probability(
    separation_readiness: float,
    activist_signal: float,
    peer_precedent_signal: float,
    margin_stress_signal: float,
    debt_stress_signal: float,
) -> float:
    """Calculate probability of separation occurring (transaction likelihood).

    Combines multiple factors into likelihood score.

    Args:
        separation_readiness: 0-1 (technical feasibility)
        activist_signal: 0-1 (activist pressure)
        peer_precedent_signal: 0-1 (market validation)
        margin_stress_signal: 0-1 (operational motivation)
        debt_stress_signal: 0-1 (financial motivation)

    Returns:
        Separation probability (0-1)
    """
    # Weights: Readiness (30%) + Activist (25%) + Precedent (20%) + Margin (15%) + Debt (10%)
    probability = (
        separation_readiness * 0.30
        + activist_signal * 0.25
        + peer_precedent_signal * 0.20
        + margin_stress_signal * 0.15
        + debt_stress_signal * 0.10
    )

    return min(probability, 1.0)


def apply_multi_threshold_gating(
    cs2_score: float,
    equity_value_usd: float,
    separation_readiness: float,
    separation_probability: float,
    min_equity_value: float = 750_000_000,  # $750M
    min_readiness: float = 0.40,
    min_probability: float = 0.20,
) -> tuple[bool, str]:
    """Apply multi-threshold gating to avoid false positives.

    Only flag carve-outs that pass multiple criteria (not just high score).

    Args:
        cs2_score: Overall CS2 signal score (0-1)
        equity_value_usd: Estimated subsidiary equity value
        separation_readiness: Separation feasibility (0-1)
        separation_probability: Probability of occurring (0-1)
        min_equity_value: Minimum market cap threshold
        min_readiness: Minimum readiness threshold
        min_probability: Minimum probability threshold

    Returns:
        (should_flag: bool, reason: str)
    """
    reasons = []

    # Gate 1: Equity value threshold
    if equity_value_usd < min_equity_value:
        return False, f"Below minimum equity value (${equity_value_usd/1e9:.1f}B < ${min_equity_value/1e9:.1f}B)"

    # Gate 2: Readiness threshold
    if separation_readiness < min_readiness:
        reasons.append(f"Low readiness ({separation_readiness:.2f} < {min_readiness:.2f})")

    # Gate 3: Probability threshold
    if separation_probability < min_probability:
        reasons.append(f"Low probability ({separation_probability:.2f} < {min_probability:.2f})")

    # Gate 4: Composite score
    if cs2_score < 0.45:
        reasons.append(f"Low CS2 score ({cs2_score:.2f} < 0.45)")

    if reasons:
        reason_str = " AND ".join(reasons)
        return False, reason_str

    return True, "Passed all gates"


def _extract_division_name(text: str) -> Optional[str]:
    """Extract division/subsidiary name from news headline.

    Simple pattern matching for common patterns.
    """
    patterns = [
        r"(\w+(?:\s+\w+)?)\s+(?:division|business|unit|segment)",
        r"spins?\s+off?\s+(\w+(?:\s+\w+)?)",
        r"divests?\s+(\w+(?:\s+\w+)?)",
        r"separates?\s+(\w+(?:\s+\w+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None
