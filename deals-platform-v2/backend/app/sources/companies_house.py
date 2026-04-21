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


class CompaniesHouse(Source):
    id = "reg.companies_house"
    name = "UK Companies House"
    scope = DataScope.PUBLIC

    def fetch(self, company_number: str, **_: object) -> list[RawItem]:
        s = get_settings()
        mode = SourceMode.LIVE
        try:
            if not s.companies_house_api_key:
                raise RuntimeError("no Companies House key")
            url = f"https://api.company-information.service.gov.uk/company/{company_number}"
            with httpx.Client(timeout=10, auth=(s.companies_house_api_key, "")) as cli:
                r = cli.get(url)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            log.warning("companies house fetch failed (%s): fallback fixture", e)
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
