# Assumptions (living log)

Every assumption made while building the PoC. Update in-session; never
silently pick a default.

## Scope

- **A1**. The PoC is built under `deals-platform/` in this repo so the
  existing personal site at the repo root is not disturbed.
- **A2**. Deployment target for the PoC is `docker compose up` on a
  developer laptop. No cloud deployment scripts in v1.
- **A3**. Auth is a header-based identity stub (`X-Reviewer` header carries
  the reviewer id). SSO is out of scope.

## Data

- **A4**. Public-data sources used by default: SEC EDGAR (filings + XBRL),
  Google News RSS, Yahoo Finance via yfinance, FRED (macro), Companies
  House (UK). GDELT, OpenCorporates, GLEIF marked as optional stubs in
  `docs/source-matrix.md`.
- **A5**. Where live APIs need credentials, the adapter falls back to a
  canned JSON fixture in `fixtures/` and the UI surfaces `source: mocked`.
- **A6**. Currency: all monetary values are normalised to USD at the
  retrieval FX rate (FRED daily). Mixed-currency inputs convert at upload.
- **A7**. Sector taxonomy: SIC code rolled up to 11 high-level sectors.
  This is sufficient for sector-lens heatmaps; GICS not used (licence).

## CS1 — Origination

- **A8**. "Large deal" threshold: equity value > $1bn as per brief. The
  horizon window (12–24m) is applied at scoring time, not at filtering.
- **A9**. Universe: US listed issuers with market-cap > $1bn (configurable
  in /settings). UK extension is a backlog item.
- **A10**. "Strategic relevance to the advisor" uses only public proxies:
  sector weight, deal-size band, geography. No proprietary account data.

## CS2 — Carve-outs

- **A11**. "Situation" is modelled as one row with `kind ∈ {company,
  segment, division, asset_cluster, strategic_review}`.
- **A12**. Segment-level financials come from XBRL segment disclosures.
  Where a company does not publish segment data, the module falls back to
  whole-company signals and flags low confidence.
- **A13**. Feasibility proxies: separability (`segment_reported`,
  `distinct_ceo_mentioned`), visibility (`filing_segment_disclosure_years`),
  non-core evidence (`strategic_review_language_hits`).

## CS3 — Post-deal

- **A14**. Deal-case upload is a JSON or XLSX with a fixed schema (see
  `backend/app/modules/post_deal/schemas.py`).
- **A15**. Trend-band curve choice: initiatives tagged `cost_out` default
  to S-curve; `revenue_synergy` defaults to J-curve; `integration_milestone`
  defaults to linear. Override in upload.
- **A16**. Tolerance band: ±10% of target by default, overridable per KPI.
- **A17**. Refresh cadence: daily. Manual refresh available in UI.

## CS4 — Working capital

- **A18**. Peer benchmark cohort: same 2-digit SIC and revenue band
  (0.5x–2x subject revenue), trailing-4-quarter median.
- **A19**. DSO = AR / (Revenue / days). DPO = AP / (COGS / days).
  DIO = Inventory / (COGS / days). Days = 365 unless trailing quarter
  chosen.
- **A20**. Cash opportunity = (subject_days − benchmark_p50_days) ×
  (daily driver) clamped at 0. Surfaced with a low/mid/high band using
  p60/p50/p40 of the peer cohort.

## Models / LLM

- **A21**. Offline mode is the default for CI. The LLM client returns
  deterministic fixtures. Setting `ANTHROPIC_API_KEY` switches to live.
- **A22**. Extraction/classification: `claude-haiku-4-5`. Synthesis and
  explanation: `claude-sonnet-4-6`.
- **A23**. No vector DB in v1 (see ADR-0002). If later needed, use pgvector
  inside the existing Postgres.

## Open questions carried as design choices

- **O1**. Cross-border deals: v1 scopes US + UK issuers. EU extension in
  backlog.
- **O2**. Newsflow dedup: using `sha256(title + source + date)` as the
  evidence key; collisions unlikely at PoC scale.
- **O3**. PDF briefing: generated via WeasyPrint from a templated HTML so
  the same template drives on-screen rendering.
