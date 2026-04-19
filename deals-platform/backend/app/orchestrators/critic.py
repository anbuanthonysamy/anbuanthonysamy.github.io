"""Critic — rubric-scores the chain's output and re-runs if below threshold."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CriticReport:
    score: float  # 0..1
    passes: bool
    notes: list[str]


def rubric_score(situation: dict) -> CriticReport:
    notes: list[str] = []
    score = 1.0

    if not situation.get("evidence_ids"):
        score -= 0.4
        notes.append("No evidence attached.")
    if not situation.get("explanation"):
        score -= 0.3
        notes.append("No explanation text.")
    elif len(situation["explanation"]) < 40:
        score -= 0.1
        notes.append("Explanation too short.")
    dims = situation.get("dimensions") or {}
    if sum(dims.values()) == 0:
        score -= 0.3
        notes.append("All dimensions zero.")
    if (situation.get("confidence") or 0) < 0.2:
        score -= 0.1
        notes.append("Low confidence (< 0.2).")
    if not situation.get("next_action"):
        score -= 0.1
        notes.append("No next action.")
    score = max(0.0, score)
    return CriticReport(score=round(score, 3), passes=score >= 0.7, notes=notes)
