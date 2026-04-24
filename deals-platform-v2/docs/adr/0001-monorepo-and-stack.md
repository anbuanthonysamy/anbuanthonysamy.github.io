# ADR-0001: Monorepo with FastAPI + Next.js

## Context

The PoC needs one deployable product with four modules, shared spine,
Postgres persistence, and the ability to run locally with one command.

## Decision

Single repo, two services plus a database:
- `backend/` — Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, APScheduler.
- `frontend/` — Next.js 14 app router, Tailwind, TypeScript strict.
- Postgres 16 with pgvector extension available (used lazily; see ADR-0002).

`docker compose up` brings everything up. No Kubernetes, no terraform, no
multi-cloud deployment scripts — those are explicit non-goals.

## Consequences

+ Minimum moving parts, fastest path to a runnable demo.
+ Clear language boundary: data/ML in Python, UI in TS.
- Two toolchains to keep in sync; mitigated by a small `lib/` of shared
  TS types generated from Pydantic via `datamodel-code-generator` (backlog)
  or hand-kept in v1.
