"""FastAPI application entry point."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import eval as eval_router
from app.api import settings as settings_router
from app.api import situations as situations_router
from app.api import sources as sources_router
from app.config import get_settings
from app.db import init_db
from app.modules.carve_outs.api import router as carve_outs_router
from app.modules.origination.api import router as origination_router
from app.modules.post_deal.api import router as post_deal_router
from app.modules.working_capital.api import router as working_capital_router
from app.scanner.api import router as scanner_router
from app.scanner.jobs import schedule_daily_scan
from app.scripts.seed_companies import seed_companies
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


@app.on_event("startup")
def _startup() -> None:
    init_db()
    log.info("DB initialised")

    # Seed test companies for development
    count = seed_companies()
    if count > 0:
        log.info(f"Seeded {count} test companies")

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
