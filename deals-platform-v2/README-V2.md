# Deals Platform v2 — Continuous Market Scanner

**Status:** MVP implementation complete with core features operational.

## What's New in v2?

v2 adds **continuous market scanning** with **deterministic signal scoring** and **module-specific prioritization**. Unlike v1 (on-demand analyzer), v2:

- ✅ Runs independently on **ports 8001/3001** (v1 stays on 8000/3000)
- ✅ Scans ~600 companies (S&P 500 + FTSE 100) **automatically at 02:00 UTC daily**
- ✅ Detects **new situations** via rules-based signals (zero LLM during scan)
- ✅ **Defers LLM explanations** until user opens a situation (~$0.02 per explanation vs. ~$0.40 upfront)
- ✅ **Case study-aligned prioritization:**
  - **CS1 (M&A Origination):** P1 Hot (activist catalyst), P2 Target (market stress), P3 Monitor
  - **CS2 (Carve-outs):** P1 Ready (separation-feasible), P2 Candidate (stressed), P3 Monitor
  - **CS3 (Post-Deal):** P1 At-Risk (synergy gap >25%), P2 On-Track, P3 Green
  - **CS4 (Working Capital):** P1 Quick Win (cash >$50M), P2 Solid, P3 Monitor
- ✅ **Tier colour coding:** Red (P1), Amber (P2), Green (P3)
- ✅ **Geography toggle:** UK-only or Worldwide (for CS1/CS2)
- ✅ **Tracks situation lifecycle:** `first_seen_at`, `score_delta`, `signals`

---

## Running v1 + v2 Side-by-Side

```bash
# Terminal 1: v1 on ports 8000/3000
cd deals-platform
docker compose up

# Terminal 2: v2 on ports 8001/3001
cd deals-platform-v2
docker compose up

# Open in browser:
# v1: http://localhost:3000
# v2: http://localhost:3001/scanner
```

---

## Continuous Scanning

### Automatic Daily Scan (APScheduler)

```python
# Runs at 02:00 UTC every day
# Scans both Worldwide + UK-only
# Updates existing situations, creates new ones
```

### Manual Trigger

```bash
# REST endpoint
curl -X POST "http://localhost:8001/api/v2/scan/run?api_mode=live&geography=worldwide"

# Response
{
  "status": "success",
  "timestamp": "2026-04-21T16:15:42Z",
  "geography": "worldwide",
  "counts": {
    "cs1_origination": 12,
    "cs2_carve_outs": 8,
    "cs3_post_deal": 0,
    "cs4_working_capital": 0
  },
  "total": 20
}
```

### API Mode: Live vs Offline

- **Live:** Real APIs (Fees ~$0.01 per company)
- **Offline:** Cached/seeded data (Zero cost)

Set via environment or UI toggle:

```bash
# API mode toggle in UI: http://localhost:3001/scanner
# Or via query param: ?api_mode=offline
```

---

## Deterministic Signals (No LLM During Scan)

### CS1 — M&A Origination (Equity Value > $1B)

**Signals:**
- Stock underperformance vs peers (>15% delta)
- PE multiple discount (>20% gap)
- Strategic margin compression
- Leadership changes (CEO/CFO <6m)
- Activist 13D filings
- Leverage stress (Net Debt / EBITDA > 3.5x)

**Catalyst Check (P1 Hot requires one of):**
- Active 13D filing (<6m old)
- Fresh CEO/CFO from activist/M&A background
- Activist board director appointment
- Debt maturity <18m + covenant tightness
- Announced strategic review (<6m)
- PE interest signals

### CS2 — Carve-out Detection (Equity Value > $750M)

**Signals:**
- Net debt escalation (3y trend)
- Segment underperformance vs peers
- Conglomerate discount (SoTP gap)
- Separation feasibility (systems independence, contract assignability)
- Capital actions (dividend suspend, equity issuance, asset sale)

---

## Frontend Dashboard

### URL

```
http://localhost:3001/scanner
```

### Features

1. **Scanner Panel:**
   - Manual "Refresh Now" button
   - API mode toggle (Live/Offline)
   - Geography toggle (Worldwide/UK-only)
   - Last scan timestamp
   - Result summary (counts by module)

2. **Filters & Sorting:**
   - Filter by Module (All / CS1 / CS2 / CS3 / CS4)
   - Filter by Tier (All / P1 / P2 / P3)
   - Sort by (Priority / Score / Recency)

3. **Situation Cards:**
   - Tier badge with colour (Red/Amber/Green)
   - Score (0–1)
   - Score delta (±0.XX)
   - Key signals (3 displayed)
   - Detection date

4. **Detail View:**
   - Full signal breakdown
   - "Generate Explanation" button (on-demand LLM)
   - Explanation preview
   - Caveats
   - Metadata (company, IDs)

---

## Architecture

### Backend Structure

```
deals-platform-v2/
  backend/
    app/
      scanner/
        api.py           # FastAPI routes (/api/v2/scan/*)
        service.py       # Core scanning logic
        signals.py       # Deterministic signal scorers
        jobs.py          # APScheduler jobs
      models/
        orm.py           # Situation + tier/geography fields
        enums.py         # Tier, Geography enums
      main.py            # Scheduler startup
```

### Database Schema (v2 Extensions)

```sql
ALTER TABLE situation ADD COLUMN tier VARCHAR;        -- p1_hot, p2_target, etc.
ALTER TABLE situation ADD COLUMN tier_colour VARCHAR; -- red, amber, green
ALTER TABLE situation ADD COLUMN signals JSONB;       -- Deterministic signals
ALTER TABLE situation ADD COLUMN score_delta FLOAT;   -- Change vs previous scan
ALTER TABLE situation ADD COLUMN first_seen_at TIMESTAMP;
ALTER TABLE situation ADD COLUMN last_updated_at TIMESTAMP;

ALTER TABLE company ADD COLUMN net_debt_usd FLOAT;    -- For leverage calculations
ALTER TABLE company ADD COLUMN current_pe_ratio FLOAT;
```

### API Endpoints

```
POST   /api/v2/scan/run
       ?api_mode=live|offline
       ?geography=worldwide|uk_only
       → { status, timestamp, counts, total }

GET    /api/v2/scan/situations
       ?module=origination|carve_outs|...
       ?tier=p1_hot|p2_target|...
       ?sort_by=priority|score|recency
       ?limit=50 &offset=0
       → { total, limit, offset, situations[] }

GET    /api/v2/scan/situations/{id}
       → SituationV2 { id, module, tier, tier_colour, score, score_delta, signals, ... }

POST   /api/v2/scan/situations/{id}/explain
       → { id, explanation, cached }
```

---

## Cost Model

### Scanning Phase
- **Per company analyzed:** $0.00 (deterministic signals only)
- **Daily scan (600 companies):** ~$0.00 (in offline mode) or ~$3-5 (live APIs if enabled)

### On-Demand Explanation
- **Per explanation generated:** ~$0.01–0.02 (Claude Haiku classification)
- **1 analyst reviewing 20 situations:** ~$0.20–0.40

### Scheduler
- **Runs daily:** No additional cost (scheduled job, offline mode by default)

---

## Configuration

### Environment Variables

```bash
# Enable/disable APScheduler
ENABLE_SCHEDULER=True

# API mode (live or offline)
OFFLINE_MODE=True

# Scoring thresholds (configured in code)
EQUITY_VALUE_CS1_MIN=1_000_000_000
EQUITY_VALUE_CS2_MIN=750_000_000
```

### Settings (env or UI)

- `api_mode`: "live" or "offline"
- `geography`: "worldwide" or "uk_only" (CS1/CS2 only)
- `enable_scheduler`: True/False

---

## Comparing v1 vs v2

| Aspect | v1 | v2 |
|--------|----|----|
| **Ports** | 8000/3000 | 8001/3001 |
| **Scanning** | On-demand (manual) | Scheduled (daily 02:00 UTC) |
| **Universe** | 5 hard-coded | ~600 (S&P 500 + FTSE 100) |
| **Signals** | LLM-based (in-scan) | Deterministic (rules) |
| **Explanations** | Pre-computed | On-demand (deferred) |
| **Prioritization** | Generic scoring | Module-specific (CS1-4) |
| **Tiers** | None | P1/P2/P3 with colours |
| **Geography** | N/A | Worldwide / UK-only |
| **Lifecycle Tracking** | None | first_seen_at, score_delta |
| **Cost** | ~$0.40 upfront | ~$0.02 per explanation |

---

## Testing & Validation

### Offline Mode Demo

```bash
# Uses seeded data, zero API calls, zero cost
curl -X POST "http://localhost:8001/api/v2/scan/run?api_mode=offline&geography=worldwide"
```

### Live Mode (requires API keys)

```bash
export ANTHROPIC_API_KEY=sk-...
export FRED_API_KEY=...
export COMPANIES_HOUSE_API_KEY=...

curl -X POST "http://localhost:8001/api/v2/scan/run?api_mode=live&geography=uk_only"
```

### Frontend Testing

1. Visit http://localhost:3001/scanner
2. Toggle "Offline (Cached)" mode
3. Click "Refresh Now"
4. Select a situation
5. Click "Generate" to trigger on-demand explanation

---

## Known Limitations (Backlog)

- [ ] CS3/CS4 scanning deferred (currently upload-driven)
- [ ] Signal weights not yet calibrated to live deal data
- [ ] Explanation caching not implemented (each generation is a new API call)
- [ ] Batch processing not optimized for >1000 companies
- [ ] No alert/notification system yet

---

## Next Steps

1. **Calibration:** Backtest CS1/CS2 signals against historical deals (~200 examples)
2. **Live Testing:** Run v2 for 1 month, collect coverage metrics
3. **CS3/CS4:** Extend scanning to uploaded data sources
4. **Alerts:** Email/webhook notifications for P1 situations
5. **Export:** CSV/PDF reports for analyst reviews

---

## Questions?

See `/deals-platform-v2/docs/` for:
- `architecture.md` — System design
- `assumptions.md` — Design choices
- `limitations.md` — Known gaps
