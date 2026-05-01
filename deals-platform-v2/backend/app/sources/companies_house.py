"""UK Companies House adapter (requires COMPANIES_HOUSE_API_KEY)."""
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


def search_company_number(name: str) -> str | None:
    """Resolve a company name to a UK Companies House company number.

    Uses the authenticated /search/companies endpoint. Returns the top match's
    company_number, or None if no match is found or the API key is missing.

    Picks the first ``active`` PLC result when available; otherwise the first
    result returned by the search.
    """
    s = get_settings()
    if not s.companies_house_api_key:
        return None
    url = "https://api.company-information.service.gov.uk/search/companies"
    try:
        with httpx.Client(timeout=10, auth=(s.companies_house_api_key, "")) as cli:
            r = cli.get(url, params={"q": name, "items_per_page": 10})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("companies house search failed for %r: %s", name, e)
        return None

    items = data.get("items", []) or []
    if not items:
        return None

    # Prefer an active PLC match, falling back to first result.
    for item in items:
        title = (item.get("title") or "").upper()
        status = (item.get("company_status") or "").lower()
        if "PLC" in title and status == "active":
            return item.get("company_number")
    return items[0].get("company_number")


class CompaniesHouse(Source):
    id = "reg.companies_house"
    name = "UK Companies House"
    scope = DataScope.PUBLIC
    is_stub = False
    description = (
        "UK Companies House registry — official company records (status, SIC codes, "
        "incorporation date). Requires COMPANIES_HOUSE_API_KEY env var. Free, "
        "600 req/5min."
    )
    homepage_url = "https://developer.company-information.service.gov.uk/"

    def fetch(self, company_number: str, **_: object) -> list[RawItem]:
        s = get_settings()
        mode = SourceMode.LIVE
        fallback_reason: str | None = None
        try:
            if not s.companies_house_api_key:
                raise RuntimeError("COMPANIES_HOUSE_API_KEY not configured")
            url = f"https://api.company-information.service.gov.uk/company/{company_number}"
            with httpx.Client(timeout=10, auth=(s.companies_house_api_key, "")) as cli:
                r = cli.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            log.warning("companies house fetch failed (%s): fallback fixture", e)
            if "COMPANIES_HOUSE_API_KEY not configured" in str(e):
                fallback_reason = "COMPANIES_HOUSE_API_KEY not configured"
            else:
                fallback_reason = f"Live fetch failed: {type(e).__name__}: {str(e)[:200]}"
            fx = _load_fixture(s.fixtures_dir, f"companies_house_{company_number}.json")
            data = fx
            mode = SourceMode.FIXTURE

        name = data.get("company_name") or company_number
        return [
            RawItem(
                kind="registry",
                source_id=self.id,
                title=f"{name} UK registry entry",
                url=f"https://find-and-update.company-information.service.gov.uk/company/{company_number}",
                snippet=json.dumps({k: data.get(k) for k in ("company_status", "sic_codes", "date_of_creation") if data.get(k)}),
                published_at=dt.datetime.now(dt.timezone.utc),
                scope=DataScope.PUBLIC,
                mode=mode,
                company_name=name,
                meta={"company_number": company_number, "sic_codes": data.get("sic_codes")},
                fallback_reason=fallback_reason,
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
