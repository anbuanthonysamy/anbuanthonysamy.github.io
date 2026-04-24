"""CS1 — M&A origination signal handlers.

Each function takes (company, evidence_list) and returns a SignalResult.
Deterministic: scoring math is pure; LLM extraction is called once at
ingest time to tag evidence with booleans, then consumed here.
"""
from __future__ import annotations

import datetime as dt

from app.models.orm import Company, Evidence
from app.signals.registry import SignalResult


def _confidence_from_evidence(evs: list[Evidence]) -> float:
    if not evs:
        return 0.0
    kinds = {e.kind for e in evs}
    source_diversity = min(1.0, len({e.source_id for e in evs}) / 3.0)
    kind_diversity = min(1.0, len(kinds) / 3.0)
    return round(0.5 * source_diversity + 0.5 * kind_diversity, 3)


def _recent(evs: list[Evidence], days: int) -> list[Evidence]:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    def _aware(x: dt.datetime | None) -> dt.datetime | None:
        if x is None:
            return None
        return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)

    out = []
    for e in evs:
        pub = _aware(e.published_at)
        got = _aware(e.retrieved_at)
        if (pub and pub >= cutoff) or (got and got >= cutoff):
            out.append(e)
    return out


def _signal(matches: list[Evidence], base: float) -> SignalResult:
    if not matches:
        return SignalResult(strength=0.0, confidence=0.0, evidence_ids=[], detail={})
    strength = min(1.0, base + 0.05 * len(matches))
    return SignalResult(
        strength=strength,
        confidence=_confidence_from_evidence(matches),
        evidence_ids=[e.id for e in matches[:5]],
        detail={"hits": len(matches)},
    )


def activist_13d(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [e for e in evs if e.kind == "filing_13d"]
    return _signal(matches, base=0.7)


def refi_window_12_24m(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [e for e in evs if "refinanc" in (e.snippet or "").lower()
               or "matur" in (e.snippet or "").lower()]
    return _signal(matches, base=0.5)


def adjacent_deals(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in _recent(evs, 180)
        if e.kind == "news"
        and any(k in (e.title or "").lower()
                for k in ("acqui", "merger", "deal", "takeover", "consolidat"))
    ]
    return _signal(matches, base=0.4)


def mgmt_change(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in _recent(evs, 365)
        if any(k in (e.title or "").lower()
               for k in ("ceo", "chief executive", "cfo", "chair"))
        and any(k in (e.title or "").lower() for k in ("appoint", "step down", "resign", "new"))
    ]
    return _signal(matches, base=0.45)


def strategic_review_language(company: Company, evs: list[Evidence]) -> SignalResult:
    needles = ("strategic review", "strategic alternatives", "explore options",
               "explore strategic", "review its portfolio")
    matches = [
        e for e in evs
        if any(n in (e.snippet or "").lower() or n in (e.title or "").lower() for n in needles)
    ]
    return _signal(matches, base=0.75)


def scale_band(company: Company, evs: list[Evidence]) -> SignalResult:
    """Convert market-cap to an [0,1] band: $1bn -> 0.1, $50bn+ -> 1.0."""
    mcap = company.market_cap_usd or 0.0
    if mcap <= 0:
        return SignalResult(strength=0.0, confidence=0.1, evidence_ids=[], detail={"mcap": 0})
    import math

    strength = max(0.0, min(1.0, math.log10(max(mcap, 1)) / math.log10(50e9)))
    return SignalResult(
        strength=round(strength, 3),
        confidence=0.9,
        evidence_ids=[e.id for e in evs if e.kind == "market"][:2],
        detail={"mcap_usd": mcap},
    )


def sector_weight(company: Company, evs: list[Evidence]) -> SignalResult:
    """Neutral default; configurable weighting lives in settings."""
    return SignalResult(strength=0.5, confidence=0.5, evidence_ids=[], detail={})
