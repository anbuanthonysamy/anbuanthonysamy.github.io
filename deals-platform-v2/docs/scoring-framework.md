# Scoring framework

Per-module score dimensions, default weights, and the calibration path.
All weights are editable at runtime through `/settings` and persisted in
the `setting` table.

## General contract

Every scored object (Opportunity, Situation, Deviation, Recommendation)
has:

- `dimensions: dict[str, float]` — each in [0, 1]
- `weights: dict[str, float]` — module-level weights summing to 1
- `confidence: float` in [0, 1] — derived from evidence coverage and
  agreement between signals
- `score = sum(dimensions[k] * weights[k] for k in dimensions) * confidence_shape(confidence)`
  where `confidence_shape(c) = 0.5 + 0.5 * c` so low-confidence items are
  not suppressed to zero but are visibly dampened.

The golden-set regression test in `backend/tests/test_scoring_golden.py`
asserts that recomputing scores on the seeded fixtures does not drift by
more than ±0.02 vs the recorded baseline.

## CS1 — M&A Origination

| Dimension | Default weight | Signals feeding it |
|-----------|---------------:|--------------------|
| likelihood         | 0.30 | activist_13d, refi_window, adjacent_deals, mgmt_change, strategic_review_language |
| expected_scale     | 0.20 | market_cap, ev_band, historical_premia |
| timing_fit         | 0.15 | news_recency_decay, refi_maturity_12_24m, 8K_cadence |
| confidence         | 0.15 | evidence_count, source_diversity, signal_agreement |
| sector_relevance   | 0.10 | sector_weight (configurable) |
| strategic_relevance| 0.10 | deal_size_band_preference, geography_preference |

Elevated-likelihood threshold: `score >= 0.55` (configurable).

## CS2 — Carve-outs

| Dimension | Default weight | Signals feeding it |
|-----------|---------------:|--------------------|
| divestment_likelihood | 0.30 | segment_margin_drift, strategic_review_language, activist_breakup, peer_divestment |
| urgency               | 0.20 | covenant_headroom, refi_window_6_18m, rating_watch |
| feasibility           | 0.20 | segment_reported, distinct_leadership, comparable_precedent |
| expected_value        | 0.15 | segment_revenue_ev_comp, industry_multiple |
| confidence            | 0.15 | evidence_count, source_diversity |

## CS3 — Post-deal

| Dimension | Default weight |
|-----------|---------------:|
| value_at_risk    | 0.30 |
| urgency          | 0.20 |
| business_impact  | 0.20 |
| confidence       | 0.15 |
| intervention_priority | 0.15 |

Deviation detection: actual vs target-band (linear/S/J-curve). A KPI
crossing out of its band for 2 consecutive refreshes flags a `Deviation`.

## CS4 — Working capital

| Dimension | Default weight |
|-----------|---------------:|
| cash_unlock_potential | 0.35 |
| ease_of_action        | 0.20 |
| operational_risk      | 0.15 (inverted — lower is better) |
| confidence            | 0.15 |
| implementation_priority | 0.15 |

Cash unlock:
```
unlock_low  = max(0, (subject_days - peer_p60) * daily_driver)
unlock_mid  = max(0, (subject_days - peer_p50) * daily_driver)
unlock_high = max(0, (subject_days - peer_p40) * daily_driver)
```
where `daily_driver` is revenue/365 for AR, COGS/365 for AP and inventory.

## Calibration

Human reviewers label outputs on a 1–10 scale with a short reason. A
nightly job (disabled by default, enabled when ≥50 labels are available)
fits a logistic regression mapping `dimensions -> accepted` and proposes
new weights. Proposals appear in `/eval` for human approval before
activation. This is gated behind the `CALIBRATION_ENABLED` env var.
