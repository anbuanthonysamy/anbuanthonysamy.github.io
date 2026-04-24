# ADR-0003: create_all instead of Alembic migrations in v1

## Context

The PoC needs persistence but not schema evolution across environments.
A developer-laptop target and daily full rebuilds mean migrations would
be friction without benefit.

## Decision

Use `Base.metadata.create_all(engine)` on startup. Ship a `reset-db`
Make target that drops and recreates everything. Alembic is a documented
backlog item for production.

## Consequences

+ One less tool to learn and maintain in v1.
+ Fast iteration on the schema.
- Schema changes require a DB reset; acceptable for a PoC.
- Production would need Alembic (tracked in `docs/limitations.md`).
