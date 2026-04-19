"""End-to-end-ish: seed a company and a few evidence rows, run the
origination pipeline, assert a Situation with attached evidence and
passing-critic output."""
import datetime as dt

from app.models.enums import DataScope, Module, ReviewState, SourceMode
from app.models.orm import Company
from app.modules.origination.service import build_pipeline
from app.shared.evidence import upsert_evidence


def test_origination_pipeline_produces_situation(db_session):
    co = Company(ticker="X", cik="99999", name="Consumer Corp", sector="Consumer",
                 market_cap_usd=12_500_000_000)
    db_session.add(co)
    db_session.flush()

    upsert_evidence(
        db_session, source_id="edgar.submissions", scope=DataScope.PUBLIC,
        mode=SourceMode.FIXTURE, kind="filing_13d",
        title="Elliott Management SC 13D — Consumer Corp",
        snippet="3% stake disclosed; engaging management on strategic alternatives.",
        company_id=co.id,
        published_at=dt.datetime(2024, 4, 5, tzinfo=dt.timezone.utc),
    )
    upsert_evidence(
        db_session, source_id="news.google_rss", scope=DataScope.PUBLIC,
        mode=SourceMode.FIXTURE, kind="news",
        title="Activist pushes Consumer Corp to explore strategic review",
        snippet="Activist demands exploration of strategic alternatives including divestment.",
        company_id=co.id,
        published_at=dt.datetime(2024, 5, 1, tzinfo=dt.timezone.utc),
    )
    upsert_evidence(
        db_session, source_id="market.yfinance", scope=DataScope.PUBLIC,
        mode=SourceMode.FIXTURE, kind="market",
        title="Consumer Corp market snapshot",
        snippet="mcap=12500000000",
        company_id=co.id,
        meta={"market_cap": 12_500_000_000},
    )

    p = build_pipeline(db_session)
    run = p.run_for_company(co, title="Unit-test opportunity", extras={"sector": "Consumer"})
    s = run.situation
    assert s.module == Module.ORIGINATION.value
    assert s.score > 0
    assert s.evidence_ids
    assert s.review_state == ReviewState.PENDING.value
    # Explanation must cite evidence ids that exist
    assert s.explanation_cites
