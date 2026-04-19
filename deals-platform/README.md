# Deals Platform — PoC

One product, four AI-enabled modules for professional-services M&A work. Each
surfaces a ranked list of **evidence-linked** situations with a human-in-the-loop
review workflow.

| Module | Route            | Data scope                        | Horizon  | Threshold |
|--------|------------------|-----------------------------------|----------|-----------|
| CS1    | `/origination`   | Public only                       | 12–24m   | >$1bn eq  |
| CS2    | `/carve-outs`    | Public only                       | 6–18m    | >$750m eq |
| CS3    | `/post-deal`     | Uploaded (+ public context)       | 0–24m    | n/a       |
| CS4    | `/working-capital` | Uploaded (+ XBRL peer benchmark) | 3–9m     | n/a       |

## Quickstart

```bash
cp .env.example .env   # optional: add live API keys
make demo              # build + seed fixtures + run all four pipelines
# then open http://localhost:3000
```

`make demo` will:

1. Start Postgres, the FastAPI backend, and the Next.js frontend via
   `docker compose`.
2. Seed public-scope fixtures (companies, segments, news, 10-Q/13D stubs,
   XBRL segment stubs, market snapshots, peer benchmarks).
3. Generate deterministic synthetic AR/AP/inventory ledgers and a post-deal
   case with actuals (CS3/CS4).
4. Run all four module pipelines in-process and print a summary.

The UI exposes the ranked pipeline, a sector heatmap (CS1/CS2), KPI band
charts (CS3), DSO/DPO/DIO cards (CS4), a review queue, sources health,
scoring-weights editor, and an evaluation dashboard.

## Design principles

- **Evidence root-of-trust.** Every Score, Signal, and Recommendation cites
  at least one Evidence row. `explain.unsupported_claims` enforces this
  before any output can be approved.
- **Data segregation.** CS1/CS2 code is import-isolated from CS3/CS4; the
  segregation test walks the AST and fails CI on cross-imports. At row level,
  `Evidence.scope` is `public` or `client` and public modules refuse to
  surface client-scope evidence.
- **No fabricated sources.** Every adapter maps to a real named service
  (EDGAR, Google News RSS, Yahoo/yfinance, FRED, Companies House). Unavailable
  sources return a fixture and the row is flagged `fixture` in the UI.
- **Human-in-the-loop.** Situations cannot move to `approved` without a
  reviewer, reason, and at least one evidence row.
- **Offline by default.** The LLM client returns deterministic fixtures when
  `ANTHROPIC_API_KEY` is unset. Tests run fully offline.

## Module-by-module

- **CS1 — Origination** scores public-company targets above a $1bn market-cap
  floor on a 12–24 month horizon, combining activist 13D filings, refi
  windows, adjacent deal flow, management changes, strategic-review language,
  and scale/sector context.
- **CS2 — Carve-Outs** scores segment-level divestiture readiness for groups
  above $750m equity on a 6–18 month horizon: segment margin drift, covenant
  headroom, activist break-up theses, peer divestments, rating watch, and
  whether the segment is reported separately at all.
- **CS3 — Post-Deal** ingests uploaded deal cases (JSON: initiatives with
  linear / S-curve / J-curve target bands and ±tolerance), plus uploaded
  actuals. Deviations are flagged after two consecutive out-of-band
  observations and scored by value-at-risk / urgency / impact.
- **CS4 — Working Capital** takes uploaded AR, AP, and inventory plus annual
  revenue and COGS, computes DSO / DPO / DIO with aging and concentration,
  benchmarks against XBRL peers (or fallback p40 / p50 / p60 benchmarks), and
  returns cash-opportunity low / mid / high bands.

## Repo layout

See [`CLAUDE.md`](CLAUDE.md) for conventions and
[`docs/implementation-plan.md`](docs/implementation-plan.md) for the phased
build plan. ADRs live under [`docs/adr/`](docs/adr/).

## Commands

```bash
make dev         # docker compose up --build
make demo        # seed + run all pipelines
make test        # backend pytest
make backtest    # CS1/CS2 backtest over fixtures/historical_deals.json
make lint        # ruff + eslint
make reset-db    # stop stack and drop postgres volume
```

## Non-goals

SSO, production security hardening, multi-tenancy, mobile UI, outbound
automation, paywall scraping, real client data. See
[`docs/limitations.md`](docs/limitations.md) for the backlog.
