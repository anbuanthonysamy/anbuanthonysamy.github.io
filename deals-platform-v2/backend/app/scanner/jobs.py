"""APScheduler jobs for continuous scanning."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.config import get_settings
from app.db import SessionLocal
from app.models.enums import Geography
from app.scanner.service import run_full_scan

log = logging.getLogger(__name__)


def schedule_daily_scan():
    """APScheduler job: run full scan daily at 02:00 UTC."""
    db = SessionLocal()
    try:
        log.info("Starting scheduled full scan...")
        start = datetime.utcnow()

        # Run scan for worldwide (default), then separately for UK
        asyncio.run(run_full_scan(db, api_mode="live", geography=Geography.WORLDWIDE))
        asyncio.run(run_full_scan(db, api_mode="live", geography=Geography.UK_ONLY))

        elapsed = (datetime.utcnow() - start).total_seconds()
        log.info(f"Scheduled scan completed in {elapsed:.1f}s")
    except Exception as e:
        log.error(f"Scheduled scan failed: {e}", exc_info=True)
    finally:
        db.close()
