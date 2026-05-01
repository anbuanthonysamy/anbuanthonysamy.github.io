"""FRED (St Louis Fed) macro data."""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

import httpx

from app.config import get_settings
from app.models.enums import DataScope, SourceMode
from app.sources.base import RawItem, Source

log = logging.getLogger(__name__)


class FRED(Source):
    id = "macro.fred"
    name = "FRED (St Louis Fed)"
    scope = DataScope.PUBLIC
    is_stub = False
    description = (
        "Federal Reserve Economic Data (FRED) — official US macroeconomic time series "
        "(treasury yields, CPI, etc.). Requires FRED_API_KEY environment variable. "
        "Free, 120 req/min."
    )
    homepage_url = "https://fred.stlouisfed.org/docs/api/fred/"

    def fetch(self, series: str = "DGS10", **_: object) -> list[RawItem]:
        s = get_settings()
        mode = SourceMode.LIVE
        fallback_reason: str | None = None
        url = "https://api.stlouisfed.org/fred/series/observations"
        items: list[RawItem] = []
        try:
            if not s.fred_api_key:
                raise RuntimeError("FRED_API_KEY not configured")
            with httpx.Client(timeout=10) as cli:
                r = cli.get(
                    url,
                    params={"series_id": series, "api_key": s.fred_api_key, "file_type": "json"},
                )
                r.raise_for_status()
                data = r.json()
                obs = data.get("observations", [])[-12:]
        except Exception as e:
            log.warning("fred live fetch failed (%s): fallback fixture", e)
            if "FRED_API_KEY not configured" in str(e):
                fallback_reason = "FRED_API_KEY not configured"
            else:
                fallback_reason = f"Live fetch failed: {type(e).__name__}: {str(e)[:200]}"
            fx = _load_fixture(s.fixtures_dir, f"fred_{series}.json")
            obs = fx.get("observations", [])[-12:]
            mode = SourceMode.FIXTURE

        for o in obs:
            val = o.get("value")
            if val in (".", None):
                continue
            items.append(
                RawItem(
                    kind="macro",
                    source_id=self.id,
                    title=f"FRED {series} {o.get('date')} = {val}",
                    url=f"https://fred.stlouisfed.org/series/{series}",
                    snippet=f"{series}={val} on {o.get('date')}",
                    published_at=_parse_date(o.get("date")),
                    scope=DataScope.PUBLIC,
                    mode=mode,
                    meta={"series": series, "value": float(val)},
                    fallback_reason=fallback_reason,
                )
            )
        return items


def _load_fixture(dirpath: str, name: str) -> dict:
    p = Path(dirpath) / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _parse_date(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
