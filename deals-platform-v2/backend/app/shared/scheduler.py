"""Scheduler — daily source refresh. Disabled in tests; optional in dev."""
from __future__ import annotations

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

log = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    s = get_settings()
    jobstores = {"default": SQLAlchemyJobStore(url=s.database_url)}
    sched = BackgroundScheduler(jobstores=jobstores)
    return sched
