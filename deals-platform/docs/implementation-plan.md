# Implementation plan

One-page plan for the four-module Deals Platform PoC. Phases match the
wrapper prompt. Each phase lists deliverables, then their status.

## Phase 0 — Plan
- CLAUDE.md, assumptions, source matrix, scoring framework, limitations
- Architecture diagram (Mermaid in `architecture.md`)
- Canonical Pydantic data model

## Phase 1 — Spine
- Monorepo skeleton under `deals-platform/`
- `docker-compose.yml` (postgres, backend, frontend)
- FastAPI backend with health, settings, sources, review-queue
- Next.js + Tailwind frontend shell with four module routes
- Postgres persistence via SQLAlchemy (no separate Alembic migrations in v1;
  `Base.metadata.create_all` on startup — see ADR-0003)
- Source interface + adapters: EDGAR, Google News RSS, yfinance, FRED,
  Companies House, FileUpload
- Auth stub (header-based identity; SSO intentionally out of scope)
- CI: ruff + pytest + eslint + typecheck; segregation test

## Phase 2 — Shared platform
- Ingestion scheduler (APScheduler, daily + manual refresh)
- Evidence store with retrieved_at, parsed_at, sha256
- Signal definitions in YAML with code handlers
- Scoring engine with configurable weights (editable in /settings)
- Explanation generator with unsupported-claims check (rejects outputs
  referencing an evidence_id that does not exist in the store)
- Review queue with accept/reject/edit/approve and persisted reviewer
- Source health page

## Phase 3 — Modules
- CS1 Origination: universe builder, M&A-likelihood signals, ranked pipeline,
  sector heatmap, per-company briefing PDF
- CS2 Carve-outs: segment-level XBRL extraction, carve-out likelihood signals,
  readiness heatmap, break-up logic tree, value-at-stake bands
- CS3 Post-deal: deal-case upload, trend-band generation (linear/S/J-curve),
  deviation detection, root-cause, intervention priority
- CS4 Working capital: AR/AP/inventory upload, DSO/DPO/DIO, peer benchmark
  from EDGAR, cash-opportunity quantification, diagnostic drill-down

## Phase 4 — Test & demo
- `scripts/seed_synth.py` generates realistic AR/AP/inventory and KPI streams
- `fixtures/historical_deals.json` with ~20 known past deals
- `scripts/backtest.py` produces precision/recall at top-N for CS1 and CS2
- Pytest regression suite with golden-set scoring tolerance

## Phase 5 — Verify & summarise
- Full test run
- `make demo` end-to-end walk of each module
- docs updated; mocked-vs-live clearly labelled

## Status

Phase 0: in progress.
Phase 1 onwards: pending — see git history for incremental commits.
