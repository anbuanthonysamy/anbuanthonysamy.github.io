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

    def fetch(self, ticker: str, **_: object) -> list[RawItem]:
        s = get_settings()
        mode = SourceMode.LIVE
        try:
            import yfinance  # type: ignore

            t = yfinance.Ticker(ticker)
            info = t.fast_info
            mcap = float(getattr(info, "market_cap", 0) or 0)
            price = float(getattr(info, "last_price", 0) or 0)
            name = getattr(t, "info", {}).get("shortName", ticker) if hasattr(t, "info") else ticker
        except Exception as e:
            log.warning("yfinance live fetch failed (%s): fallback fixture", e)
            fx = _load_fixture(s.fixtures_dir, "market_yf.json")
            row = fx.get(ticker, {})
            mcap = float(row.get("market_cap", 0) or 0)
            price = float(row.get("last_price", 0) or 0)
            name = row.get("name") or ticker
            mode = SourceMode.FIXTURE

        now = dt.datetime.now(dt.timezone.utc)
        return [
            RawItem(
                kind="market",
                source_id=self.id,
                title=f"{name} market snapshot",
                url=f"https://finance.yahoo.com/quote/{ticker}",
                snippet=f"price={price} mcap={mcap}",
                published_at=now,
                scope=DataScope.PUBLIC,
                mode=mode,
                company_ticker=ticker,
                company_name=name,
                meta={"market_cap": mcap, "last_price": price},
            )
        ]


def _load_fixture(dirpath: str, name: str) -> dict:
    p = Path(dirpath) / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}
