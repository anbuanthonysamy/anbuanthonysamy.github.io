# Limitations and backlog

## Non-goals (intentionally out of scope for v1)

- Enterprise SSO / production auth (header-stub only)
- Production security hardening, rate limiting, WAF, secrets rotation
- Multi-tenant isolation
- Mobile UI
- Live trading or investment-advice framing
- Any scraping behind paywalls or consent walls
- Use of real client data
- Generic competitor research
- Autonomous outbound workflows (no emails/Slack sent by default)

## Known limitations

- **Segment extraction coverage**: CS2 relies on XBRL segment data. Where
  an issuer doesn't publish it, the module drops to whole-company signals
  and sets `confidence ≤ 0.4`.
- **yfinance**: unofficial library; rate-limits unpredictable. Production
  replacement (Polygon, Refinitiv, FMP paid) is a backlog item.
- **GDELT, OpenCorporates, GLEIF, World Bank** are stubs in v1 with
  fixture fallback.
- **Currency**: daily FRED FX; intra-day exposures not tracked.
- **LLM offline mode**: without `ANTHROPIC_API_KEY`, extraction and
  synthesis use deterministic fixtures. Explanations in offline mode are
  templated rather than generated.
- **No automatic scheduled recalibration** in v1 — gated behind a labelled
  set size and a manual toggle.

## Backlog

- EU issuer coverage (ESMA filings)
- GICS / sub-industry taxonomy (requires licence)
- Integrate LEI via GLEIF and corporate-family graph via OpenCorporates
- Migrate persistence from `create_all` to Alembic migrations
- Replace header-stub auth with OAuth2/OIDC
- Move synthesis explanations to streaming for snappier UI
- Add PDF export worker (WeasyPrint pool)
- Replace `pgvector` stub with actual embedding-based evidence search if
  volume warrants it
