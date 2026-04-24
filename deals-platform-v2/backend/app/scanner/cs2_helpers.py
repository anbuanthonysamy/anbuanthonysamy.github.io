"""CS2 (Carve-out) signal calculation helpers."""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def calculate_segment_margin_drift(
    segment_margin: float,
    parent_margin: float,
    segment_name: str = "segment",
) -> tuple[float, bool]:
    """Calculate segment margin underperformance vs parent.

    Underperforming segments are carve-out candidates:
    - Could be turned around post-separation
    - May have operational drag on parent

    Args:
        segment_margin: Segment operating margin (%)
        parent_margin: Parent operating margin (%)
        segment_name: Segment identifier for logging

    Returns:
        (margin_gap: float, is_underperforming: bool)
        Margin gap = parent - segment (positive = underperforming)
    """
    margin_gap = parent_margin - segment_margin

    # Underperforming: margin gap > 5% or negative margin
    is_underperforming = margin_gap > 5 or segment_margin < 0

    log.debug(
        f"{segment_name}: segment_margin={segment_margin:.1f}%, "
        f"parent_margin={parent_margin:.1f}%, gap={margin_gap:.1f}%"
    )

    return margin_gap, is_underperforming


def calculate_balance_sheet_stress(
    current_debt: float,
    prior_year_debt: Optional[float] = None,
    current_ebitda: float = 1.0,
    current_ratio: Optional[float] = None,
    interest_coverage: Optional[float] = None,
) -> tuple[float, bool]:
    """Calculate balance sheet stress signals.

    Rising debt + tightening liquidity = carve-out pressure.

    Args:
        current_debt: Current total debt ($)
        prior_year_debt: Prior year debt ($), optional for trend
        current_ebitda: Current EBITDA ($)
        current_ratio: Current assets / current liabilities, optional
        interest_coverage: EBITDA / interest expense, optional

    Returns:
        (stress_score: 0-1, is_stressed: bool)
    """
    stress_score = 0.0

    # Debt escalation (year-over-year increase)
    if prior_year_debt and prior_year_debt > 0:
        debt_growth = (current_debt - prior_year_debt) / prior_year_debt
        if debt_growth > 0.1:  # >10% increase
            stress_score += min(debt_growth / 0.5, 0.3)  # Cap at 0.3

    # Leverage ratio (debt/EBITDA)
    if current_ebitda > 0:
        leverage = current_debt / current_ebitda
        if leverage > 3.5:
            stress_score += min((leverage - 3.5) / 3.5, 0.3)  # Cap at 0.3

    # Liquidity stress (current ratio < 1.0)
    if current_ratio and current_ratio < 1.0:
        stress_score += min(0.2 * (1.0 - current_ratio), 0.2)

    # Interest coverage stress (< 3.0x = risky)
    if interest_coverage and interest_coverage < 3.0:
        stress_score += min((3.0 - interest_coverage) / 3.0 * 0.2, 0.2)

    is_stressed = stress_score > 0.3
    return min(stress_score, 1.0), is_stressed


def calculate_conglomerate_discount(
    segment_count: int,
    revenue_concentration: float,  # 0-1, 1 = single segment
    sector_diversity: int = 0,  # Number of different sectors
    parent_pe: float = 15.0,
    sum_of_parts_pe: float = 18.0,
) -> float:
    """Calculate conglomerate discount (SOTP valuation gap).

    Conglomerates trade at discount vs sum-of-parts due to:
    - Complexity/confusion
    - Cross-subsidization
    - Allocation inefficiency

    Args:
        segment_count: Number of reportable segments
        revenue_concentration: 0 = diversified, 1 = single segment
        sector_diversity: Number of different industry sectors
        parent_pe: Parent company P/E ratio
        sum_of_parts_pe: Estimated sum-of-parts P/E ratio

    Returns:
        Conglomerate discount (%), 0-50%
    """
    if segment_count <= 1:
        return 0.0  # Single segment = no conglomerate discount

    # P/E-based discount
    pe_discount = max(0, (sum_of_parts_pe - parent_pe) / sum_of_parts_pe * 100)

    # Diversity penalty: more diverse portfolio = larger discount
    diversity_penalty = min(sector_diversity * 3, 15)  # Up to 15% from diversity

    # Concentration benefit: concentrated businesses get smaller discount
    concentration_benefit = (revenue_concentration * 5)  # 0-5% reduction

    discount = pe_discount + diversity_penalty - concentration_benefit

    # Clip to reasonable range
    return max(0, min(discount, 50))


def calculate_separation_readiness(
    years_of_segment_reporting: int,
    segment_has_independent_ops: bool = False,
    segment_revenue_pct: float = 0.0,
    systems_independence_score: float = 0.5,  # 0-1
    contract_assignability_score: float = 0.5,  # 0-1
    regulatory_barriers_score: float = 0.5,  # 0-1
) -> float:
    """Calculate separation readiness for carve-out.

    High readiness = can be spun quickly with low separation cost.
    Low readiness = complex entanglement, long separation timeline.

    Args:
        years_of_segment_reporting: Years company has reported segment separately
        segment_has_independent_ops: Whether segment has standalone operations
        segment_revenue_pct: Segment revenue as % of parent (0-100)
        systems_independence_score: IT systems independence (0-1)
        contract_assignability_score: Key contracts assignable (0-1)
        regulatory_barriers_score: Regulatory approvals needed (0-1, 1 = no barriers)

    Returns:
        Separation readiness (0-1)
    """
    score = 0.0

    # Historical separation reporting (shows visibility for spin)
    if years_of_segment_reporting >= 5:
        score += 0.2
    elif years_of_segment_reporting >= 3:
        score += 0.1

    # Operational independence
    if segment_has_independent_ops:
        score += 0.15

    # Size (need minimum size to justify independence)
    if segment_revenue_pct >= 20:
        score += 0.15
    elif segment_revenue_pct >= 10:
        score += 0.08

    # Systems integration
    score += systems_independence_score * 0.2

    # Contract assignability
    score += contract_assignability_score * 0.15

    # Regulatory ease
    score += regulatory_barriers_score * 0.15

    return min(score, 1.0)


def detect_capital_stress_actions(
    dividend_cut: bool = False,
    dividend_suspended: bool = False,
    recent_equity_issuance: bool = False,
    share_buyback_suspended: bool = False,
    covenant_waiver: bool = False,
) -> tuple[float, bool]:
    """Detect capital stress actions (management responses to financial pressure).

    These actions signal distress and potential carve-out driver.

    Args:
        dividend_cut: Dividend was cut or reduced
        dividend_suspended: Dividend was suspended entirely
        recent_equity_issuance: Equity raised in last 12 months
        share_buyback_suspended: Share buyback was suspended
        covenant_waiver: Debt covenant was waived

    Returns:
        (stress_score: 0-1, has_stress_actions: bool)
    """
    stress_signals = 0

    if dividend_suspended:
        stress_signals += 2  # Severe signal
    elif dividend_cut:
        stress_signals += 1

    if recent_equity_issuance:
        stress_signals += 1  # Need for capital

    if share_buyback_suspended:
        stress_signals += 1  # Liquidity constraint

    if covenant_waiver:
        stress_signals += 2  # Debt distress

    # Convert to 0-1 scale (max = 7 signals)
    stress_score = min(stress_signals / 7, 1.0)
    has_stress = stress_signals >= 2

    return stress_score, has_stress
