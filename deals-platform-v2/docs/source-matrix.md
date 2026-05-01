# Source matrix

Every data source the platform uses, with licence, rate-limit and mock
status. Mocked sources ship with fixture data so the PoC runs offline.

| Id | Source | URL | Used by | Licence / terms | Rate limit | Mock status |
|----|--------|-----|---------|----------------|------------|-------------|
| edgar.submissions | SEC EDGAR submissions index | https://data.sec.gov/submissions/CIK{cik}.json | CS1, CS2, CS4 | Public domain, SEC fair-use; UA required | 10 req/s | Live + fixture fallback |
| edgar.filing | SEC EDGAR filings archive | https://www.sec.gov/Archives/edgar/data/{cik}/... | CS1, CS2 | Public domain | 10 req/s | Live + fixture fallback |
| edgar.xbrl_companyfacts | SEC XBRL Company Facts | https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json | CS2, CS4 | Public domain | 10 req/s | Live + fixture fallback |
| news.google_rss | Google News RSS | https://news.google.com/rss/search?q={query} | CS1, CS2, CS3 | Public RSS; Google TOS; no scraping behind consent wall | ~1 req/2s | Live + fixture fallback |
| news.gdelt | GDELT 2.0 DOC API | https://api.gdeltproject.org/api/v2/doc/doc | CS1, CS2 | Free, attribution | ~1 req/s | Stub (fixture only in v1) |
| market.yfinance | Yahoo Finance (yfinance) | https://pypi.org/project/yfinance/ | CS1, CS2, CS3 | Unofficial, personal use; Yahoo TOS | best-effort | Live + fixture fallback |
| market.stooq | Stooq EOD CSVs | https://stooq.com/q/d/ | CS1 backup | Free, attribution | 1 req/s | Stub |
| macro.fred | FRED (St. Louis Fed) | https://fred.stlouisfed.org/docs/api/fred/ | CS1, CS3, CS4 | Free, API key | 120 req/min | Live + fixture fallback |
| reg.companies_house | UK Companies House | https://developer.company-information.service.gov.uk/ | CS1, CS2 | Free, API key, attribution | 600 req/5min | Live + fixture fallback |
| lei.gleif | GLEIF LEI | https://www.gleif.org/en/lei-data/gleif-api | CS1, CS2 | Free, CC0 | modest | Stub (backlog) |
| corp.opencorporates | OpenCorporates free tier | https://api.opencorporates.com/ | CS1, CS2 | Free tier with attribution | 50 req/day free | Stub (backlog) |
| macro.worldbank | World Bank Indicators | https://api.worldbank.org/v2/ | CS1 sector lens | Free, CC-BY | generous | Stub (backlog) |
| upload.file | Local FileUpload | n/a | CS3, CS4 | Client-controlled; never shared with CS1/CS2 modules | n/a | Live |

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

Each `Source` row persists `mode ∈ {live, fixture, blocked}`. The
`/sources` page lists them with last-refresh timestamp and a coloured dot.
Every Evidence record also carries `mode`; the evidence side panel labels
fixture-sourced evidence as `MOCK` in a pill.
