"""Seed CS3 (post-deal) and CS4 (working capital) with synthetic demo data.

Mirrors the v1 approach: generate deterministic synthetic AR/AP/inventory
ledgers, a deal-case KPI plan with actuals, and default sector benchmarks.
Then run the ingest + compute pipelines so the CS3/CS4 module pages render
sensible visuals and situation details on first load.

Idempotent: checks for existing KPI rows and diagnostic situations before
seeding, so restarts don't duplicate data.
"""
from __future__ import annotations

import datetime as dt
import logging
import random
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Module
from app.models.orm import Benchmark, KPI, Situation
from app.modules.post_deal.service import (
    compute_deviations,
    ingest_actuals,
    ingest_deal_case,
)
from app.modules.working_capital.service import WCInputs, diagnose

log = logging.getLogger(__name__)


def _rng(seed: str) -> random.Random:
    return random.Random(seed)


def _gen_ar(subject: str, revenue: float, as_of: dt.datetime, n_customers: int = 40) -> list[dict]:
    r = _rng(f"{subject}-ar")
    avg_invoice = revenue / (n_customers * 12)
    rows: list[dict] = []
    for cust in range(n_customers):
        size = 0.5 + (cust / n_customers) * 4.0
        n_inv = r.randint(8, 18)
        for i in range(n_inv):
            invoice_date = as_of - dt.timedelta(days=r.randint(5, 120))
            due_date = invoice_date + dt.timedelta(days=45)
            paid = None
            if (as_of - invoice_date).days > 60 and r.random() > 0.25:
                paid = invoice_date + dt.timedelta(days=r.randint(30, 70))
            elif (as_of - invoice_date).days > 30 and r.random() > 0.5:
                paid = invoice_date + dt.timedelta(days=r.randint(25, 55))
            amount = round(avg_invoice * size * (0.5 + r.random()), 2)
            rows.append({
                "customer_id": f"C{cust:03d}",
                "invoice_id": f"INV-{cust:03d}-{i:03d}",
                "amount_usd": amount,
                "invoice_date": invoice_date.isoformat(),
                "due_date": due_date.isoformat(),
                "paid_date": paid.isoformat() if paid else None,
            })
    return rows


def _gen_ap(subject: str, cogs: float, as_of: dt.datetime, n_suppliers: int = 30) -> list[dict]:
    r = _rng(f"{subject}-ap")
    avg_invoice = cogs / (n_suppliers * 10)
    rows: list[dict] = []
    for sup in range(n_suppliers):
        n_inv = r.randint(6, 14)
        size = 0.5 + (sup / n_suppliers) * 4.0
        for i in range(n_inv):
            invoice_date = as_of - dt.timedelta(days=r.randint(5, 120))
            due_date = invoice_date + dt.timedelta(days=45)
            paid = None
            if (as_of - invoice_date).days > 60 and r.random() > 0.3:
                paid = invoice_date + dt.timedelta(days=r.randint(35, 80))
            amount = round(avg_invoice * size * (0.5 + r.random()), 2)
            rows.append({
                "supplier_id": f"S{sup:03d}",
                "invoice_id": f"BILL-{sup:03d}-{i:03d}",
                "amount_usd": amount,
                "invoice_date": invoice_date.isoformat(),
                "due_date": due_date.isoformat(),
                "paid_date": paid.isoformat() if paid else None,
            })
    return rows


def _gen_inventory(subject: str, cogs: float, n_skus: int = 120) -> list[dict]:
    r = _rng(f"{subject}-inv")
    rows = []
    target_value = cogs * 0.18  # ~65 days of COGS
    for i in range(n_skus):
        value = round(target_value / n_skus * (0.5 + 1.5 * r.random()), 2)
        days_held = r.randint(10, 220)
        rows.append({"sku": f"SKU-{i:04d}", "value_usd": value, "days_held": days_held})
    return rows


def _gen_deal_case(subject: str, start: dt.datetime, end: dt.datetime) -> dict:
    return {
        "name": f"{subject} Integration — deal case v1",
        "initiatives": [
            {"name": "Procurement synergies", "unit": "USD m/year",
             "curve": "s_curve", "start_value": 0, "end_value": 45,
             "start": start.isoformat(), "end": end.isoformat(), "tolerance": 0.15},
            {"name": "Back-office rationalisation", "unit": "USD m/year",
             "curve": "linear", "start_value": 0, "end_value": 25,
             "start": start.isoformat(), "end": end.isoformat(), "tolerance": 0.10},
            {"name": "Cross-sell revenue uplift", "unit": "USD m/year",
             "curve": "j_curve", "start_value": 0, "end_value": 60,
             "start": start.isoformat(), "end": end.isoformat(), "tolerance": 0.20},
            {"name": "EBITDA uplift vs plan", "unit": "USD m/year",
             "curve": "s_curve", "start_value": 20, "end_value": 130,
             "start": start.isoformat(), "end": end.isoformat(), "tolerance": 0.12},
        ],
    }


def _gen_actuals(case: dict, noise: float = 0.12) -> dict[str, list[dict]]:
    r = _rng("actuals")
    out: dict[str, list[dict]] = {}
    drifts = {
        "Procurement synergies": -0.15,
        "Cross-sell revenue uplift": 0.0,
        "Back-office rationalisation": 0.08,
        "EBITDA uplift vs plan": -0.07,
    }
    n_points = 24
    for ini in case["initiatives"]:
        rows = []
        s = dt.datetime.fromisoformat(ini["start"].replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(ini["end"].replace("Z", "+00:00"))
        step = (e - s) / (n_points - 1)
        drift = drifts.get(ini["name"], 0.0)
        for i in range(n_points):
            ts = s + step * i
            frac = i / (n_points - 1)
            mid = ini["start_value"] + (ini["end_value"] - ini["start_value"]) * frac
            value = mid * (1 + drift + noise * (r.random() - 0.5))
            rows.append({"ts": ts.isoformat(), "value": round(value, 2)})
        out[ini["name"]] = rows
    return out


def _to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ("invoice_date", "due_date", "paid_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def _seed_wc_benchmarks(db: Session) -> int:
    """Seed default DSO/DPO/DIO benchmarks for common sectors."""
    sectors = ("Consumer", "Industrials", "Technology", "Generic",
               "Consumer Defensive", "Consumer Cyclical", "Healthcare",
               "Financials", "Energy", "Materials")
    metrics = {
        "DSO": (42.0, 50.0, 60.0),
        "DPO": (35.0, 45.0, 55.0),
        "DIO": (40.0, 55.0, 75.0),
    }
    added = 0
    for sector in sectors:
        for metric, (p40, p50, p60) in metrics.items():
            existing = db.scalar(
                select(Benchmark)
                .where(Benchmark.module == "working_capital")
                .where(Benchmark.sector == sector)
                .where(Benchmark.metric == metric)
            )
            if existing:
                continue
            db.add(Benchmark(
                module="working_capital", sector=sector, metric=metric,
                p40=p40, p50=p50, p60=p60, sample_size=12, evidence_ids=[],
            ))
            added += 1
    db.commit()
    return added


def seed_cs3_cs4(db: Session, subject: str = "SampleCo", sector: str = "Consumer",
                 revenue: float = 600_000_000, cogs: float = 400_000_000) -> dict[str, Any]:
    """Seed CS3 KPIs + actuals and CS4 diagnostic.

    Idempotent: if KPIs or CS4 situations already exist for the module, skip
    that portion.
    """
    result = {"cs3_kpis": 0, "cs3_situations": 0, "cs4_situations": 0, "benchmarks": 0}

    result["benchmarks"] = _seed_wc_benchmarks(db)

    now = dt.datetime.now(dt.timezone.utc)

    # CS3: Seed deal case + actuals if no KPIs exist
    cs3_kpi_count = db.scalar(
        select(KPI).where(KPI.module == Module.POST_DEAL.value).limit(1)
    )
    if cs3_kpi_count is None:
        case_start = now - dt.timedelta(days=30)
        case_end = now + dt.timedelta(days=700)
        case = _gen_deal_case(subject, case_start, case_end)
        kpis = ingest_deal_case(db, case, upload_id=f"seed:{subject}:deal_case")
        actuals = _gen_actuals(case)
        for name, rows in actuals.items():
            ingest_actuals(db, name, rows)
        db.commit()
        sits = compute_deviations(db)
        result["cs3_kpis"] = len(kpis)
        result["cs3_situations"] = len(sits)
        log.info(f"CS3 seeded: {len(kpis)} KPIs, {len(sits)} deviation situations")
    else:
        log.info("CS3 KPIs already present — skipping CS3 seed")

    # CS4: Seed diagnostic if no working-capital situations exist
    cs4_existing = db.scalar(
        select(Situation).where(Situation.module == Module.WORKING_CAPITAL.value).limit(1)
    )
    if cs4_existing is None:
        ar = _to_df(_gen_ar(subject, revenue, now))
        ap = _to_df(_gen_ap(subject, cogs, now))
        inv = pd.DataFrame(_gen_inventory(subject, cogs))
        sits = diagnose(
            db,
            inp=WCInputs(
                revenue_annual_usd=revenue,
                cogs_annual_usd=cogs,
                ar_df=ar, ap_df=ap, inv_df=inv,
                as_of=now, sector=sector,
            ),
            subject_name=subject,
        )
        result["cs4_situations"] = len(sits)
        log.info(f"CS4 seeded: {len(sits)} diagnostic situations")
    else:
        log.info("CS4 situations already present — skipping CS4 seed")

    return result


if __name__ == "__main__":
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        r = seed_cs3_cs4(db)
        print(f"Seeded CS3/CS4: {r}")
    finally:
        db.close()
