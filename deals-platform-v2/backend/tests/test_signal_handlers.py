import datetime as dt

from app.models.orm import Company, Evidence
from app.signals.handlers.origination import (
    activist_13d,
    adjacent_deals,
    mgmt_change,
    scale_band,
    strategic_review_language,
)


def _ev(**kw) -> Evidence:
    base = dict(id="e1", source_id="x", scope="public", mode="live",
                kind="news", title="t", snippet="", url=None, file_ref=None,
                retrieved_at=dt.datetime.now(dt.timezone.utc), parsed_at=None,
                published_at=dt.datetime.now(dt.timezone.utc),
                sha256="h", ok=True, meta={})
    base.update(kw)
    return Evidence(**base)


def test_activist_13d_triggers_on_13d_kind():
    co = Company(name="X")
    evs = [_ev(id="e1", kind="filing_13d", title="13D filing")]
    r = activist_13d(co, evs)
    assert r.strength > 0.6


def test_adjacent_deals_keywords():
    co = Company(name="X")
    evs = [_ev(id="e1", kind="news", title="Peer announces acquisition")]
    r = adjacent_deals(co, evs)
    assert r.strength > 0.3


def test_mgmt_change_keywords():
    co = Company(name="X")
    evs = [_ev(id="e1", kind="news", title="New CEO appointed")]
    r = mgmt_change(co, evs)
    assert r.strength > 0.3


def test_strategic_review_language():
    co = Company(name="X")
    evs = [_ev(id="e1", kind="filing_8k", title="Board update",
               snippet="The company has begun a strategic review of non-core assets.")]
    r = strategic_review_language(co, evs)
    assert r.strength > 0.6


def test_scale_band_monotonic():
    small = Company(name="S", market_cap_usd=1_000_000_000)
    big = Company(name="B", market_cap_usd=50_000_000_000)
    r_small = scale_band(small, [])
    r_big = scale_band(big, [])
    assert r_big.strength > r_small.strength
