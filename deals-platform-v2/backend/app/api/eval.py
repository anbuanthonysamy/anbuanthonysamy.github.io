"""Evaluation endpoints: labelled review log + backtest results."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models.orm import LLMCall, Review, Situation

router = APIRouter(tags=["eval"])


@router.get("/eval/labels")
def labels_summary(db: DbSession):
    total = db.scalar(select(func.count()).select_from(Review))
    rated = db.scalar(
        select(func.count()).select_from(Review).where(Review.rating_1_to_10.isnot(None))
    )
    by_action = dict(
        db.execute(select(Review.action, func.count()).group_by(Review.action)).all()
    )
    return {"total_reviews": total, "rated": rated, "by_action": by_action}


@router.get("/eval/llm")
def llm_summary(db: DbSession):
    total = db.scalar(select(func.count()).select_from(LLMCall))
    offline = db.scalar(select(func.count()).select_from(LLMCall).where(LLMCall.offline))
    cost = db.scalar(select(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)))
    tokens_in = db.scalar(select(func.coalesce(func.sum(LLMCall.input_tokens), 0)))
    tokens_out = db.scalar(select(func.coalesce(func.sum(LLMCall.output_tokens), 0)))
    return {"calls": total, "offline": offline, "cost_usd": float(cost),
            "tokens_in": int(tokens_in), "tokens_out": int(tokens_out)}


@router.get("/eval/coverage")
def coverage(db: DbSession):
    # Per-module count of pending/approved/accepted/rejected
    rows = db.execute(
        select(Situation.module, Situation.review_state, func.count())
        .group_by(Situation.module, Situation.review_state)
    ).all()
    out: dict = {}
    for module, state, n in rows:
        out.setdefault(module, {})[state] = n
    return out
