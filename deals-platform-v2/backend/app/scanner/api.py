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
    sort_by: str = Query("score", description="priority | value | score | recency"),
    limit: Optional[int] = Query(None, description="Limit results; default 15 for CS1/CS2, unlimited for CS3/CS4"),
    offset: int = Query(0, ge=0),
    min_score: Optional[float] = Query(None, description="Minimum score threshold (0-1)"),
) -> dict:
    """List situations with filters, sorting, and configurable thresholds.

    Ranking strategy:
    - CS1/CS2: Top 15 by score (deal value as tiebreaker)
    - CS3/CS4: All opportunities by score (no limit)

    This prevents analysis paralysis while surfacing all viable opportunities.
    """
    db = SessionLocal()
    try:
        # Normalize module name (accept both hyphen and underscore variants)
        normalized_module = module
        if module == "carve-outs":
            normalized_module = "carve_outs"
        elif module == "post-deal":
            normalized_module = "post_deal"
        elif module == "working-capital":
            normalized_module = "working_capital"

        query = db.query(Situation).outerjoin(Company, Situation.company_id == Company.id)

        # Filters
        if normalized_module:
            query = query.filter(Situation.module == normalized_module)

        # Equity value thresholds per module (minimum size filters)
        if normalized_module == "origination":
            query = query.filter((Company.market_cap_usd >= 1_000_000_000) | (Company.market_cap_usd.is_(None)))
        elif normalized_module == "carve_outs":
            query = query.filter((Company.market_cap_usd >= 750_000_000) | (Company.market_cap_usd.is_(None)))

        # Score threshold (avoid low-quality opportunities)
        # Note: use explicit None check so callers can pass min_score=0 to see all.
        score_threshold = min_score if min_score is not None else 0.20
        query = query.filter(Situation.score >= score_threshold)

        if tier:
            query = query.filter(Situation.tier == tier)
        if new_since:
            try:
                since_dt = datetime.fromisoformat(new_since)
                query = query.filter(Situation.first_seen_at >= since_dt)
            except ValueError:
                pass

        # Sorting with deal value as secondary factor for CS1/CS2
        if sort_by == "priority":
            query = query.order_by(Situation.tier).order_by(Situation.score.desc()).order_by(Company.market_cap_usd.desc().nullslast())
        elif sort_by == "value":
            query = query.order_by(Company.market_cap_usd.desc().nullslast())
        elif sort_by == "recency":
            query = query.order_by(Situation.last_updated_at.desc())
        else:  # score (default)
            # Primary: score (desc), Secondary: deal value (desc) for tie-breaking
            query = query.order_by(Situation.score.desc()).order_by(Company.market_cap_usd.desc().nullslast())

        total = query.count()

        # Module-specific limit: CS1/CS2 top 15, CS3/CS4 all
        effective_limit = limit
        if effective_limit is None:
            if normalized_module in ("origination", "carve_outs"):
                effective_limit = 15
            else:  # CS3, CS4 - show all
                effective_limit = 500

        situations = query.limit(effective_limit).offset(offset).all()

        # Build company lookup for efficient access
        company_ids = {s.company_id for s in situations if s.company_id}
        companies = {c.id: c for c in db.query(Company).filter(Company.id.in_(company_ids)).all()} if company_ids else {}

        return {
            "total": total,
            "limit": effective_limit,
            "offset": offset,
            "score_threshold": score_threshold,
            "situations": [
                {
                    "id": s.id,
                    "module": s.module,
                    "rank": offset + idx + 1,
                    "tier": s.tier,
                    "tier_colour": s.tier_colour,
                    "score": s.score,
                    "score_delta": s.score_delta,
                    "first_seen_at": s.first_seen_at.isoformat() if s.first_seen_at else None,
                    "last_updated_at": s.last_updated_at.isoformat() if s.last_updated_at else None,
                    "company_id": s.company_id,
                    "company": {
                        "id": companies[s.company_id].id if s.company_id and s.company_id in companies else None,
                        "name": companies[s.company_id].name if s.company_id and s.company_id in companies else "Unknown",
                        "ticker": companies[s.company_id].ticker if s.company_id and s.company_id in companies else None,
                        "sector": companies[s.company_id].sector if s.company_id and s.company_id in companies else None,
                        "country": companies[s.company_id].country if s.company_id and s.company_id in companies else None,
                        "market_cap_usd": companies[s.company_id].market_cap_usd if s.company_id and s.company_id in companies else None,
                        "equity_value": companies[s.company_id].equity_value if s.company_id and s.company_id in companies else None,
                    },
                    "signals": s.signals,
                }
                for idx, s in enumerate(situations)
            ],
        }
    finally:
        db.close()


@router.get("/situations/{situation_id}")
def get_situation(
    situation_id: str,
) -> dict:
    """Get a single situation with details."""
    from app.shared.source_status import TRACKER

    db = SessionLocal()
    try:
        situation = db.query(Situation).filter(Situation.id == situation_id).first()
        if not situation:
            return {"error": "Situation not found"}

        company = db.query(Company).filter(Company.id == situation.company_id).first() if situation.company_id else None

        # Get source status for this module
        source_status = TRACKER.module_report(situation.module)

        return {
            "id": situation.id,
            "module": situation.module,
            "company_id": situation.company_id,
            "company": {
                "id": company.id if company else None,
                "name": company.name if company else "Unknown",
                "ticker": company.ticker if company else None,
                "sector": company.sector if company else None,
                "country": company.country if company else None,
                "market_cap_usd": company.market_cap_usd if company else None,
                "equity_value": company.equity_value if company else None,
            },
            "tier": situation.tier,
            "tier_colour": situation.tier_colour,
            "score": situation.score,
            "score_delta": situation.score_delta,
            "signals": situation.signals,
            "first_seen_at": situation.first_seen_at.isoformat() if situation.first_seen_at else None,
            "last_updated_at": situation.last_updated_at.isoformat() if situation.last_updated_at else None,
            "explanation": situation.explanation,
            "caveats": situation.caveats,
            "source_status": source_status,
        }
    finally:
        db.close()


@router.post("/situations/{situation_id}/explain")
async def generate_explanation_on_demand(
    situation_id: str,
) -> dict:
    """Generate LLM explanation for a situation on-demand."""
    from app.explain.explainer import generate_explanation

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

        # Generate explanation using LLM (or offline synthesis)
        explanation, cited_ids = generate_explanation(
            db,
            title=f"{situation.module.upper()} situation",
            dimensions=situation.dimensions or {},
            evidence_ids=situation.evidence_ids or [],
        )

        # Update situation with generated explanation
        situation.explanation = explanation
        db.commit()

        return {
            "id": situation.id,
            "explanation": explanation,
            "cached": False,
        }
    except Exception as e:
        log.error(f"Failed to generate explanation for {situation_id}: {e}")
        return {
            "error": f"Failed to generate explanation: {str(e)}"
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
