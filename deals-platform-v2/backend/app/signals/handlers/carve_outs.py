"""CS2 — Carve-out signal handlers."""
from __future__ import annotations

from app.models.orm import Company, Evidence
from app.signals.handlers.origination import _confidence_from_evidence, _recent, _signal
from app.signals.registry import SignalResult


def segment_margin_drift(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [e for e in evs if e.kind == "xbrl_segment"
               and (e.meta or {}).get("margin_trend_1y", 0) < -0.02]
    if not matches:
        return SignalResult(strength=0.0, confidence=0.1, evidence_ids=[], detail={})
    worst = min((e.meta or {}).get("margin_trend_1y", 0) for e in matches)
    strength = min(1.0, abs(worst) * 10)  # -10pp -> 1.0
    return SignalResult(
        strength=round(strength, 3),
        confidence=_confidence_from_evidence(matches),
        evidence_ids=[e.id for e in matches[:3]],
        detail={"worst_trend": worst},
    )


def covenant_headroom(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in evs
        if any(k in (e.snippet or "").lower()
               for k in ("covenant", "waiver", "headroom", "amendment"))
    ]
    return _signal(matches, base=0.6)


def activist_breakup(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in _recent(evs, 365)
        if any(k in (e.title or "").lower() + (e.snippet or "").lower()
               for k in ("break up", "break-up", "spin off", "spin-off", "activist", "push to divest"))
    ]
    return _signal(matches, base=0.7)


def peer_divestment(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in _recent(evs, 365)
        if e.kind == "news"
        and any(k in (e.title or "").lower()
                for k in ("divest", "sells", "carve-out", "carve out", "spin"))
    ]
    return _signal(matches, base=0.4)


def rating_watch(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [
        e for e in evs
        if any(k in (e.title or "").lower()
               for k in ("downgrade", "rating watch", "negative outlook", "credit watch"))
    ]
    return _signal(matches, base=0.65)


def segment_reported(company: Company, evs: list[Evidence]) -> SignalResult:
    matches = [e for e in evs if e.kind == "xbrl_segment"]
    if not matches:
        return SignalResult(strength=0.2, confidence=0.3, evidence_ids=[], detail={})
    # More segments reported over more years -> higher feasibility
    years = {(e.meta or {}).get("fy") for e in matches}
    strength = min(1.0, 0.3 + 0.1 * len(matches) + 0.1 * len(years))
    return SignalResult(
        strength=round(strength, 3),
        confidence=_confidence_from_evidence(matches),
        evidence_ids=[e.id for e in matches[:3]],
        detail={"segments": len(matches), "years": len(years)},
    )


def strategic_review_language(company: Company, evs: list[Evidence]) -> SignalResult:
    needles = (
        "strategic review", "portfolio review", "non-core", "non core",
        "explore alternatives", "review its portfolio",
    )
    matches = [
        e for e in evs
        if any(n in (e.snippet or "").lower() or n in (e.title or "").lower() for n in needles)
    ]
    return _signal(matches, base=0.7)
