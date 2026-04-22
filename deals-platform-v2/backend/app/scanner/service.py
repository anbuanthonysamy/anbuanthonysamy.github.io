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
from app.shared.source_status import TRACKER
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
        TRACKER.reset_module("origination")

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
        TRACKER.reset_module("carve_outs")

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
        stmt = select(Company).where(Company.market_cap_usd >= min_equity_value)

        if geography == Geography.UK_ONLY:
            stmt = stmt.where(Company.country == "UK")

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

    def _dimensions_from_signals(self, module: Module, signals: dict) -> dict:
        """Map deterministic signal values onto named score dimensions.

        Review-queue cards and the score-breakdown panel render one bar per
        dimension. Without this mapping the card shows "no dimensions scored".
        """
        def _clip(x: float) -> float:
            if x is None:
                return 0.0
            return max(0.0, min(1.0, float(x)))

        if module == Module.ORIGINATION:
            return {
                "likelihood": _clip(signals.get("activist_signal_strength", 0)),
                "expected_scale": _clip(
                    (signals.get("net_debt_ebitda", 0) or 0) / 5.0
                ),
                "timing_fit": 1.0 if signals.get("active_13d_filing") else 0.3,
                "confidence": _clip(
                    (signals.get("margin_compression_pct", 0) or 0) / 30.0
                ),
                "sector_relevance": _clip(
                    (signals.get("pe_discount_pct", 0) or 0) / 40.0
                ),
                "strategic_relevance": 1.0
                if signals.get("leverage_stress")
                else 0.3,
            }
        if module == Module.CARVE_OUTS:
            return {
                "divestment_likelihood": _clip(
                    signals.get("separation_readiness", 0)
                ),
                "urgency": _clip(signals.get("stress_signals", 0)),
                "feasibility": _clip(signals.get("separation_readiness", 0)),
                "expected_value": _clip(
                    (signals.get("standalone_revenue_pct", 0) or 0)
                ),
                "confidence": 0.5,
            }
        if module == Module.POST_DEAL:
            return {
                "synergy_gap": _clip(
                    (signals.get("synergy_gap_pct", 0) or 0) / 100.0
                ),
                "execution_risk": _clip(signals.get("execution_risk", 0.3)),
                "value_at_stake": _clip(signals.get("value_at_stake", 0.3)),
            }
        if module == Module.WORKING_CAPITAL:
            return {
                "cash_opportunity": _clip(
                    (signals.get("cash_opportunity_usd", 0) or 0) / 100_000_000.0
                ),
                "feasibility": _clip(
                    signals.get("implementation_feasibility", 0)
                ),
                "quick_win": _clip(signals.get("quick_win_pct", 0)),
            }
        return {}

    def _confidence_from_signals(self, signals: dict) -> float:
        """Return a coarse confidence based on how many signals carry real data."""
        if not signals:
            return 0.0
        meaningful = 0
        total = 0
        for key, val in signals.items():
            total += 1
            if isinstance(val, bool):
                if val:
                    meaningful += 1
            elif isinstance(val, (int, float)) and val:
                meaningful += 1
        if total == 0:
            return 0.0
        return round(min(1.0, meaningful / total + 0.2), 2)

    def _summary_from_signals(
        self, module: Module, company: Company, signals: dict
    ) -> str:
        """Build a one-line human summary from the top few active signals."""
        active: list[str] = []
        for k, v in signals.items():
            label = k.replace("_", " ")
            if isinstance(v, bool) and v:
                active.append(label)
            elif isinstance(v, (int, float)) and v:
                active.append(f"{label} {v:.1f}")
            if len(active) >= 3:
                break
        if not active:
            return f"{company.name}: no material signals triggered; carried for universe coverage."
        return f"{company.name}: " + "; ".join(active) + "."

    def _build_evidence_from_sources(
        self, company: Company, module: Module, signals: dict
    ) -> tuple[list[str], list]:
        """Create Evidence rows for each public source that contributed real data.

        Keeps the Review Queue 'evidence' counter honest and gives the
        on-demand explanation endpoint something to cite.
        """
        from app.models.enums import DataScope, SourceMode
        from app.shared.evidence import upsert_evidence

        ids: list[str] = []
        records = []
        module_key = module.value if hasattr(module, "value") else str(module)
        has_financial_metric = any(
            isinstance(signals.get(k), (int, float)) and signals.get(k)
            for k in (
                "net_debt_ebitda",
                "margin_compression_pct",
                "pe_discount_pct",
                "market_underperformance_pct",
            )
        )
        has_catalyst = any(
            signals.get(k)
            for k in (
                "active_13d_filing",
                "fresh_leadership_change",
                "activist_board_appointment",
            )
        )

        # edgar.xbrl_companyfacts if we derived any financial metric
        if has_financial_metric and company.cik:
            ev = upsert_evidence(
                self.db,
                source_id="edgar.xbrl_companyfacts",
                scope=DataScope.PUBLIC,
                mode=SourceMode.LIVE,
                kind="xbrl_snapshot",
                title=f"{company.name} — XBRL financial metrics",
                snippet=(
                    f"Net Debt/EBITDA {signals.get('net_debt_ebitda', 0):.2f}; "
                    f"margin compression {signals.get('margin_compression_pct', 0):.1f}%."
                ),
                company_id=company.id,
                meta={"module": module_key},
            )
            ids.append(ev.id)
            records.append(ev)

        # market.yfinance for market-level signals
        if company.ticker and (
            signals.get("pe_discount_pct")
            or signals.get("market_underperformance_pct")
        ):
            ev = upsert_evidence(
                self.db,
                source_id="market.yfinance",
                scope=DataScope.PUBLIC,
                mode=SourceMode.LIVE,
                kind="market",
                title=f"{company.name} — market snapshot ({company.ticker})",
                snippet=(
                    f"PE discount {signals.get('pe_discount_pct', 0):.1f}%; "
                    f"market underperformance {signals.get('market_underperformance_pct', 0):.1f}%."
                ),
                company_id=company.id,
                meta={"module": module_key},
            )
            ids.append(ev.id)
            records.append(ev)

        # edgar.submissions for 13D / leadership filings
        if has_catalyst and company.cik:
            ev = upsert_evidence(
                self.db,
                source_id="edgar.submissions",
                scope=DataScope.PUBLIC,
                mode=SourceMode.LIVE,
                kind="filing",
                title=f"{company.name} — recent filings suggest catalyst",
                snippet=(
                    f"13D filing active: {signals.get('active_13d_filing', False)}; "
                    f"leadership change: {signals.get('fresh_leadership_change', False)}."
                ),
                company_id=company.id,
                meta={"module": module_key},
            )
            ids.append(ev.id)
            records.append(ev)

        return ids, records

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

        # Derive dimensions, confidence, summary from signals so that the
        # Review Queue and explanation endpoints have useful data. Without
        # this, the scanner writes bare score+signals rows and every card
        # displays "conf 0% / 0 evidence / no dimensions".
        dimensions = self._dimensions_from_signals(module, signals)
        confidence = self._confidence_from_signals(signals)
        summary = self._summary_from_signals(module, company, signals)
        evidence_ids, evidence_records = self._build_evidence_from_sources(
            company, module, signals
        )

        if existing:
            # Update: track score_delta, update last_updated_at
            score_delta = score - existing.score
            existing.score = score
            existing.tier = tier
            existing.signals = signals
            existing.score_delta = score_delta
            existing.last_updated_at = now
            existing.dimensions = dimensions
            existing.confidence = confidence
            existing.summary = summary
            existing.evidence_ids = evidence_ids
            situation = existing
        else:
            # Create: set first_seen_at
            title = f"{company.name} — {module.value.replace('_', ' ').title()}"
            situation = Situation(
                title=title,
                summary=summary,
                company_id=company.id,
                module=module.value,
                score=score,
                tier=tier,
                signals=signals,
                dimensions=dimensions,
                confidence=confidence,
                evidence_ids=evidence_ids,
                first_seen_at=now,
                last_updated_at=now,
                score_delta=0.0,
            )
            self.db.add(situation)

        self.db.commit()
        return situation


async def run_full_scan(
    db_session: Session,
    api_mode: str = "auto",
    geography: Geography = Geography.WORLDWIDE,
) -> dict:
    """Run a full scan across all modules.

    If ``api_mode`` is ``auto`` the effective mode is read from the
    persisted user preference (SettingKV). Otherwise the caller's explicit
    ``live`` / ``offline`` value is honoured.
    """
    from app.shared.api_mode import get_mode

    if api_mode == "auto":
        api_mode = get_mode(db_session)

    scanner = ContinuousScanner(db_session, api_mode=api_mode)

    results = {
        "cs1": await scanner.scan_cs1_origination(geography),
        "cs2": await scanner.scan_cs2_carve_outs(geography),
        "cs3": await scanner.scan_cs3_post_deal(),
        "cs4": await scanner.scan_cs4_working_capital(),
        "timestamp": datetime.utcnow(),
    }

    # Sync per-module TRACKER state into the global Source DB table so the
    # /sources page reflects what the scan just did instead of always
    # displaying "never_refreshed".
    try:
        _sync_tracker_to_source_rows(db_session)
    except Exception as e:
        log.warning(f"Failed to sync tracker to source rows: {e}")

    results["geography"] = geography.value
    results["api_mode"] = api_mode
    return results


def _sync_tracker_to_source_rows(db: Session) -> None:
    """Project in-memory TRACKER state onto the persisted Source DB table.

    The /sources page reads from the Source table; without this sync,
    every row shows "never_refreshed" regardless of how recently scans ran.
    """
    from datetime import datetime as _dt, timezone
    from app.models.orm import Source as SourceRow
    from app.shared.source_status import TRACKER, MODULE_SOURCES
    from app.sources.registry import BY_ID as SOURCES

    # Collapse per-module statuses into one row per source_id: latest attempt wins.
    latest: dict[str, dict] = {}
    for module, specs in MODULE_SOURCES.items():
        report = TRACKER.module_report(module)
        for row in report.get("sources", []):
            sid = row["id"]
            ts_str = row.get("last_attempt_at")
            if not ts_str:
                continue
            try:
                ts = _dt.fromisoformat(ts_str)
            except Exception:
                continue
            current = latest.get(sid)
            if current is None or ts > current["ts"]:
                latest[sid] = {
                    "ts": ts,
                    "status": row.get("status") or "unknown",
                    "mode": row.get("mode") or "live",
                    "detail": row.get("detail"),
                }

    for sid, info in latest.items():
        src = SOURCES.get(sid)
        name = src.name if src else sid
        db_row = db.scalar(select(SourceRow).where(SourceRow.id == sid))
        if db_row is None:
            db_row = SourceRow(id=sid, name=name, mode=info["mode"])
            db.add(db_row)
        db_row.last_refresh_at = info["ts"].astimezone(timezone.utc).replace(tzinfo=None)
        db_row.last_status = info["status"]
        db_row.last_error = info["detail"] if info["status"] == "error" else None
        db_row.mode = info["mode"]

    db.commit()
