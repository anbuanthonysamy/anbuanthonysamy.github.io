"""In-process per-module source status tracker.

Records which external API fetches succeeded / failed during the most recent
scan. Exposed via the ``/api/v2/scan/source-status`` endpoint so the frontend
can show red/green indicators per module and be honest when a live integration
is unavailable.
"""
from __future__ import annotations

import datetime as dt
import threading
from dataclasses import asdict, dataclass
from typing import Literal, Optional

Status = Literal["ok", "error", "skipped", "unknown"]


# Declarative registry: which public APIs each module relies on.
# Frontend renders a row per entry so users see exactly which integrations
# are expected and whether they are currently live.
MODULE_SOURCES: dict[str, list[dict]] = {
    "origination": [
        {"id": "edgar.submissions", "name": "SEC EDGAR (submissions / 13D)", "required": True},
        {"id": "edgar.xbrl_companyfacts", "name": "SEC EDGAR (company facts / XBRL)", "required": True},
        {"id": "market.yfinance", "name": "Yahoo Finance (market data)", "required": True},
        {"id": "news.google_rss", "name": "Google News RSS", "required": False},
        {"id": "reg.companies_house", "name": "UK Companies House", "required": False},
    ],
    "carve_outs": [
        {"id": "edgar.xbrl_segment_facts", "name": "SEC EDGAR (segment facts)", "required": True},
        {"id": "edgar.xbrl_companyfacts", "name": "SEC EDGAR (company facts)", "required": True},
        {"id": "edgar.submissions", "name": "SEC EDGAR (submissions)", "required": False},
        {"id": "market.yfinance", "name": "Yahoo Finance (market data)", "required": True},
        {"id": "news.google_rss", "name": "Google News RSS", "required": False},
        {"id": "reg.companies_house", "name": "UK Companies House", "required": False},
    ],
    "post_deal": [
        {"id": "upload.client_kpi", "name": "Client KPI upload (mock)", "required": True, "mocked": True},
        {"id": "market.yfinance", "name": "Yahoo Finance (market context)", "required": False},
        {"id": "macro.fred", "name": "FRED macro indicators", "required": False},
        {"id": "news.google_rss", "name": "Google News RSS (sector context)", "required": False},
    ],
    "working_capital": [
        {"id": "upload.client_wc", "name": "Client AR/AP/inventory upload (mock)", "required": True, "mocked": True},
        {"id": "edgar.xbrl_companyfacts", "name": "SEC EDGAR (peer benchmarks)", "required": True},
        {"id": "market.yfinance", "name": "Yahoo Finance (peer market data)", "required": False},
    ],
}


@dataclass
class SourceAttempt:
    source_id: str
    status: Status
    last_attempt_at: str
    detail: Optional[str] = None
    mode: str = "live"  # "live" | "offline"


class SourceStatusTracker:
    """Thread-safe per-module source status map."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # module -> source_id -> SourceAttempt
        self._by_module: dict[str, dict[str, SourceAttempt]] = {}

    def record(
        self,
        module: str,
        source_id: str,
        status: Status,
        detail: Optional[str] = None,
        mode: str = "live",
    ) -> None:
        with self._lock:
            bucket = self._by_module.setdefault(module, {})
            bucket[source_id] = SourceAttempt(
                source_id=source_id,
                status=status,
                last_attempt_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                detail=(detail or "")[:500] if detail else None,
                mode=mode,
            )

    def reset_module(self, module: str) -> None:
        with self._lock:
            self._by_module[module] = {}

    def module_report(self, module: str) -> dict:
        """Return declarative source list merged with last-attempt statuses."""
        with self._lock:
            sources_spec = MODULE_SOURCES.get(module, [])
            attempts = self._by_module.get(module, {})

            rows = []
            for spec in sources_spec:
                att = attempts.get(spec["id"])
                rows.append({
                    "id": spec["id"],
                    "name": spec["name"],
                    "required": spec.get("required", False),
                    "mocked": spec.get("mocked", False),
                    "status": att.status if att else "unknown",
                    "last_attempt_at": att.last_attempt_at if att else None,
                    "detail": att.detail if att else None,
                    "mode": att.mode if att else "unknown",
                })

            # Rollup
            required_statuses = [r["status"] for r in rows if r["required"]]
            if not required_statuses:
                overall: Status = "unknown"
            elif all(s == "ok" for s in required_statuses):
                overall = "ok"
            elif any(s == "ok" for s in required_statuses):
                overall = "degraded"  # type: ignore[assignment]
            elif all(s in ("error", "skipped") for s in required_statuses):
                overall = "error"
            else:
                overall = "unknown"

            return {
                "module": module,
                "overall": overall,
                "sources": rows,
            }

    def all_modules_report(self) -> list[dict]:
        return [self.module_report(m) for m in MODULE_SOURCES.keys()]


TRACKER = SourceStatusTracker()
