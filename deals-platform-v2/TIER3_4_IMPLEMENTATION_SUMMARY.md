# Tier 3 & 4 Implementation Summary — Advanced Refinement & Polish

## Tier 3: CS2 Signal Refinement

### Overview
Tier 3 adds sophisticated CS2 analysis using multi-year trends, activist pressure detection, peer precedent analysis, and transaction probability modeling. Signals become highly discriminating between spin-off candidates.

### New File: `backend/app/scanner/cs2_tier3_helpers.py`

**Key Functions:**

#### 1. `calculate_margin_trend_3y(current, prior_year, two_year_ago)`
- Analyzes margin trajectory (3-year trend)
- Returns: (trend_score: -1 to 1, trend_direction: str)
- Trend directions:
  - `declining`: >2% annual decline → spin pressure
  - `sharp_decline`: >3% YoY drop → crisis signal
  - `improving`: positive trajectory → less urgent
  - `stable`: stable margins → baseline

**Signal Example:**
```
Current margin: 12%, Prior: 15%, 2-year ago: 18%
→ Declining 2% annually = trend_score -0.7 ("declining")
→ Strong carve-out signal (consistent deterioration)
```

#### 2. `detect_activist_breakup_calls(news_items)`
- Parses news/filings for activist separation pressure
- Keyword detection: "break up", "spin off", "carve out", "strategic review"
- Multi-keyword hits strengthen signal
- Activist + breakup combination = strong signal
- Returns: (signal_score: 0-1, has_breakup_call: bool)

**Signal Example:**
```
News: "Activist investor calls for spinoff of Healthcare division"
→ Keywords: "activist" + "spinoff" = 2 hits
→ signal_score = 0.3 (single article)
→ has_breakup_call = True
```

#### 3. `detect_peer_divestment_patterns(sector, company, peer_news)`
- Detects when peer companies divest similar divisions
- Validates separation thesis (if peer could do it, so can we)
- Extracts divested division names for pattern matching
- Returns: (precedent_score: 0-1, divested_divisions: list[str])

**Signal Example:**
```
Peer "TechCorp" spins off "Software Services" division (same sector)
→ Establishes precedent for separation
→ precedent_score = 0.2 per successful precedent
→ divested_divisions = ["Software Services"]
```

#### 4. `calculate_separation_probability(readiness, activist, precedent, margins, debt)`
- Combines all factors into likelihood of actual spin-off
- Weights: Readiness (30%) + Activist (25%) + Precedent (20%) + Margins (15%) + Debt (10%)
- Returns: Probability 0-1
- Probability = 0.65 → ~65% chance of separation within 2-3 years

**Example:**
```
Readiness: 0.75, Activist: 0.8, Precedent: 0.6, Margins: 0.4, Debt: 0.3
→ probability = (0.75×0.30) + (0.8×0.25) + (0.6×0.20) + (0.4×0.15) + (0.3×0.10)
            = 0.225 + 0.200 + 0.120 + 0.060 + 0.030
            = 0.635 (63.5% probability)
```

#### 5. `apply_multi_threshold_gating(score, equity_value, readiness, probability)`
- Prevents false positives by requiring multiple criteria
- Gates:
  - Equity value ≥ $750M
  - Separation readiness ≥ 0.40
  - Separation probability ≥ 0.20
  - CS2 score ≥ 0.45
- Returns: (should_flag: bool, reason: str)

**Example:**
```
Company: score 0.65, equity $200M, readiness 0.75, probability 0.30
→ Gate 1 fails: Below $750M threshold
→ should_flag = False
→ reason = "Below minimum equity value ($200B < $750M)"
```

---

## Tier 4: Polish & Advanced Scoring

### New File: `backend/app/scanner/tier4_helpers.py`

**Key Functions:**

#### 1. `detect_leadership_changes(filings, news, days_lookback=180)`
- Parses SEC 8-K filings and news for executive transitions
- Flags PE/strategic background appointments (strong M&A signal)
- Looks for CEO, CFO, COO transitions
- Returns: (score: 0-1, changes: list[dict])
- Each change captures: executive name, date, source, background

**Signal Example:**
```
8-K Filing: "CEO John Smith (from Apollo Global) appointed"
→ Executive: "John Smith"
→ Date: 2024-04-15
→ Source: "8-K Filing"
→ Background: "PE/Strategic"
→ score += 0.3 (PE background = strong M&A signal)
```

#### 2. `assess_ownership_structure(insider%, institutional%, activist%)`
- Evaluates spin readiness based on shareholder composition
- Concentrated insider ownership = harder spin (founder resistance)
- High institutional/activist = easier spin (proxy-fighting friendly)
- Returns: (spin_readiness: 0-1, structure_type: str)

**Structure Types:**
- `founder_controlled` (>30% insider): readiness 0.3 (resistant to spin)
- `insider_significant` (10-30%): readiness 0.5
- `institutional_friendly` (>70% inst): readiness 0.75
- `activist_friendly` (>5% activist): readiness 0.9
- `balanced`: readiness 0.6

#### 3. `calculate_transaction_probability_model(cs1, cs2, years_since_deal, pace, sector_activity)`
- Estimates when transaction will occur (temporal dimension)
- Factors:
  - Sector M&A frequency (baseline)
  - Company signal strength (probability boost)
  - Historical acquisition pace (recent acquirers more likely to repeat)
- Returns: Annualized probability (0-1)

**Example:**
```
Company: Recent acquirer (1 year since last deal)
Sector: High M&A activity (0.6 frequency)
Signals: Strong (CS2 = 0.7)

probability = (0.6 × 0.3) + (0.7 × 0.5) + (0.3 [recent])
            = 0.18 + 0.35 + 0.30 = 0.83 (83% prob this year)
```

#### 4. `calculate_deal_value_estimate(equity_value, premium%=25)`
- Adds acquisition premium to current equity value
- Default premium: 25% (typical acquisition range 20-35%)
- Returns: (deal_value, premium_amount)

**Example:**
```
Company equity value: $1.0B
Estimated premium: 25%
→ deal_value = $1.0B + $250M = $1.25B
→ premium = $250M
```

#### 5. `score_deal_attractiveness(deal_cost, ebitda, ev_ebitda_multiple, sector_median)`
- Evaluates valuation appeal to acquirers
- Compares company EV/EBITDA to sector peers
- Discount to sector = attractive (lower cost)
- Premium to sector = expensive
- Returns: (attractiveness: 0-1, assessment: str)

**Assessments:**
- `very_attractive`: >20% discount to sector (0.85)
- `attractive`: 10-20% discount (0.65)
- `fair_value`: 0-10% discount (0.45)
- `slight_premium`: -10% to 0% discount (0.25)
- `expensive`: >10% premium (0.05)

#### 6. `refine_signal_scoring(signals, data_quality, consistency)`
- Adjusts signal confidence based on data reliability
- Poor data quality → confidence discount (0.7x)
- Signal conflicts → confidence discount (0.6x)
- Returns: Refined signals dict with adjustment factors

---

## Integration into Signal Scorers

### CS1 Enhancements (Tier 4):
```python
# Detect leadership changes from 8-K filings
leadership_change_score, changes = detect_leadership_changes(filings)
→ signals["leadership_change_score"] = 0.3-0.8
→ signals["leadership_changes"] = count

# Weighted composite updated:
score = (... + leadership * 0.12 + activist * 0.28)
→ Activist signals = 28% weight (highest)
```

### CS2 Enhancements (Tier 3 & 4):

**Tier 3 Integration:**
```python
# Multi-year margin analysis
margin_trend, direction = calculate_margin_trend_3y(current, prior, 2y_ago)
→ signals["margin_trend_score"] = -0.7 to 0.7
→ signals["margin_trend_direction"] = "declining"

# Activist break-up detection
breakup_signal, has_call = detect_activist_breakup_calls(news)
→ signals["breakup_call_signal"] = 0.3
→ signals["has_breakup_activist_call"] = True

# Peer precedent
precedent, divisions = detect_peer_divestment_patterns(...)
→ signals["peer_precedent_signal"] = 0.2-0.4
→ signals["similar_divestments"] = count

# Separation probability
separation_prob = calculate_separation_probability(...)
→ signals["separation_probability"] = 0.35-0.75

# Multi-threshold gating
should_flag, reason = apply_multi_threshold_gating(...)
→ signals["passes_multi_threshold_gates"] = True/False
```

**Tier 4 Integration:**
```python
# Transaction probability (when?)
transaction_prob = calculate_transaction_probability_model(...)
→ signals["transaction_probability"] = 0.40-0.85

# Deal value estimates
deal_value, premium = calculate_deal_value_estimate(equity)
→ signals["estimated_deal_value_usd"] = $X.XXB
→ signals["acquisition_premium_usd"] = $XXXm
```

### Composite Score Rebalancing:

**CS1 (Tiers 1-4):**
```python
score = (
    underperf * 0.14 +
    pe_disc * 0.14 +
    margin * 0.14 +
    leverage * 0.18 +
    leadership * 0.12 +
    activist * 0.28  # Activist = strongest signal (↑ from 0.20)
)
```

**CS2 (Tiers 1-4):**
```python
score = (
    debt_stress * 0.16 +      # Tier 2
    segment_perf * 0.16 +     # Tier 2
    discount * 0.14 +         # Tier 2
    separation * 0.18 +       # Tier 2
    capital_stress * 0.12 +   # Tier 2
    margin_trend * 0.08 +     # Tier 3 (new)
    breakup_signal * 0.10 +   # Tier 3 (new)
    peer_precedent * 0.06     # Tier 3 (new)
) * probability_factor        # Tier 3 gating (0.7-1.0)
```

---

## Testing & Validation

**Expected Behavior After All Tiers:**

1. **Signal Discrimination:** Scores span 0.1-0.95 (not clustered)
2. **Activist Boost:** Companies with active 13D/8-K get 0.6+ score bump
3. **Margin Trends:** Declining margins = +0.2-0.3 carve-out signal
4. **Peer Precedent:** Similar divestitures = +0.2 validation signal
5. **Multi-gate Filtering:** <20% of high-score companies actually flagged (quality filter)
6. **Deal Estimates:** All flagged situations include estimated deal value

---

## Summary: All Tiers Complete

| Tier | Focus | Key Innovation |
|------|-------|-----------------|
| **1** | API data pipeline | Real XBRL/market/filing data fetching |
| **2** | Signal sophistication | Multi-dimensional metrics (PE, leverage, margins) |
| **3** | CS2 discrimination | Activist pressure, peer precedent, gating |
| **4** | Deal context | Leadership changes, transaction timing, valuations |

**Final Result:** Production-grade M&A and carve-out opportunity detection using real data, deterministic rules, and multi-threshold validation. Zero LLM during scan; on-demand explanations only.
