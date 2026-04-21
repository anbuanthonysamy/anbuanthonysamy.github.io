"""Seed a demo environment: companies, segments, evidence rows for CS1/CS2.

Run inside the backend container:
    docker compose exec backend python -m scripts.seed_demo

Produces enough data for each of the four modules to demo end-to-end.
Uses fixture data only (no live calls).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

# Allow running from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db import init_db, session_scope  # noqa: E402
from app.models.enums import DataScope, SourceMode  # noqa: E402
from app.models.orm import Benchmark, Company, Segment  # noqa: E402
from app.shared.evidence import upsert_evidence  # noqa: E402


def _utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc)


def run() -> None:
    init_db()
    with session_scope() as db:
        # ----- Companies (fixture market data) -----
        companies = [
            Company(ticker="CONS", cik="1111111", name="Consumer Corp",
                    sector="Consumer", country="US", market_cap_usd=12_500_000_000),
            Company(ticker="INDL", cik="2222222", name="Industrial Inc",
                    sector="Industrials", country="US", market_cap_usd=8_200_000_000),
            Company(ticker="TECH", cik="3333333", name="Tech Giant",
                    sector="Technology", country="US", market_cap_usd=210_000_000_000),
            Company(ticker="RETL", cik="4444444", name="Retail Co",
                    sector="Consumer", country="US", market_cap_usd=3_400_000_000),
            Company(ticker="CHEM", cik="5555555", name="Chemicals PLC",
                    sector="Industrials", country="US", market_cap_usd=6_100_000_000),
        ]
        db.add_all(companies)
        db.flush()

        by_name = {c.name: c for c in companies}

        # Segments for Consumer Corp and Industrial Inc (CS2 demo)
        segments = [
            Segment(company_id=by_name["Consumer Corp"].id, name="Agricultural Chemicals",
                    revenue_usd=1_800_000_000, ebitda_usd=180_000_000,
                    margin=0.10, margin_trend_1y=-0.03),
            Segment(company_id=by_name["Consumer Corp"].id, name="Home & Garden",
                    revenue_usd=3_200_000_000, ebitda_usd=540_000_000,
                    margin=0.17, margin_trend_1y=0.01),
            Segment(company_id=by_name["Industrial Inc"].id, name="Specialty Chemicals",
                    revenue_usd=2_400_000_000, ebitda_usd=220_000_000,
                    margin=0.09, margin_trend_1y=-0.04),
            Segment(company_id=by_name["Industrial Inc"].id, name="Heavy Machinery",
                    revenue_usd=4_500_000_000, ebitda_usd=630_000_000,
                    margin=0.14, margin_trend_1y=-0.005),
            Segment(company_id=by_name["Tech Giant"].id, name="Cloud Services",
                    revenue_usd=45_000_000_000, ebitda_usd=18_000_000_000,
                    margin=0.40, margin_trend_1y=0.02),
            Segment(company_id=by_name["Tech Giant"].id, name="Legacy Hardware",
                    revenue_usd=12_000_000_000, ebitda_usd=900_000_000,
                    margin=0.075, margin_trend_1y=-0.025),
        ]
        db.add_all(segments)
        db.flush()

        # ----- Evidence rows from fixtures -----
        news = json.loads((ROOT / "fixtures" / "news_google.json").read_text())

        # Map each fixture article to a company based on substring in title
        for item in news["entries"]:
            title = item["title"]
            target = None
            for name in by_name:
                if name.split()[0].lower() in title.lower():
                    target = by_name[name]
                    break

            pub = None
            raw = item.get("published")
            if raw:
                try:
                    from email.utils import parsedate_to_datetime
                    pub = parsedate_to_datetime(raw)
                except Exception:
                    pub = None

            upsert_evidence(
                db,
                source_id="news.google_rss",
                scope=DataScope.PUBLIC,
                mode=SourceMode.FIXTURE,
                kind="news",
                title=title,
                snippet=item.get("summary"),
                url=item.get("link"),
                company_id=target.id if target else None,
                published_at=pub,
            )

        # Filings — a few 10-K / 10-Q / 8-K / 13D stubs
        upsert_evidence(
            db, source_id="edgar.submissions", scope=DataScope.PUBLIC, mode=SourceMode.FIXTURE,
            kind="filing_13d",
            title="Elliott Management SC 13D — Consumer Corp (3% stake)",
            snippet="Elliott files 13D disclosing 3% stake and intent to engage management on strategic alternatives.",
            url="https://example.com/filings/consumer-13d.htm",
            company_id=by_name["Consumer Corp"].id,
            published_at=_utc("2024-04-05T00:00:00"),
        )
        upsert_evidence(
            db, source_id="edgar.submissions", scope=DataScope.PUBLIC, mode=SourceMode.FIXTURE,
            kind="filing_10q",
            title="Industrial Inc 10-Q — covenant headroom tightened; refinancing window 2025",
            snippet="Management discusses covenant headroom and upcoming maturities over the next 12-18 months.",
            url="https://example.com/filings/industrial-10q.htm",
            company_id=by_name["Industrial Inc"].id,
            published_at=_utc("2024-06-01T00:00:00"),
        )
        upsert_evidence(
            db, source_id="edgar.submissions", scope=DataScope.PUBLIC, mode=SourceMode.FIXTURE,
            kind="filing_8k",
            title="Retail Co 8-K — CEO appointment and strategic review",
            snippet="Board appoints new CEO; strategic review to explore alternatives including sale.",
            url="https://example.com/filings/retail-8k.htm",
            company_id=by_name["Retail Co"].id,
            published_at=_utc("2024-07-22T00:00:00"),
        )

        # XBRL segment evidence (drives CS2 segment_margin_drift / segment_reported)
        for seg in segments:
            upsert_evidence(
                db, source_id="edgar.xbrl_companyfacts",
                scope=DataScope.PUBLIC, mode=SourceMode.FIXTURE,
                kind="xbrl_segment",
                title=f"{seg.name} segment — FY24 margin={seg.margin:.0%} trend={seg.margin_trend_1y:+.0%}",
                snippet=f"Segment revenue {seg.revenue_usd:,.0f} EBITDA {seg.ebitda_usd:,.0f}",
                company_id=seg.company_id,
                meta={
                    "segment_id": seg.id,
                    "segment_name": seg.name,
                    "margin": seg.margin,
                    "margin_trend_1y": seg.margin_trend_1y,
                    "fy": 2024,
                },
            )

        # Market snapshots for scale_band
        market = json.loads((ROOT / "fixtures" / "market_yf.json").read_text())
        for ticker, row in market.items():
            co = next((c for c in companies if c.ticker == ticker), None)
            if co is None:
                continue
            upsert_evidence(
                db, source_id="market.yfinance",
                scope=DataScope.PUBLIC, mode=SourceMode.FIXTURE,
                kind="market",
                title=f"{row['name']} market snapshot",
                snippet=f"price={row['last_price']} mcap={row['market_cap']}",
                url=f"https://finance.yahoo.com/quote/{ticker}",
                company_id=co.id,
                meta={"market_cap": row["market_cap"]},
            )

        # CS4 fallback benchmarks for the sectors we seed
        for sector in ("Consumer", "Industrials", "Technology", "Generic"):
            for metric, (p40, p50, p60) in {
                "DSO": (42.0, 50.0, 60.0),
                "DPO": (35.0, 45.0, 55.0),
                "DIO": (40.0, 55.0, 75.0),
            }.items():
                db.add(
                    Benchmark(
                        module="working_capital",
                        sector=sector,
                        metric=metric,
                        p40=p40, p50=p50, p60=p60,
                        sample_size=12,
                        evidence_ids=[],
                    )
                )

        print(f"Seeded {len(companies)} companies, {len(segments)} segments, "
              "news/filing/xbrl/market evidence and default benchmarks.")


if __name__ == "__main__":
    run()
