"""Unsupported-claims check.

An output passes iff every evidence_id it cites exists in the evidence
store. The FastAPI response middleware runs this on every SituationOut
payload and on PDF briefings before returning.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Evidence


class UnsupportedClaimsError(Exception):
    pass


def check_ids(db: Session, evidence_ids: list[str]) -> None:
    if not evidence_ids:
        return
    found = set(db.scalars(select(Evidence.id).where(Evidence.id.in_(evidence_ids))).all())
    missing = [i for i in evidence_ids if i not in found]
    if missing:
        raise UnsupportedClaimsError(f"Unknown evidence_ids: {missing[:5]}")


def check_situation(db: Session, situation: dict) -> None:
    ids = list(situation.get("evidence_ids") or []) + list(situation.get("explanation_cites") or [])
    check_ids(db, ids)
