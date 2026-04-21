"""Golden-set regression for scoring math.

Changing the scoring engine requires updating this file. The tolerance
is ±0.02 per dimension aggregation.
"""
from app.scoring.engine import DEFAULT_WEIGHTS, compose

TOLERANCE = 0.02

GOLDEN = [
    # (module, dimensions, confidence, expected_score)
    ("origination",
     {"likelihood": 0.8, "expected_scale": 0.7, "timing_fit": 0.6,
      "confidence": 0.6, "sector_relevance": 0.5, "strategic_relevance": 0.4},
      0.6, 0.5200),
    ("carve_outs",
     {"divestment_likelihood": 0.75, "urgency": 0.6, "feasibility": 0.7,
      "expected_value": 0.55, "confidence": 0.65},
      0.65, 0.5486),
    ("post_deal",
     {"value_at_risk": 0.6, "urgency": 0.5, "business_impact": 0.55,
      "confidence": 0.7, "intervention_priority": 0.6},
      0.7, 0.4972),
    ("working_capital",
     {"cash_unlock_potential": 0.6, "ease_of_action": 0.5, "operational_risk": 0.3,
      "confidence": 0.7, "implementation_priority": 0.6},
      0.7, 0.4675),
]


def test_golden_scores_stable():
    for module, dims, conf, expected in GOLDEN:
        w = DEFAULT_WEIGHTS[module]
        b = compose(dims, w, confidence=conf)
        assert abs(b.score - expected) <= TOLERANCE, (module, b.score, expected)
