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


class YFinanceMarket(Source):
    id = "market.yfinance"
    name = "Yahoo Finance (yfinance)"
    scope = DataScope.PUBLIC

    def fetch(self, ticker: str, sector: str | None = None, api_mode: str = "live", **_: object) -> list[RawItem]:
        """Fetch market data and compute underperformance vs sector.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')
            sector: Industry sector for comparison (e.g., 'Information Technology')
            api_mode: 'live' (must fetch real data, raise on error) or 'offline' (use fixtures)
        """
        s = get_settings()
        mode = SourceMode.LIVE
        try:
            import yfinance  # type: ignore

            t = yfinance.Ticker(ticker)
            info = t.fast_info
            mcap = float(getattr(info, "market_cap", 0) or 0)
            price = float(getattr(info, "last_price", 0) or 0)
            pe_ratio = float(getattr(info, "trailing_pe", 0) or 0)
            name = getattr(t, "info", {}).get("shortName", ticker) if hasattr(t, "info") else ticker

            # Compute 52-week performance
            history = t.history(period="1y")
            performance_52w = ((price - history.iloc[0]["Close"]) / history.iloc[0]["Close"] * 100) if len(history) > 0 else 0

        except Exception as e:
            if api_mode == "live":
                # In live mode, don't fall back — propagate the error
                raise
            # In offline mode, fall back to fixture
            log.warning("yfinance live fetch failed (%s): fallback fixture", e)
            fx = _load_fixture(s.fixtures_dir, "market_yf.json")
            row = fx.get(ticker, {})
            mcap = float(row.get("market_cap", 0) or 0)
            price = float(row.get("last_price", 0) or 0)
            pe_ratio = float(row.get("pe_ratio", 0) or 0)
            name = row.get("name") or ticker
            performance_52w = float(row.get("performance_52w", 0) or 0)
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
                },
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
