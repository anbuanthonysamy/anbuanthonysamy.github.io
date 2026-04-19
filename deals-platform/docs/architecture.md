# Architecture

One-page view of the platform. Four modules, one spine.

## Diagram

```mermaid
flowchart LR
  subgraph Sources
    E[EDGAR] --- N[Google News RSS]
    N --- M[yfinance / FRED]
    M --- U[FileUpload]
  end

  subgraph Spine
    ING[Ingestor] --> EVT[Evidence Store]
    EVT --> SIG[Signal Engine]
    SIG --> SCO[Scorer]
    SCO --> EXP[Explainer]
    EXP --> HAL[Hallucination Detector]
    HAL --> CRT[Critic]
    CRT --> Q[Review Queue]
  end

  subgraph Modules
    CS1[CS1 Origination]
    CS2[CS2 Carve-outs]
    CS3[CS3 Post-deal]
    CS4[CS4 Working capital]
  end

  subgraph UI["Next.js UI"]
    R1["/origination"]
    R2["/carve-outs"]
    R3["/post-deal"]
    R4["/working-capital"]
    RS["/sources /settings /eval /review-queue"]
  end

  Sources --> ING
  CRT --> CS1
  CRT --> CS2
  CRT --> CS3
  CRT --> CS4
  CS1 --> R1
  CS2 --> R2
  CS3 --> R3
  CS4 --> R4
  Q --> RS
```

## Layers

1. **Sources** — pluggable `Source` adapters behind a uniform interface.
   Each adapter yields `Evidence` records.
2. **Spine** — orchestrates ingest → evidence → signals → score → explain
   → critic. All stateful operations persist to Postgres.
3. **Modules** — thin per-case configuration on top of the spine:
   module-specific signals, weights, output shape and UI views.
4. **UI** — single Next.js app with module routes plus four shared
   utility routes.

## Data flow invariants

- No claim is surfaced to UI without at least one `Evidence` referenced
  by its `explanation.evidence_ids`. Enforced by
  `backend/app/explain/unsupported_claims.py` on every response.
- Every explanation is measured for hallucination post-generation: sentence
  coverage against evidence (cosine similarity + fact matching), unsupported
  claim count logged in `LLMCall.hallucination_score` and
  `LLMCall.evidence_coverage_pct`. Surfaced via `/eval/llm` dashboard.
- CS1 and CS2 pipelines execute only against `public_*` sources. The
  segregation test (`backend/tests/test_segregation.py`) walks imports
  and fails CI on a cross-boundary import.
- The `Critic` re-runs the score+explain chain up to 2 times if its
  rubric score is below `CRITIC_PASS_THRESHOLD` (default 0.7). Output
  after max retries is still surfaced but flagged `needs_review`.

## Resilience

- Jobs are idempotent by `(source_id, external_id)` upsert key.
- Scheduler state lives in Postgres (APScheduler Postgres job store), so
  weekly restarts resume cleanly.
- The LLM client retries with exponential backoff on 429/5xx and falls
  back to deterministic fixture output when offline.

## Boundary diagram

```
public-data modules  ──▶ sources/public/*      ──▶ Evidence (scope=public)
uploaded-data modules ──▶ sources/upload/*     ──▶ Evidence (scope=client)
                          sources/public/*     ──▶ Evidence (scope=public)  (benchmarks only)
```

The `Evidence.scope` column is checked at read time: a request in a
public-only module cannot read `scope=client` rows.
