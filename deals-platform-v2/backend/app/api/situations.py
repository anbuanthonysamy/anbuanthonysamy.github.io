"""Shared Situations + Review queue API.

Every module's output is a Situation row. These routes power the review
queue, accept/reject/edit/approve flow, and the item detail panels.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import and_, select

from app.api.deps import DbSession, Reviewer
from app.explain.unsupported_claims import UnsupportedClaimsError, check_situation
from app.models.enums import DataScope, Module, ReviewState
from app.models.orm import Company, Evidence, Review, Situation
from app.models.schemas import EvidenceOut, ReviewOut, ReviewRequest, SituationOut

router = APIRouter(tags=["situations"])


def to_out(db, s: Situation) -> SituationOut:
    ev_rows: list[Evidence] = []
    if s.evidence_ids:
        ev_rows = list(
            db.scalars(select(Evidence).where(Evidence.id.in_(s.evidence_ids))).all()
        )
        order = {i: n for n, i in enumerate(s.evidence_ids)}
        ev_rows.sort(key=lambda e: order.get(e.id, 999))

    # Enforce scope: public-only modules cannot surface client evidence
    if s.module in (Module.ORIGINATION.value, Module.CARVE_OUTS.value):
        for e in ev_rows:
            if e.scope == DataScope.CLIENT.value:
                raise HTTPException(500, "Scope violation: client evidence in public module")

    evidence = [
        EvidenceOut(
            id=e.id,
            source_id=e.source_id,
            scope=e.scope,
            mode=e.mode,
            kind=e.kind,
            title=e.title,
            snippet=e.snippet,
            url=e.url,
            file_ref=e.file_ref,
            retrieved_at=e.retrieved_at,
            parsed_at=e.parsed_at,
            published_at=e.published_at,
            ok=e.ok,
        )
        for e in ev_rows
    ]
    return SituationOut(
        id=s.id,
        module=s.module,
        kind=s.kind,
        company_id=s.company_id,
        segment_id=s.segment_id,
        title=s.title,
        summary=s.summary,
        next_action=s.next_action,
        caveats=s.caveats or [],
        score=s.score,
        dimensions=s.dimensions or {},
        weights=s.weights or {},
        confidence=s.confidence,
        signal_ids=s.signal_ids or [],
        evidence_ids=s.evidence_ids or [],
        evidence=evidence,
        explanation=s.explanation,
        explanation_cites=s.explanation_cites or [],
        extras=s.extras or {},
        review=ReviewOut(
            state=s.review_state,
            reviewer=s.reviewer,
            ts=s.reviewed_at,
            reason=s.review_reason,
        ),
        created_at=s.created_at,
    )


@router.get("/situations", response_model=list[SituationOut])
def list_situations(db: DbSession, module: str | None = None, state: str | None = None,
                    limit: int = 100):
    q = select(Situation).order_by(Situation.score.desc())
    if module:
        q = q.where(Situation.module == module)
    if state:
        q = q.where(Situation.review_state == state)
    rows = db.scalars(q.limit(limit)).all()
    return [to_out(db, s) for s in rows]


@router.get("/situations/{sid}", response_model=SituationOut)
def get_situation(sid: str, db: DbSession):
    s = db.get(Situation, sid)
    if s is None:
        raise HTTPException(404, "situation not found")
    try:
        check_situation(db, {"evidence_ids": s.evidence_ids, "explanation_cites": s.explanation_cites})
    except UnsupportedClaimsError as e:
        raise HTTPException(500, f"Output rejected by unsupported-claims check: {e}") from e
    return to_out(db, s)


@router.post("/situations/{sid}/review", response_model=SituationOut)
def review_situation(sid: str, req: ReviewRequest, db: DbSession, reviewer: Reviewer):
    s = db.get(Situation, sid)
    if s is None:
        raise HTTPException(404, "situation not found")
    if not req.reason or not req.reason.strip():
        raise HTTPException(400, "reason is required")
    actor = req.reviewer or reviewer
    valid = {"accept", "reject", "edit", "approve"}
    if req.action not in valid:
        raise HTTPException(400, f"action must be one of {valid}")

    # edit patch
    if req.action == "edit" and req.edit_patch:
        for k, v in req.edit_patch.items():
            if k in ("title", "summary", "next_action"):
                setattr(s, k, v)
        s.review_state = ReviewState.EDITED.value
    elif req.action == "accept":
        s.review_state = ReviewState.ACCEPTED.value
    elif req.action == "reject":
        s.review_state = ReviewState.REJECTED.value
    elif req.action == "approve":
        # approval requires the item to have at least one evidence row
        if not s.evidence_ids:
            raise HTTPException(400, "cannot approve without evidence")
        s.review_state = ReviewState.APPROVED.value

    s.reviewer = actor
    s.reviewed_at = dt.datetime.now(dt.timezone.utc)
    s.review_reason = req.reason

    db.add(
        Review(
            situation_id=s.id,
            reviewer=actor,
            action=req.action,
            reason=req.reason,
            rating_1_to_10=req.rating_1_to_10,
            edit_patch=req.edit_patch,
        )
    )
    db.commit()
    db.refresh(s)
    return to_out(db, s)


@router.get("/situations/sector/heatmap")
def sector_heatmap(db: DbSession, module: str):
    # Build company_id -> sector map for scanner-generated situations
    company_sectors: dict[str, str] = {}
    for co in db.scalars(select(Company)).all():
        if co.id and co.sector:
            company_sectors[co.id] = co.sector

    q = (
        select(Situation)
        .where(and_(Situation.module == module))
        .order_by(Situation.score.desc())
    )
    buckets: dict[str, dict] = {}
    for s in db.scalars(q).all():
        extras = s.extras or {}
        # Prefer extras["sector"] (CS3/CS4), fall back to company sector (CS1/CS2)
        sector = (
            extras.get("sector")
            or (company_sectors.get(s.company_id) if s.company_id else None)
            or "Unclassified"
        )
        b = buckets.setdefault(
            sector, {"sector": sector, "count": 0, "scores": [], "ids": []}
        )
        b["count"] += 1
        b["scores"].append(s.score)
        if len(b["ids"]) < 3:
            b["ids"].append(s.id)
    out = []
    for b in buckets.values():
        out.append(
            {
                "sector": b["sector"],
                "count": b["count"],
                "avg_score": round(sum(b["scores"]) / len(b["scores"]), 3) if b["scores"] else 0,
                "top_situation_ids": b["ids"],
            }
        )
    out.sort(key=lambda x: -x["avg_score"])
    return out


@router.post("/situations/{sid}/explain")
def explain_situation(sid: str, db: DbSession):
    """On-demand LLM explanation for CS3/CS4 v1 situations."""
    from app.explain.explainer import generate_explanation

    s = db.get(Situation, sid)
    if s is None:
        raise HTTPException(404, "situation not found")

    if s.explanation:
        return {"id": sid, "explanation": s.explanation, "cached": True}

    try:
        explanation, cites = generate_explanation(
            db,
            title=s.title or "",
            dimensions=s.dimensions or {},
            evidence_ids=s.evidence_ids or [],
        )
        s.explanation = explanation
        s.explanation_cites = cites
        db.commit()
        return {"id": sid, "explanation": explanation, "cached": False}
    except Exception as e:
        raise HTTPException(503, f"LLM unavailable: {e}") from e
