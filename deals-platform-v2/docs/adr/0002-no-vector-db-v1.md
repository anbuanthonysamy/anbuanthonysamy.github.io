# ADR-0002: No vector DB in v1

## Context

The wrapper prompt warns against introducing vector DBs, RAG pipelines,
MCP servers or multi-agent frameworks unless the delivered code clearly
benefits and the choice is justified in an ADR.

## Decision

No vector DB or RAG pipeline in v1. Evidence is stored as rows in
Postgres with text fields and retrieved by deterministic queries
(company_id, signal_id, time window). LLM calls operate on
already-filtered evidence lists rather than on embedding search.

The pgvector extension is enabled in the Postgres image so we can
introduce embedding search later without a migration blocker, but no
code uses it in v1.

## Consequences

+ Simpler stack, deterministic retrieval, fewer failure modes.
+ No embedding infrastructure to operate.
- If the evidence table grows beyond ~1M rows, keyword filters alone will
  be slow; that is a scale problem, not a PoC problem.
