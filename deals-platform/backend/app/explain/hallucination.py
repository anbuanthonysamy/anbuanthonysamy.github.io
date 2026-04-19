"""Hallucination detector — measures evidence coverage and unsupported claims.

Splits explanation into sentences, checks each against cited evidence using
cosine similarity, and scores coverage (0..1). Flags sentences with no backing
as unsupported claims.

Runs post-LLM-generation, before unsupported_claims.check validates citations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.orm import Evidence


@dataclass
class HallucinationMetrics:
    hallucination_score: float  # 0..1, higher = more hallucination
    evidence_coverage_pct: float  # 0..100, % of explanation backed by evidence
    unsupported_claim_count: int  # count of sentences with no evidence support


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences. Naive but good enough for metrics."""
    # Split on period, question mark, exclamation; keep sentence intact.
    # Handles abbreviations loosely (e.g. "U.S." may produce empty parts).
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in parts if s.strip()]


def _cosine_similarity(a: str, b: str) -> float:
    """Simple token overlap cosine similarity (bag-of-words)."""
    tokens_a = set(re.findall(r'\b\w+\b', a.lower()))
    tokens_b = set(re.findall(r'\b\w+\b', b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _extract_factual_phrases(text: str) -> list[str]:
    """Extract noun phrases, numbers, named entities (simple heuristic)."""
    # Phrases with capitals, numbers, domain terms. Not a real NER, just heuristic.
    phrases = re.findall(r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|\$?\d+(?:M|B|T)?)', text)
    return [p for p in phrases if p]


def measure_hallucination(
    db: Session,
    explanation: str,
    evidence_ids: list[str],
    similarity_threshold: float = 0.3,
) -> HallucinationMetrics:
    """Measure hallucination in an explanation against cited evidence.

    Args:
        db: Database session
        explanation: Generated explanation text
        evidence_ids: IDs of evidence pieces that back this explanation
        similarity_threshold: Cosine similarity score (0..1) above which a sentence
                            is considered "backed" by evidence.

    Returns:
        HallucinationMetrics with hallucination_score, coverage %, unsupported count.
    """
    if not explanation or not evidence_ids:
        return HallucinationMetrics(
            hallucination_score=1.0 if explanation else 0.0,
            evidence_coverage_pct=0.0,
            unsupported_claim_count=len(_split_sentences(explanation)),
        )

    # Fetch evidence snippets
    evs: list[Evidence] = db.query(Evidence).filter(Evidence.id.in_(evidence_ids)).all()
    if not evs:
        return HallucinationMetrics(
            hallucination_score=1.0,
            evidence_coverage_pct=0.0,
            unsupported_claim_count=len(_split_sentences(explanation)),
        )

    # Combine evidence into one text block for similarity checks
    evidence_text = " ".join(
        [e.snippet or e.title for e in evs if e.snippet or e.title]
    )

    sentences = _split_sentences(explanation)
    if not sentences:
        return HallucinationMetrics(0.0, 100.0, 0)

    # Check each sentence against evidence
    unsupported = 0
    covered_sentences = 0

    for sent in sentences:
        # Similarity check: does the sentence overlap with evidence?
        sim = _cosine_similarity(sent, evidence_text)

        # Fact check: do the factual phrases in the sentence appear in evidence?
        facts = _extract_factual_phrases(sent)
        facts_backed = 0
        if facts:
            for fact in facts:
                if any(fact in ev.snippet or fact in ev.title for ev in evs if ev.snippet or ev.title):
                    facts_backed += 1
            fact_coverage = facts_backed / len(facts)
        else:
            fact_coverage = 1.0  # No factual claims, so no hallucination

        # A sentence is "supported" if it has high similarity OR most facts are in evidence
        is_supported = sim >= similarity_threshold or fact_coverage >= 0.5
        if is_supported:
            covered_sentences += 1
        else:
            unsupported += 1

    coverage_pct = (covered_sentences / len(sentences)) * 100 if sentences else 0.0
    hallucination_score = (unsupported / len(sentences)) if sentences else 0.0

    return HallucinationMetrics(
        hallucination_score=hallucination_score,
        evidence_coverage_pct=coverage_pct,
        unsupported_claim_count=unsupported,
    )
