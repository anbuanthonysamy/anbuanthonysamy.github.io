"""Client data management for CS3/CS4 (mocked company data).

Allows users to view, download, and upload mock client KPI/AR/AP data
separate from real peer benchmarks (which come from public APIs).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)


class ClientDataManager:
    """Manage seeded/uploaded mock client data for CS3 (post-deal) and CS4 (working capital)."""

    def __init__(self, data_dir: str | None = None) -> None:
        if data_dir is None:
            settings = get_settings()
            data_dir = settings.fixtures_dir
        self.data_dir = Path(data_dir)
        self.cs3_file = self.data_dir / "cs3_client_data.json"
        self.cs4_file = self.data_dir / "cs4_client_data.json"

    def get_cs3_data(self) -> dict:
        """Load or generate default CS3 client data (post-deal case)."""
        if self.cs3_file.exists():
            try:
                return json.loads(self.cs3_file.read_text())
            except Exception as e:
                log.warning(f"Failed to load CS3 data: {e}")
        return self._default_cs3_data()

    def get_cs4_data(self) -> dict:
        """Load or generate default CS4 client data (working capital case)."""
        if self.cs4_file.exists():
            try:
                return json.loads(self.cs4_file.read_text())
            except Exception as e:
                log.warning(f"Failed to load CS4 data: {e}")
        return self._default_cs4_data()

    def set_cs3_data(self, data: dict) -> dict:
        """Persist user-uploaded CS3 client data."""
        try:
            self.cs3_file.write_text(json.dumps(data, indent=2))
            return {"status": "saved", "file": str(self.cs3_file)}
        except Exception as e:
            log.error(f"Failed to save CS3 data: {e}")
            raise

    def set_cs4_data(self, data: dict) -> dict:
        """Persist user-uploaded CS4 client data."""
        try:
            self.cs4_file.write_text(json.dumps(data, indent=2))
            return {"status": "saved", "file": str(self.cs4_file)}
        except Exception as e:
            log.error(f"Failed to save CS4 data: {e}")
            raise

    @staticmethod
    def _default_cs3_data() -> dict:
        """Default mock client data for CS3 (post-deal value creation)."""
        return {
            "deal_name": "Acme Inc Acquisition",
            "close_date": "2024-01-15",
            "deal_value_usd": 500_000_000,
            "currency": "USD",
            "kpis": [
                {
                    "name": "Revenue",
                    "unit": "$M",
                    "target": 800,
                    "actual_q1": 750,
                    "actual_q2": 780,
                    "actual_q3": 810,
                    "forecast_q4": 850,
                },
                {
                    "name": "EBITDA",
                    "unit": "$M",
                    "target": 180,
                    "actual_q1": 160,
                    "actual_q2": 165,
                    "actual_q3": 175,
                    "forecast_q4": 190,
                },
                {
                    "name": "Cost Synergies Realized",
                    "unit": "$M",
                    "target": 80,
                    "actual_q1": 15,
                    "actual_q2": 30,
                    "actual_q3": 45,
                    "forecast_q4": 80,
                },
                {
                    "name": "Revenue Synergies",
                    "unit": "$M",
                    "target": 75,
                    "actual_q1": 0,
                    "actual_q2": 5,
                    "actual_q3": 15,
                    "forecast_q4": 50,
                },
            ],
            "synergy_gap": 0.32,
            "integration_status": "on_track",
            "risks": [
                "Customer retention: 2 key accounts under review",
                "Talent: Integration team down 15%",
                "Technology: ERP migration 3 weeks behind",
            ],
            "notes": "Overall tracking to plan. Cost realization ahead of schedule. Revenue synergies starting to materialize.",
        }

    @staticmethod
    def _default_cs4_data() -> dict:
        """Default mock client data for CS4 (working capital optimization)."""
        return {
            "company_name": "Widget Manufacturing Corp",
            "fiscal_year": 2024,
            "currency": "USD",
            "annual_revenue": 500_000_000,
            "annual_cogs": 300_000_000,
            "accounts_receivable": {
                "balance_usd": 85_000_000,
                "days_outstanding": 52,
                "benchmark_days": 35,
                "gap_days": 17,
                "opportunity_usd": 28_333_333,
                "aging": {
                    "current": 0.70,
                    "1_30_days": 0.20,
                    "31_60_days": 0.07,
                    "60_plus_days": 0.03,
                },
            },
            "inventory": {
                "balance_usd": 120_000_000,
                "days_outstanding": 145,
                "benchmark_days": 100,
                "gap_days": 45,
                "opportunity_usd": 75_000_000,
                "categories": {
                    "raw_materials": 0.30,
                    "work_in_progress": 0.35,
                    "finished_goods": 0.35,
                },
            },
            "accounts_payable": {
                "balance_usd": 95_000_000,
                "days_outstanding": 38,
                "benchmark_days": 48,
                "gap_days": -10,
                "extension_opportunity_usd": 16_666_667,
            },
            "total_wc_opportunity_usd": 120_000_000,
            "implementation_timeline_months": 9,
            "quick_win_pct": 0.35,
            "implementation_complexity": 0.65,
            "notes": "Strong DSO reduction opportunity. Inventory optimization requires process changes.",
        }


def get_client_data_manager() -> ClientDataManager:
    return ClientDataManager()
