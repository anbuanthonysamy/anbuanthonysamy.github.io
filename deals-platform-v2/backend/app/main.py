"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import logging
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import eval as eval_router
from app.api import settings as settings_router
from app.api import situations as situations_router
from app.api import sources as sources_router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models.orm import Company
from app.modules.carve_outs.api import router as carve_outs_router
from app.modules.origination.api import router as origination_router
from app.modules.post_deal.api import router as post_deal_router
from app.modules.working_capital.api import router as working_capital_router
from app.scanner.api import router as scanner_router
from app.scanner.jobs import schedule_daily_scan
from app.scanner.service import run_full_scan
from app.scripts.seed_companies import seed_sp500_ftse100
from app.shared.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

settings = get_settings()

app = FastAPI(title="Deals Platform PoC", version="0.1.0")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


def _check_db_empty() -> bool:
    """Check if Company table is empty."""
    db = SessionLocal()
    try:
        company_count = db.query(Company).count()
        return company_count == 0
    finally:
        db.close()


def _trigger_initial_scan() -> None:
    """Load S&P 500/FTSE 100 companies and run initial scan in background."""
    db = SessionLocal()
    try:
        log.info("Database is empty. Loading S&P 500 + FTSE 100 companies...")
        count = seed_sp500_ftse100(db=db)
        log.info(f"Loaded {count} companies from S&P 500 + FTSE 100")

        log.info("Triggering initial scan with live data...")
        # Run async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_full_scan(db, api_mode="live"))
            log.info("Initial scan completed")
        finally:
            loop.close()
    except Exception as e:
        log.error(f"Initial scan failed: {e}")
    finally:
        db.close()


@app.on_event("startup")
def _startup() -> None:
    init_db()
    log.info("DB initialised")

    # Check if database is empty and trigger initial scan with live data
    if _check_db_empty():
        # Run scan in background thread so startup completes quickly
        scan_thread = Thread(target=_trigger_initial_scan, daemon=False)
        scan_thread.start()
    else:
        log.info("Database has existing companies, skipping initial scan")

    if settings.enable_scheduler:
        sched = build_scheduler()
        sched.add_job(
            schedule_daily_scan,
            "cron",
            hour=2,
            minute=0,
            id="daily_scan",
            replace_existing=True,
        )
        sched.start()
        log.info("Scheduler started: daily scan at 02:00 UTC")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "live_llm": settings.live_llm, "offline": not settings.live_llm}


app.include_router(situations_router.router)
app.include_router(sources_router.router)
app.include_router(settings_router.router)
app.include_router(eval_router.router)
app.include_router(origination_router)
app.include_router(carve_outs_router)
app.include_router(post_deal_router)
app.include_router(working_capital_router)
app.include_router(scanner_router)
