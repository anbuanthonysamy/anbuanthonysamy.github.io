"""SEC EDGAR adapter. Live with fixture fallback."""
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


class EdgarSubmissions(Source):
    id = "edgar.submissions"
    name = "SEC EDGAR Submissions"
    scope = DataScope.PUBLIC

    def fetch(self, cik: str, company_name: str | None = None, api_mode: str = "live", **_: object) -> list[RawItem]:
        s = get_settings()
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        headers = {"User-Agent": s.sec_user_agent, "Accept-Encoding": "gzip, deflate"}

        items: list[RawItem] = []
        mode = SourceMode.LIVE
        try:
            with httpx.Client(timeout=10) as cli:
                resp = cli.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            if api_mode == "live":
                # In live mode, don't fall back — propagate the error
                raise
            # In offline mode, fall back to fixture
            log.warning("edgar live fetch failed (%s): falling back to fixture", e)
            data = _load_fixture(s.fixtures_dir, f"edgar_submissions_{cik}.json")
            mode = SourceMode.FIXTURE

        name = data.get("name") or company_name or cik
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        primary = filings.get("primaryDocument", [])
        for i, form in enumerate(forms[:50]):
            accession = accessions[i] if i < len(accessions) else ""
            filed_at = _parse_date(dates[i] if i < len(dates) else None)
            doc = primary[i] if i < len(primary) else ""
            kind = _form_to_kind(form)
            acc_no_dash = accession.replace("-", "")
            furl = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{acc_no_dash}/{doc}"
            )
            items.append(
                RawItem(
                    kind=kind,
                    source_id=self.id,
                    title=f"{name} {form} filed {filed_at.date() if filed_at else ''}",
                    url=furl,
                    snippet=None,
                    published_at=filed_at,
                    scope=DataScope.PUBLIC,
                    mode=mode,
                    company_cik=cik,
                    company_name=name,
                    meta={"form": form, "accession": accession},
                )
            )
        return items


class EdgarCompanyFacts(Source):
    id = "edgar.xbrl_companyfacts"
    name = "SEC EDGAR XBRL Company Facts"
    scope = DataScope.PUBLIC

    def fetch(self, cik: str, company_name: str | None = None, api_mode: str = "live", **_: object) -> list[RawItem]:
        s = get_settings()
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        headers = {"User-Agent": s.sec_user_agent, "Accept-Encoding": "gzip, deflate"}

        items: list[RawItem] = []
        mode = SourceMode.LIVE
        try:
            with httpx.Client(timeout=15) as cli:
                r = cli.get(url, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            if api_mode == "live":
                # In live mode, don't fall back — propagate the error
                raise
            # In offline mode, fall back to fixture
            log.warning("edgar xbrl live fetch failed (%s): fallback fixture", e)
            data = _load_fixture(s.fixtures_dir, f"edgar_companyfacts_{cik}.json")
            mode = SourceMode.FIXTURE

        name = data.get("entityName") or company_name or cik
        facts = data.get("facts", {}).get("us-gaap", {})

        # Per-concept annual values yield one RawItem per (concept, year).
        for concept, payload in facts.items():
            if concept not in (
                "Revenues",
                "Revenue",
                "OperatingIncomeLoss",
                "GrossProfit",
                "CostOfRevenue",
                "AccountsReceivableNetCurrent",
                "AccountsPayableCurrent",
                "InventoryNet",
                "LongTermDebt",
            ):
                continue
            units = payload.get("units", {})
            usd = units.get("USD", [])
            for row in usd:
                fy = row.get("fy")
                if row.get("fp") not in ("FY",):
                    continue
                items.append(
                    RawItem(
                        kind="xbrl_fact",
                        source_id=self.id,
                        title=f"{name} {concept} FY{fy}",
                        url=row.get("accn"),
                        snippet=f"{concept}={row.get('val')} USD",
                        published_at=_parse_date(row.get("end")),
                        scope=DataScope.PUBLIC,
                        mode=mode,
                        company_cik=cik,
                        company_name=name,
                        meta={"concept": concept, "fy": fy, "val": row.get("val")},
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


def _form_to_kind(form: str) -> str:
    form = (form or "").upper()
    if form.startswith("10-K"):
        return "filing_10k"
    if form.startswith("10-Q"):
        return "filing_10q"
    if form.startswith("8-K"):
        return "filing_8k"
    if form.startswith("SC 13D"):
        return "filing_13d"
    if form.startswith("SC 13G"):
        return "filing_13g"
    if form.startswith("DEF 14A"):
        return "filing_def14a"
    return "filing_other"
