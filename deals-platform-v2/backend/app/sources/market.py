"""Market data — yfinance with fixture fallback."""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.models.enums import DataScope, SourceMode
from app.sources.base import RawItem, Source

log = logging.getLogger(__name__)


def _yahoo_ticker(ticker: str, country: str | None = None) -> str:
    """Convert our stored ticker to the form Yahoo Finance expects.

    - US tickers with a dot class share (BRK.B) use a dash on Yahoo (BRK-B).
    - UK tickers need the London exchange suffix (.L). HSBC's LSE listing
      is HSBA, not HSBC, so we translate that explicitly.
    """
    t = ticker.strip().upper()
    if country and country.upper() == "UK":
        uk_map = {"HSBC": "HSBA", "ASZA": "AZN"}
        t = uk_map.get(t, t)
        if not t.endswith(".L"):
            t = f"{t}.L"
        return t
    # US dot-class shares (e.g. BRK.B) use a dash on Yahoo
    if "." in t and not t.endswith(".L"):
        t = t.replace(".", "-")
    return t


class YFinanceMarket(Source):
    id = "market.yfinance"
    name = "Yahoo Finance (yfinance)"
    scope = DataScope.PUBLIC
    is_stub = False
    description = (
        "Market data via the unofficial yfinance Python library (price, market cap, "
        "PE ratio, debt, margins, 52-week performance). Acceptable for research PoC, "
        "not for production. No API key, but Yahoo TOS applies."
    )
    homepage_url = "https://pypi.org/project/yfinance/"

    def fetch(
        self,
        ticker: str,
        sector: str | None = None,
        country: str | None = None,
        api_mode: str = "live",
        **_: object,
    ) -> list[RawItem]:
        """Fetch market data and compute underperformance vs sector.

        Args:
            ticker: Stock ticker (e.g., 'AAPL', 'ULVR', 'BRK.B')
            sector: Industry sector for comparison (e.g., 'Information Technology')
            country: Company country ('US' or 'UK') — used to format the ticker
            api_mode: 'live' (must fetch real data, raise on error) or 'offline' (use fixtures)
        """
        s = get_settings()
        mode = SourceMode.LIVE
        fallback_reason: str | None = None
        yahoo_symbol = _yahoo_ticker(ticker, country)
        try:
            import yfinance  # type: ignore

            t = yfinance.Ticker(yahoo_symbol)
            info = t.fast_info
            mcap = float(getattr(info, "market_cap", 0) or 0)
            price = float(getattr(info, "last_price", 0) or 0)
            pe_ratio = float(getattr(info, "trailing_pe", 0) or 0)
            name = getattr(t, "info", {}).get("shortName", ticker) if hasattr(t, "info") else ticker

            # Extract financial metrics from yfinance info dict
            full_info = getattr(t, "info", {}) or {}
            total_debt = float(full_info.get("totalDebt", 0) or 0)
            total_revenue = float(full_info.get("totalRevenue", 0) or 0)
            operating_margins = float(full_info.get("operatingMargins", 0) or 0)
            ebitda_margins = float(full_info.get("ebitdaMargins", 0) or 0)
            return_on_assets = float(full_info.get("returnOnAssets", 0) or 0)

            # Compute 52-week performance
            history = t.history(period="1y")
            performance_52w = ((price - history.iloc[0]["Close"]) / history.iloc[0]["Close"] * 100) if len(history) > 0 else 0

        except Exception as e:
            if api_mode == "live":
                # In live mode, don't fall back — propagate the error
                raise
            # In offline mode, fall back to fixture
            log.warning("yfinance live fetch failed (%s): fallback fixture", e)
            fallback_reason = f"Live fetch failed: {type(e).__name__}: {str(e)[:200]}"
            fx = _load_fixture(s.fixtures_dir, "market_yf.json")
            row = fx.get(ticker, {})
            mcap = float(row.get("market_cap", 0) or 0)
            price = float(row.get("last_price", 0) or 0)
            pe_ratio = float(row.get("pe_ratio", 0) or 0)
            name = row.get("name") or ticker
            performance_52w = float(row.get("performance_52w", 0) or 0)
            total_debt = float(row.get("total_debt", 0) or 0)
            total_revenue = float(row.get("total_revenue", 0) or 0)
            operating_margins = float(row.get("operating_margins", 0) or 0)
            ebitda_margins = float(row.get("ebitda_margins", 0) or 0)
            return_on_assets = float(row.get("return_on_assets", 0) or 0)
            mode = SourceMode.FIXTURE

        # Compute underperformance vs sector
        underperformance = _compute_sector_underperformance(sector, pe_ratio, performance_52w)

        now = dt.datetime.now(dt.timezone.utc)
        return [
            RawItem(
                kind="market",
                source_id=self.id,
                title=f"{name} market snapshot",
                url=f"https://finance.yahoo.com/quote/{ticker}",
                snippet=f"price={price} mcap={mcap} pe={pe_ratio}",
                published_at=now,
                scope=DataScope.PUBLIC,
                mode=mode,
                company_ticker=ticker,
                company_name=name,
                meta={
                    "market_cap": mcap,
                    "last_price": price,
                    "pe_ratio": pe_ratio,
                    "performance_52w": performance_52w,
                    "underperformance_vs_sector": underperformance,
                    "sector": sector,
                    "total_debt": total_debt,
                    "total_revenue": total_revenue,
                    "operating_margins": operating_margins,
                    "ebitda_margins": ebitda_margins,
                    "return_on_assets": return_on_assets,
                },
                fallback_reason=fallback_reason,
            )
        ]


def _compute_sector_underperformance(sector: str | None, pe_ratio: float, performance_52w: float) -> float:
    """Compute underperformance vs sector median.

    Returns positive value if underperforming (e.g., 15 = 15% below sector median).
    Uses PE multiple as primary signal (lower = cheaper).
    """
    if not sector:
        return 0.0

    # Sector median P/E ratios (from market data)
    sector_pe_medians = {
        "Information Technology": 25.0,
        "Healthcare": 18.0,
        "Financials": 12.0,
        "Consumer Cyclical": 15.0,
        "Consumer Defensive": 20.0,
        "Energy": 10.0,
        "Materials": 11.0,
        "Communication Services": 22.0,
    }

    sector_median_pe = sector_pe_medians.get(sector, 15.0)

    if pe_ratio <= 0:
        return 0.0

    # Compute P/E discount (negative = overvalued, positive = undervalued)
    pe_discount = ((sector_median_pe - pe_ratio) / sector_median_pe) * 100

    # Clip to reasonable range (e.g., -30% to +60%)
    return max(0, min(pe_discount, 60.0))


def _load_fixture(dirpath: str, name: str) -> dict:
    p = Path(dirpath) / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}
