"""CS1 (M&A Origination) signal calculation helpers."""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def calculate_pe_discount(company_pe: float, sector_median_pe: float) -> float:
    """Calculate P/E discount vs sector median.

    Args:
        company_pe: Company's current P/E ratio
        sector_median_pe: Sector median P/E ratio

    Returns:
        P/E discount percentage (positive = undervalued, negative = overvalued)
        Range: -50% to +50%
    """
    if company_pe <= 0 or sector_median_pe <= 0:
        return 0.0

    discount_pct = ((sector_median_pe - company_pe) / sector_median_pe) * 100

    # Clip to reasonable range
    return max(-50, min(discount_pct, 50))


def calculate_stock_underperformance(
    company_52w_return: float,
    sector_52w_return: float,
    company_3y_return: Optional[float] = None,
    sector_3y_return: Optional[float] = None,
) -> float:
    """Calculate stock underperformance vs sector.

    Compares multi-year returns. If 3Y data unavailable, uses 52W.

    Args:
        company_52w_return: Company's 52-week return (%)
        sector_52w_return: Sector median 52-week return (%)
        company_3y_return: Company's 3-year return (%), optional
        sector_3y_return: Sector median 3-year return (%), optional

    Returns:
        Underperformance gap (%), positive = underperforming
        Range: -50% to +100%
    """
    # Prefer 3-year if available (more meaningful for M&A catalysts)
    if company_3y_return is not None and sector_3y_return is not None:
        gap = sector_3y_return - company_3y_return
    else:
        gap = sector_52w_return - company_52w_return

    # Clip to reasonable range
    return max(-50, min(gap, 100))


def calculate_margin_compression(
    current_oi: float,
    current_revenue: float,
    prior_oi: Optional[float] = None,
    prior_revenue: Optional[float] = None,
    sector_median_margin: float = 15.0,
) -> float:
    """Calculate operating margin compression.

    Compares current margin to prior year or sector median.

    Args:
        current_oi: Current operating income ($)
        current_revenue: Current revenue ($)
        prior_oi: Prior year operating income ($), optional
        prior_revenue: Prior year revenue ($), optional
        sector_median_margin: Sector median margin (%), default 15%

    Returns:
        Margin compression (%), positive = compression/underperformance
        Range: -20% to +50%
    """
    if current_revenue <= 0:
        return 0.0

    current_margin = (current_oi / current_revenue) * 100

    if prior_revenue and prior_oi:
        prior_margin = (prior_oi / prior_revenue) * 100
        compression = prior_margin - current_margin
    else:
        compression = sector_median_margin - current_margin

    # Clip to reasonable range
    return max(-20, min(compression, 50))


def calculate_leverage_stress(
    total_debt: float,
    operating_income: float,
    cash: Optional[float] = None,
    depreciation_amortization: Optional[float] = None,
    stress_threshold: float = 3.5,
) -> tuple[float, bool]:
    """Calculate leverage stress (Net Debt / EBITDA).

    Args:
        total_debt: Total debt ($)
        operating_income: Operating income ($)
        cash: Cash on hand ($), optional for net debt calc
        depreciation_amortization: D&A ($), optional for precise EBITDA
        stress_threshold: Leverage threshold for stress signal (default 3.5x)

    Returns:
        (leverage_ratio: float, is_stressed: bool)
        Leverage ratio capped at 10.0x
    """
    if operating_income <= 0:
        return 0.0, False

    # Calculate EBITDA
    if depreciation_amortization:
        ebitda = operating_income + depreciation_amortization
    else:
        # Conservative estimate: OI * 1.2 (assumes ~17% D&A)
        ebitda = operating_income * 1.2

    # Calculate net debt
    if cash:
        net_debt = max(0, total_debt - cash)  # Net debt can't be negative
    else:
        net_debt = total_debt

    if ebitda <= 0:
        return 0.0, False

    leverage = net_debt / ebitda
    leverage_capped = min(leverage, 10.0)
    is_stressed = leverage >= stress_threshold

    return leverage_capped, is_stressed


def detect_valuation_gap(
    company_pe: float,
    company_pb: Optional[float] = None,
    sector_median_pe: float = 15.0,
    sector_median_pb: Optional[float] = None,
) -> tuple[float, bool]:
    """Detect significant valuation gaps (M&A signal).

    A company trading significantly below sector suggests:
    - Market discount due to distress/uncertainty
    - Potential M&A target (cheap entry)

    Args:
        company_pe: Company P/E ratio
        company_pb: Company P/B ratio, optional
        sector_median_pe: Sector median P/E
        sector_median_pb: Sector median P/B, optional

    Returns:
        (valuation_gap_score: 0-1, has_gap: bool)
    """
    if company_pe <= 0 or sector_median_pe <= 0:
        return 0.0, False

    pe_gap_pct = ((sector_median_pe - company_pe) / sector_median_pe) * 100

    # If P/B available, average the two metrics
    if company_pb and company_pb > 0 and sector_median_pb and sector_median_pb > 0:
        pb_gap_pct = ((sector_median_pb - company_pb) / sector_median_pb) * 100
        avg_gap = (pe_gap_pct + pb_gap_pct) / 2
    else:
        avg_gap = pe_gap_pct

    # Normalize to 0-1 scale (25% gap = 0.5 score)
    gap_score = min(avg_gap / 50, 1.0)
    has_gap = avg_gap > 15  # Significant gap threshold

    return gap_score, has_gap


def score_activist_signal(
    days_since_13d: Optional[int] = None,
    filing_count_6m: int = 0,
    has_proxy_contest: bool = False,
    activist_fund_name: Optional[str] = None,
) -> float:
    """Score activist involvement signal.

    Activist involvement is strong M&A catalyst:
    - Recent 13D filing indicates fresh interest
    - Multiple filings = sustained pressure
    - Proxy contests = operational intervention

    Args:
        days_since_13d: Days since most recent 13D filing
        filing_count_6m: Number of filings in last 6 months
        has_proxy_contest: Whether proxy contest is active
        activist_fund_name: Name of activist fund (e.g., 'Elliott', 'Pershing Square')

    Returns:
        Activist signal score (0-1)
    """
    score = 0.0

    # Recent 13D filing (within 6 months)
    if days_since_13d is not None:
        if days_since_13d <= 180:
            recency_factor = 1.0 - (days_since_13d / 180)  # 0 days = 1.0, 180 days = 0.0
            score += recency_factor * 0.4
        else:
            score += 0.1  # Older filing, minimal contribution

    # Multiple filings indicate sustained pressure
    if filing_count_6m >= 3:
        score += 0.3
    elif filing_count_6m >= 1:
        score += 0.15

    # Proxy contest is strong signal (operational intervention sought)
    if has_proxy_contest:
        score += 0.25

    # Known activist funds (more credible threat)
    known_activists = {"Elliott", "Pershing Square", "ValueAct", "Third Point", "Starboard"}
    if activist_fund_name and any(a.lower() in activist_fund_name.lower() for a in known_activists):
        score += 0.1

    return min(score, 1.0)
