"""Continuous market scanner service for v2.

Periodically scans broad universe (~600 companies) and detects new situations
based on deterministic signals. No LLM during scan phase — explanations deferred
until user opens a situation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Geography, Module, Tier
from app.models.orm import Company, Situation
from app.sources.registry import BY_ID as SOURCES_BY_ID
from app.scanner.signals import (
    cs1_signal_scorer,
    cs2_signal_scorer,
    cs3_signal_scorer,
    cs4_signal_scorer,
)

log = logging.getLogger(__name__)


class ContinuousScanner:
    """Scans a broad universe and detects new opportunities via deterministic signals."""

    def __init__(self, db_session: Session, api_mode: str = "live"):
        self.db = db_session
        self.api_mode = api_mode  # "live" or "offline"

    async def scan_cs1_origination(
        self, geography: Geography = Geography.WORLDWIDE
    ) -> list[Situation]:
        """Scan for M&A origination opportunities (equity value > $1B)."""
        log.info(f"Scanning CS1 opportunities [{geography.value}]...")

        # Filter to companies > $1B equity value and matching geography
        companies = self._get_companies_for_scan(
            min_equity_value=1_000_000_000, geography=geography
        )

        situations = []
        for company in companies:
            try:
                score, signals = await cs1_signal_scorer(
                    company, self.api_mode, self.db
                )
                tier = self._tier_cs1(score, signals)

                # Upsert or create situation
                situation = self._upsert_situation(
                    company=company,
                    module=Module.ORIGINATION,
                    score=score,
                    tier=tier,
                    signals=signals,
                )
                situations.append(situation)
            except Exception as e:
                log.warning(f"Error scoring {company.ticker} for CS1: {e}")
                continue

        return situations

    async def scan_cs2_carve_outs(
        self, geography: Geography = Geography.WORLDWIDE
    ) -> list[Situation]:
        """Scan for carve-out opportunities (equity value > $750M)."""
        log.info(f"Scanning CS2 opportunities [{geography.value}]...")

        companies = self._get_companies_for_scan(
            min_equity_value=750_000_000, geography=geography
        )

        situations = []
        for company in companies:
            try:
                score, signals = await cs2_signal_scorer(
                    company, self.api_mode, self.db
                )
                tier = self._tier_cs2(score, signals)

                situation = self._upsert_situation(
                    company=company,
                    module=Module.CARVE_OUTS,
                    score=score,
                    tier=tier,
                    signals=signals,
                )
                situations.append(situation)
            except Exception as e:
                log.warning(f"Error scoring {company.ticker} for CS2: {e}")
                continue

        return situations

    async def scan_cs3_post_deal(self) -> list[Situation]:
        """Scan for post-deal value creation tracking."""
        log.info("Scanning CS3 situations...")
        # CS3: Track ongoing post-deal integrations (uploaded context)
        # For now, returns empty list; typically populated via upload
        return []

    async def scan_cs4_working_capital(self) -> list[Situation]:
        """Scan for working capital optimization."""
        log.info("Scanning CS4 situations...")
        # CS4: Typically populated via uploaded data
        return []

    def _get_companies_for_scan(
        self, min_equity_value: int, geography: Geography = Geography.WORLDWIDE
    ) -> list[Company]:
        """Get companies matching criteria for scanning."""
        stmt = select(Company).where(Company.equity_value >= min_equity_value)

        if geography == Geography.UK_ONLY:
            stmt = stmt.where(Company.country == "GB")

        return self.db.execute(stmt).scalars().all()

    def _tier_cs1(self, score: float, signals: dict) -> Tier:
        """Determine CS1 tier based on score and catalyst signals."""
        if score > 0.75 and self._has_cs1_catalyst(signals):
            return Tier.P1_HOT
        elif score > 0.55 and (
            signals.get("market_underperformance_pct", 0) > 15
            or signals.get("net_debt_ebitda", 0) > 3.5
        ):
            return Tier.P2_TARGET
        else:
            return Tier.P3_MONITOR

    def _tier_cs2(self, score: float, signals: dict) -> Tier:
        """Determine CS2 tier based on separation readiness."""
        separation_readiness = signals.get("separation_readiness", 0)
        stress_signals = signals.get("stress_signals", 0)

        if score > 0.75 and separation_readiness > 0.80:
            return Tier.P1_READY
        elif score > 0.60 and stress_signals > 0:
            return Tier.P2_CANDIDATE
        else:
            return Tier.P3_MONITOR

    def _tier_cs3(self, score: float, signals: dict) -> Tier:
        """Determine CS3 tier based on synergy gap."""
        synergy_gap = signals.get("synergy_gap_pct", 0)

        if synergy_gap > 25:
            return Tier.P1_AT_RISK
        elif synergy_gap >= 10:
            return Tier.P2_ON_TRACK
        else:
            return Tier.P3_MONITOR

    def _tier_cs4(self, score: float, signals: dict) -> Tier:
        """Determine CS4 tier based on cash opportunity."""
        cash_opportunity = signals.get("cash_opportunity_usd", 0)
        feasibility = signals.get("implementation_feasibility", 0)

        if cash_opportunity > 50_000_000 and feasibility > 0.70:
            return Tier.P1_QUICK_WIN
        elif cash_opportunity >= 20_000_000:
            return Tier.P2_SOLID
        else:
            return Tier.P3_MONITOR

    def _has_cs1_catalyst(self, signals: dict) -> bool:
        """Check if situation has one of the required CS1 catalysts."""
        return (
            signals.get("active_13d_filing", False)
            or signals.get("fresh_leadership_change", False)
            or signals.get("activist_board_appointment", False)
            or signals.get("debt_maturity_stress", False)
            or signals.get("announced_strategic_review", False)
            or signals.get("pe_interest_signals", False)
        )

    def _upsert_situation(
        self,
        company: Company,
        module: Module,
        score: float,
        tier: Tier,
        signals: dict,
    ) -> Situation:
        """Create or update situation, tracking first_seen_at and score_delta."""
        # Check if situation already exists
        stmt = select(Situation).where(
            Situation.company_id == company.id, Situation.module == module
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        now = datetime.utcnow()

        if existing:
            # Update: track score_delta, update last_updated_at
            score_delta = score - existing.score
            existing.score = score
            existing.tier = tier
            existing.signals = signals
            existing.score_delta = score_delta
            existing.last_updated_at = now
        else:
            # Create: set first_seen_at
            situation = Situation(
                company_id=company.id,
                module=module,
                score=score,
                tier=tier,
                signals=signals,
                first_seen_at=now,
                last_updated_at=now,
                score_delta=0.0,
            )
            self.db.add(situation)
            return situation

        self.db.commit()
        return existing


async def run_full_scan(
    db_session: Session,
    api_mode: str = "live",
    geography: Geography = Geography.WORLDWIDE,
) -> dict:
    """Run a full scan across all modules."""
    scanner = ContinuousScanner(db_session, api_mode=api_mode)

    results = {
        "cs1": await scanner.scan_cs1_origination(geography),
        "cs2": await scanner.scan_cs2_carve_outs(geography),
        "cs3": await scanner.scan_cs3_post_deal(),
        "cs4": await scanner.scan_cs4_working_capital(),
        "timestamp": datetime.utcnow(),
        "geography": geography.value,
    }

    return results
