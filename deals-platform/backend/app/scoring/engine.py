"""Scoring engine.

Deterministic: inputs -> outputs is pure. Weights come from the SettingKV
table (editable in /settings) with fallbacks defined per-module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Module
from app.models.orm import SettingKV

# Defaults mirror docs/scoring-framework.md
DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    Module.ORIGINATION.value: {
        "likelihood": 0.30,
        "expected_scale": 0.20,
        "timing_fit": 0.15,
        "confidence": 0.15,
        "sector_relevance": 0.10,
        "strategic_relevance": 0.10,
    },
    Module.CARVE_OUTS.value: {
        "divestment_likelihood": 0.30,
        "urgency": 0.20,
        "feasibility": 0.20,
        "expected_value": 0.15,
        "confidence": 0.15,
    },
    Module.POST_DEAL.value: {
        "value_at_risk": 0.30,
        "urgency": 0.20,
        "business_impact": 0.20,
        "confidence": 0.15,
        "intervention_priority": 0.15,
    },
    Module.WORKING_CAPITAL.value: {
        "cash_unlock_potential": 0.35,
        "ease_of_action": 0.20,
        "operational_risk": 0.15,  # inverted at assembly time
        "confidence": 0.15,
        "implementation_priority": 0.15,
    },
}


@dataclass
class ScoreBundle:
    dimensions: dict[str, float]
    weights: dict[str, float]
    confidence: float
    score: float


def load_weights(db: Session, module: str) -> dict[str, float]:
    row = db.scalar(select(SettingKV).where(SettingKV.key == f"weights.{module}"))
    if row and isinstance(row.value, dict):
        return {k: float(v) for k, v in row.value.items()}
    return DEFAULT_WEIGHTS[module]


def save_weights(db: Session, module: str, weights: Mapping[str, float]) -> None:
    key = f"weights.{module}"
    row = db.scalar(select(SettingKV).where(SettingKV.key == key))
    if row is None:
        db.add(SettingKV(key=key, value=dict(weights)))
    else:
        row.value = dict(weights)
    db.flush()


def confidence_shape(c: float) -> float:
    """Dampen but don't zero low-confidence scores."""
    c = max(0.0, min(1.0, c))
    return 0.5 + 0.5 * c


def compose(
    dimensions: Mapping[str, float],
    weights: Mapping[str, float],
    confidence: float,
) -> ScoreBundle:
    weight_sum = sum(weights.values()) or 1.0
    norm = {k: v / weight_sum for k, v in weights.items()}
    subtotal = 0.0
    for k, w in norm.items():
        subtotal += w * max(0.0, min(1.0, float(dimensions.get(k, 0.0))))
    shaped = subtotal * confidence_shape(confidence)
    return ScoreBundle(
        dimensions=dict(dimensions),
        weights=dict(norm),
        confidence=confidence,
        score=round(shaped, 4),
    )
