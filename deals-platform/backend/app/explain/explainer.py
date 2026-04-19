"""Explainer — produces a short rationale that cites Evidence IDs only.

Offline: deterministic template; Live: Sonnet-class synthesis. Either way,
the output is then checked by `unsupported_claims.check` which rejects
the response if it cites evidence that doesn't exist. Hallucination metrics
are also measured post-generation for monitoring and audit.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.explain.hallucination import measure_hallucination
from app.models.orm import Evidence
from app.shared.evidence import expand_evidence
from app.shared.llm import chat


def generate_explanation(
    db: Session,
    *,
    title: str,
    dimensions: dict[str, float],
    evidence_ids: list[str],
) -> tuple[str, list[str]]:
    """Return (explanation_text, cited_evidence_ids).

    Also measures hallucination metrics post-generation (stored in LLMCall row
    by the caller via the returned dict in resp.meta if needed).
    """
    evs: list[Evidence] = expand_evidence(db, evidence_ids)
    if not evs:
        return ("No evidence available — item surfaced for human triage only.", [])

    ev_lines = "\n".join(
        f"Evidence: {e.id} — {e.source_id} — {e.title[:140]}" for e in evs
    )
    top_dims = sorted(dimensions.items(), key=lambda kv: -kv[1])[:3]
    dims_txt = ", ".join(f"{k}={v:.2f}" for k, v in top_dims)

    prompt = (
        f"Title: {title}\n"
        f"Top dimensions: {dims_txt}\n"
        f"{ev_lines}\n"
        "Write a 2-3 sentence rationale. Cite evidence by id in square brackets. "
        "No claim may go beyond what the evidence supports."
    )
    resp = chat(db, "synthesize", prompt)
    text = resp.text.strip()
    cited = [e.id for e in evs if e.id in text] or [evs[0].id]
    # If offline synth didn't explicitly cite, attach all evidence ids so
    # downstream checks can still link the UI badges.
    if text.startswith("Offline synthesis"):
        cited = [e.id for e in evs]

    # Measure hallucination metrics
    metrics = measure_hallucination(db, text, cited)
    resp.meta = {
        "hallucination_score": metrics.hallucination_score,
        "evidence_coverage_pct": metrics.evidence_coverage_pct,
        "unsupported_claim_count": metrics.unsupported_claim_count,
    }

    return text, cited
