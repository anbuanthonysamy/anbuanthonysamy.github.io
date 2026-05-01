# Source matrix

Every data source the platform uses, with licence, rate-limit and mock
status. Mocked sources ship with fixture data so the PoC runs offline.

## Mode legend

- **LIVE** — adapter calls the real API and returns real data right now.
- **MOCK** (fixture) — adapter is implemented but the live call failed, was
  blocked, or no API key was provided. Fell back to local fixture data.
  Each evidence row carries a `fallback_reason` explaining *why*.
- **STUB** — adapter is documented but **not yet implemented**. Returns a
  placeholder marker so the UI can clearly say "this source isn't wired up".
- **BLOCKED** — robots.txt or terms forbid this fetch.

You can verify any source's current mode at runtime via the `/sources` page
(click **Verify** to run a live test) or by inspecting evidence pills on any
signal card.

| Id | Source | URL | Used by | Licence / terms | Rate limit | Adapter status |
|----|--------|-----|---------|----------------|------------|----------------|
| edgar.submissions | SEC EDGAR submissions index | https://data.sec.gov/submissions/CIK{cik}.json | CS1, CS2, CS4 | Public domain, SEC fair-use; UA required | 10 req/s | Implemented (live + fixture fallback) |
| edgar.filing | SEC EDGAR filings archive | https://www.sec.gov/Archives/edgar/data/{cik}/... | CS1, CS2 | Public domain | 10 req/s | Implemented (live + fixture fallback) |
| edgar.xbrl_companyfacts | SEC XBRL Company Facts | https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json | CS2, CS4 | Public domain | 10 req/s | Implemented (live + fixture fallback) |
| edgar.xbrl_segment_facts | SEC XBRL Segment Facts | https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json | CS2 | Public domain | 10 req/s | Implemented (live + fixture fallback) |
| news.google_rss | Google News RSS | https://news.google.com/rss/search?q={query} | CS1, CS2, CS3 | Public RSS; Google TOS; no scraping behind consent wall | ~1 req/2s | Implemented (often blocked by Google → fixture) |
| market.yfinance | Yahoo Finance (yfinance) | https://pypi.org/project/yfinance/ | CS1, CS2, CS3 | Unofficial, personal use; Yahoo TOS | best-effort | Implemented (live + fixture fallback) |
| macro.fred | FRED (St. Louis Fed) | https://fred.stlouisfed.org/docs/api/fred/ | CS1, CS3, CS4 | Free, API key | 120 req/min | Implemented (requires `FRED_API_KEY`) |
| reg.companies_house | UK Companies House | https://developer.company-information.service.gov.uk/ | CS1, CS2 | Free, API key, attribution | 600 req/5min | Implemented (requires `COMPANIES_HOUSE_API_KEY`) |
| upload.file | Local FileUpload | n/a | CS3, CS4 | Client-controlled; never shared with CS1/CS2 modules | n/a | Implemented (always live, user-controlled) |
| news.gdelt | GDELT 2.0 DOC API | https://api.gdeltproject.org/api/v2/doc/doc | CS1, CS2 | Free, attribution | ~1 req/s | **STUB — not yet implemented** |
| market.stooq | Stooq EOD CSVs | https://stooq.com/q/d/ | CS1 backup | Free, attribution | 1 req/s | **STUB — not yet implemented** |
| lei.gleif | GLEIF LEI | https://www.gleif.org/en/lei-data/gleif-api | CS1, CS2 | Free, CC0 | modest | **STUB — not yet implemented** |
| corp.opencorporates | OpenCorporates free tier | https://api.opencorporates.com/ | CS1, CS2 | Free tier with attribution | 50 req/day free | **STUB — not yet implemented** |
| macro.worldbank | World Bank Indicators | https://api.worldbank.org/v2/ | CS1 sector lens | Free, CC-BY | generous | **STUB — not yet implemented** |

## Licence notes

- SEC EDGAR: SEC requires a descriptive `User-Agent: CompanyName admin@example.com`.
  The adapter reads `SEC_USER_AGENT` from env.
- Yahoo Finance via `yfinance`: unofficial library; acceptable for research PoC
  but not suitable for production. Documented as a v1 compromise.
- Companies House: requires API key (`COMPANIES_HOUSE_API_KEY`). Without key,
  fixture fallback.
- Google News RSS: uses public RSS feed. The adapter respects robots.txt for
  follow-on article fetches and does not fetch article bodies behind consent
  walls. When blocked, it persists title + source + published date only.

## Robots.txt

`backend/app/sources/http.py` consults `robots.txt` with a small on-disk cache
before fetching any non-API URL. Disallowed paths produce a `RobotsBlocked`
evidence record with `ok: false` so the UI can surface the gap honestly.

## Mock-vs-live in the UI

Each `Source` row persists `mode ∈ {live, fixture, stub, blocked}` and a
`last_fallback_reason`. The `/sources` page lists every source split into two
groups: **Real adapters** (which attempt live calls) and **Stubs** (which
aren't implemented yet). Each row has:

- **Mode pill** with colour: green=LIVE, amber=MOCK (fixture), purple=STUB,
  red=BLOCKED.
- **Verify** button that runs a live test against the source and shows the
  raw response (without writing to the database). Use this to confirm a
  source is *actually* live rather than silently falling back.
- **Last fallback reason** column — surfaces *why* a source last fell back
  (e.g. "Live fetch failed: HTTPStatusError: Client error '403 Forbidden'",
  "FRED_API_KEY not configured", "adapter not yet implemented").

Every `Evidence` record also carries `mode` and `fallback_reason`; the
evidence panel on signal/score detail views shows:

- A coloured **mode pill** (LIVE / MOCK / STUB / BLOCKED) with hover tooltip.
- A **"Why MOCK"** banner when mode != live, citing the fallback reason.
- A prominent **🔗 Verify Source** button linking to the original URL.
- Expandable full snippet and JSON `meta` so the user can inspect the raw
  extracted data.

The module overview (`DataProvenance` panel) shows an aggregated
**"Data quality: 65% live"** indicator plus a horizontal bar
visualising the live/mock/stub/blocked breakdown across all evidence
backing the situations on that page.
