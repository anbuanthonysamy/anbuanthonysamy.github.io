"""Per-module orchestrator: Ingest -> Extract -> Score -> Explain -> Critic.

Each module constructs a Pipeline with a list of SignalDef + weights;
then calls `.run()` against a company to produce a Situation.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.explain.explainer import generate_explanation
from app.explain.unsupported_claims import check_situation
from app.models.enums import ReviewState
from app.models.orm import Company, Evidence, Signal, Situation
from app.orchestrators.critic import CriticReport, rubric_score
from app.scoring.engine import ScoreBundle, compose, load_weights
from app.signals.registry import SignalDef, resolve_handler


@dataclass
class PipelineRun:
    situation: Situation
    critic: CriticReport
    attempts: int
    signal_ids: list[str] = field(default_factory=list)


class ModulePipeline:
    def __init__(
        self,
        db: Session,
        module: str,
        signals: list[SignalDef],
        max_retries: int = 2,
    ) -> None:
        self.db = db
        self.module = module
        self.signals = signals
        self.max_retries = max_retries

    def _collect_evidence(self, company: Company) -> list[Evidence]:
        return list(
            self.db.scalars(
                select(Evidence).where(Evidence.company_id == company.id)
            ).all()
        )

    def _aggregate_dimensions(
        self,
        signal_results: list[tuple[SignalDef, "SignalResult"]],
    ) -> tuple[dict[str, float], float, list[str], list[str]]:
        dims: dict[str, list[float]] = {}
        confidences: list[float] = []
        sig_ids: list[str] = []
        ev_ids: list[str] = []
        for d, r in signal_results:
            dims.setdefault(d.feeds_dimension, []).append(r.strength)
            if r.strength > 0:
                confidences.append(r.confidence)
            ev_ids.extend(r.evidence_ids)

        for d, r in signal_results:
            if r.strength <= 0:
                continue
            sig = Signal(
                module=self.module,
                signal_key=d.key,
                company_id=None,
                strength=r.strength,
                confidence=r.confidence,
                evidence_ids=r.evidence_ids,
                detail=r.detail,
            )
            self.db.add(sig)
            self.db.flush()
            sig_ids.append(sig.id)

        agg = {k: round(sum(v) / len(v), 3) for k, v in dims.items() if v}
        # ensure confidence dimension baseline
        agg.setdefault("confidence", round(sum(confidences) / len(confidences), 3) if confidences else 0.0)
        overall_conf = agg.get("confidence", 0.0)
        return agg, overall_conf, sig_ids, list(dict.fromkeys(ev_ids))

    def run_for_company(
        self,
        company: Company,
        extras: dict | None = None,
        title: str | None = None,
        next_action: str | None = None,
    ) -> PipelineRun:
        evs = self._collect_evidence(company)
        results = []
        for d in self.signals:
            handler = resolve_handler(d.handler)
            r = handler(company, evs)
            results.append((d, r))

        dims, conf, sig_ids, ev_ids = self._aggregate_dimensions(results)
        weights = load_weights(self.db, self.module)
        bundle = compose(dims, weights, conf)

        explanation, cites = generate_explanation(
            self.db,
            title=title or f"{self.module} — {company.name}",
            dimensions=dims,
            evidence_ids=ev_ids,
        )

        situation = Situation(
            module=self.module,
            kind="company",
            company_id=company.id,
            title=title or f"{self.module.replace('_', ' ').title()}: {company.name}",
            summary=None,
            next_action=next_action or _default_next_action(self.module),
            caveats=_caveats(bundle, evs),
            dimensions=bundle.dimensions,
            weights=bundle.weights,
            confidence=bundle.confidence,
            score=bundle.score,
            signal_ids=sig_ids,
            evidence_ids=ev_ids,
            explanation=explanation,
            explanation_cites=cites,
            extras=extras or {},
            review_state=ReviewState.PENDING.value,
        )

        # Critic loop: re-explain on failure. Signal strengths are deterministic.
        self.db.add(situation)
        self.db.flush()
        attempts = 1
        critic = rubric_score(_as_dict(situation))
        while not critic.passes and attempts <= self.max_retries:
            # Retry: re-generate explanation with more evidence context.
            explanation, cites = generate_explanation(
                self.db,
                title=situation.title,
                dimensions=situation.dimensions,
                evidence_ids=situation.evidence_ids,
            )
            situation.explanation = explanation
            situation.explanation_cites = cites
            attempts += 1
            critic = rubric_score(_as_dict(situation))
            if critic.passes:
                break

        if not critic.passes:
            situation.caveats = list(situation.caveats or []) + [
                f"Critic did not pass ({critic.score:.2f}): " + "; ".join(critic.notes[:2])
            ]

        check_situation(self.db, _as_dict(situation))

        return PipelineRun(
            situation=situation,
            critic=critic,
            attempts=attempts,
            signal_ids=sig_ids,
        )


def _default_next_action(module: str) -> str:
    return {
        "origination": "Assign coverage lead for briefing and outreach plan.",
        "carve_outs": "Draft divestment thesis and indicative value range.",
        "post_deal": "Convene integration steering committee on deviation.",
        "working_capital": "Owner to confirm ease-of-action and implementation plan.",
    }.get(module, "Human review required before approval.")


def _caveats(bundle: ScoreBundle, evs: Iterable[Evidence]) -> list[str]:
    out: list[str] = []
    evs = list(evs)
    if not evs:
        out.append("No evidence rows found for this subject.")
    if bundle.confidence < 0.3:
        out.append("Low evidence diversity — confidence is limited.")
    mock = [e for e in evs if e.mode == "fixture"]
    if mock and len(mock) == len(evs):
        out.append("All evidence is fixture/mock data; not live.")
    return out


def _as_dict(s: Situation) -> dict:
    return {
        "id": s.id,
        "module": s.module,
        "title": s.title,
        "dimensions": s.dimensions,
        "weights": s.weights,
        "confidence": s.confidence,
        "score": s.score,
        "evidence_ids": s.evidence_ids,
        "explanation": s.explanation,
        "explanation_cites": s.explanation_cites,
        "next_action": s.next_action,
    }
