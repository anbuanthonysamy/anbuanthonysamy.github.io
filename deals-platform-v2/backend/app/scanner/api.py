"""FastAPI routes for continuous scanner."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.enums import Geography, Module
from app.models.orm import Company, Situation
from app.scanner.service import run_full_scan
from app.scripts.seed_companies import seed_sp500_ftse100

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/scan", tags=["scanner"])


@router.post("/run")
async def trigger_scan(
    api_mode: str = Query("live", description="live or offline"),
    geography: str = Query("worldwide", description="worldwide or uk_only"),
) -> dict:
    """Manually trigger a full scan across all modules."""
    db = SessionLocal()
    try:
        try:
            geo = Geography(geography)
        except ValueError:
            return {"error": f"Invalid geography: {geography}"}

        log.info(f"Triggering manual scan (api_mode={api_mode}, geography={geography})...")

        results = await run_full_scan(db, api_mode=api_mode, geography=geo)

        return {
            "status": "success",
            "timestamp": results["timestamp"].isoformat(),
            "geography": results["geography"],
            "counts": {
                "cs1_origination": len(results["cs1"]),
                "cs2_carve_outs": len(results["cs2"]),
                "cs3_post_deal": len(results["cs3"]),
                "cs4_working_capital": len(results["cs4"]),
            },
            "total": sum(
                len(results[k])
                for k in ["cs1", "cs2", "cs3", "cs4"]
            ),
        }
    finally:
        db.close()


@router.get("/situations")
def list_situations(
    module: Optional[str] = Query(None, description="Filter by module"),
    tier: Optional[str] = Query(None, description="Filter by tier"),
    new_since: Optional[str] = Query(None, description="ISO timestamp"),
    sort_by: str = Query("priority", description="priority | value | score | recency"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List situations with filters and sorting."""
    db = SessionLocal()
    try:
        query = db.query(Situation)

        # Filters
        if module:
            query = query.filter(Situation.module == module)
        if tier:
            query = query.filter(Situation.tier == tier)
        if new_since:
            try:
                since_dt = datetime.fromisoformat(new_since)
                query = query.filter(Situation.first_seen_at >= since_dt)
            except ValueError:
                pass

        # Sorting
        if sort_by == "priority":
            query = query.order_by(Situation.tier).order_by(Situation.score.desc())
        elif sort_by == "value":
            # Would require join to company; for now sort by score proxy
            query = query.order_by(Situation.score.desc())
        elif sort_by == "score":
            query = query.order_by(Situation.score.desc())
        elif sort_by == "recency":
            query = query.order_by(Situation.last_updated_at.desc())
        else:
            query = query.order_by(Situation.score.desc())

        total = query.count()
        situations = query.limit(limit).offset(offset).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "situations": [
                {
                    "id": s.id,
                    "module": s.module,
                    "tier": s.tier,
                    "tier_colour": s.tier_colour,
                    "score": s.score,
                    "score_delta": s.score_delta,
                    "first_seen_at": s.first_seen_at.isoformat() if s.first_seen_at else None,
                    "last_updated_at": s.last_updated_at.isoformat() if s.last_updated_at else None,
                    "company_id": s.company_id,
                    "signals": s.signals,
                }
                for s in situations
            ],
        }
    finally:
        db.close()


@router.get("/situations/{situation_id}")
def get_situation(
    situation_id: str,
) -> dict:
    """Get a single situation with details."""
    db = SessionLocal()
    try:
        situation = db.query(Situation).filter(Situation.id == situation_id).first()
        if not situation:
            return {"error": "Situation not found"}

        return {
            "id": situation.id,
            "module": situation.module,
            "company_id": situation.company_id,
            "tier": situation.tier,
            "tier_colour": situation.tier_colour,
            "score": situation.score,
            "score_delta": situation.score_delta,
            "signals": situation.signals,
            "first_seen_at": situation.first_seen_at.isoformat() if situation.first_seen_at else None,
            "last_updated_at": situation.last_updated_at.isoformat() if situation.last_updated_at else None,
            "explanation": situation.explanation,
            "caveats": situation.caveats,
        }
    finally:
        db.close()


@router.post("/situations/{situation_id}/explain")
async def generate_explanation_on_demand(
    situation_id: str,
) -> dict:
    """Generate LLM explanation for a situation on-demand."""
    db = SessionLocal()
    try:
        situation = db.query(Situation).filter(Situation.id == situation_id).first()
        if not situation:
            return {"error": "Situation not found"}

        if situation.explanation:
            return {
                "id": situation.id,
                "explanation": situation.explanation,
                "cached": True,
            }

        # TODO: Call LLM to generate explanation based on signals
        # For now, return stub
        return {
            "id": situation.id,
            "explanation": "On-demand explanation generation not yet implemented",
            "cached": False,
        }
    finally:
        db.close()


@router.get("/debug")
def debug_status() -> dict:
    """Debug endpoint: show system status and company count."""
    db = SessionLocal()
    try:
        company_count = db.query(Company).count()
        situation_count = db.query(Situation).count()

        return {
            "status": "ok",
            "companies_in_db": company_count,
            "situations_in_db": situation_count,
            "message": f"Database has {company_count} companies and {situation_count} situations"
        }
    finally:
        db.close()


@router.post("/debug/load-companies")
def debug_load_companies() -> dict:
    """Debug endpoint: manually load S&P 500 + FTSE 100 companies."""
    db = SessionLocal()
    try:
        log.info("Manually loading S&P 500 + FTSE 100 companies...")
        count = seed_sp500_ftse100(db=db)

        total_companies = db.query(Company).count()

        return {
            "status": "success",
            "companies_loaded": count,
            "total_companies_in_db": total_companies,
            "message": f"Loaded {count} companies. Database now has {total_companies} total."
        }
    except Exception as e:
        log.error(f"Failed to load companies: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()
