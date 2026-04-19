# ADR-0004: LLM offline/deterministic by default

## Context

The PoC must run end-to-end without credentials. CI should not call a
paid API. But the product should use a real LLM where that adds value
(extraction from unstructured text, synthesis, explanation).

## Decision

`backend/app/shared/llm.py` exposes a single `chat()` function with two
roles: `"extract"` (Haiku-class) and `"synthesize"` (Sonnet-class). When
`ANTHROPIC_API_KEY` is unset, the client returns deterministic fixtures
keyed by `(role, prompt_hash)`. When set, it calls the real API.

Token and cost are logged to the `llm_call` table in both modes (cost
= 0 in offline mode).

## Consequences

+ CI is deterministic and free.
+ Developers can demo offline.
+ Live mode requires just one env var.
- Offline explanations are templated, not generated; the UI surfaces the
  mode clearly on every output.
