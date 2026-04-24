"""Synthetic data generator for CS3 (post-deal) and CS4 (working capital).

Produces deterministic, realistic AR/AP/inventory ledgers and post-deal
KPI streams parametrised by sector and company size.

Run:
    docker compose exec backend python -m scripts.seed_synth --subject "SampleCo" --sector Consumer
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _rng(seed: str) -> random.Random:
    return random.Random(seed)


def gen_ar(subject: str, revenue: float, as_of: dt.datetime, n_customers: int = 40) -> list[dict]:
    r = _rng(f"{subject}-ar")
    avg_invoice = revenue / (n_customers * 12)
    rows: list[dict] = []
    for cust in range(n_customers):
        # Bigger customers skew top of distribution
        size = 0.5 + (cust / n_customers) * 4.0
        n_inv = r.randint(8, 18)
        for i in range(n_inv):
            invoice_date = as_of - dt.timedelta(days=r.randint(5, 120))
            due_date = invoice_date + dt.timedelta(days=45)
            # Some unpaid, biased to more recent
            paid = None
            if (as_of - invoice_date).days > 60 and r.random() > 0.25:
                paid = invoice_date + dt.timedelta(days=r.randint(30, 70))
            elif (as_of - invoice_date).days > 30 and r.random() > 0.5:
                paid = invoice_date + dt.timedelta(days=r.randint(25, 55))
            amount = round(avg_invoice * size * (0.5 + r.random()), 2)
            rows.append(
                {
                    "customer_id": f"C{cust:03d}",
                    "invoice_id": f"INV-{cust:03d}-{i:03d}",
                    "amount_usd": amount,
                    "invoice_date": invoice_date.date().isoformat(),
                    "due_date": due_date.date().isoformat(),
                    "paid_date": paid.date().isoformat() if paid else None,
                }
            )
    return rows


def gen_ap(subject: str, cogs: float, as_of: dt.datetime, n_suppliers: int = 30) -> list[dict]:
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
            rows.append(
                {
                    "supplier_id": f"S{sup:03d}",
                    "invoice_id": f"BILL-{sup:03d}-{i:03d}",
                    "amount_usd": amount,
                    "invoice_date": invoice_date.date().isoformat(),
                    "due_date": due_date.date().isoformat(),
                    "paid_date": paid.date().isoformat() if paid else None,
                }
            )
    return rows


def gen_inventory(subject: str, cogs: float, n_skus: int = 120) -> list[dict]:
    r = _rng(f"{subject}-inv")
    rows = []
    remaining = cogs * 0.18  # target ~65 days of COGS
    for i in range(n_skus):
        value = round(remaining / n_skus * (0.5 + 1.5 * r.random()), 2)
        days_held = r.randint(10, 220)
        rows.append({"sku": f"SKU-{i:04d}", "value_usd": value, "days_held": days_held})
    return rows


def gen_deal_case(subject: str, start: dt.datetime, end: dt.datetime) -> dict:
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


def gen_actuals(case: dict, noise: float = 0.12) -> dict:
    r = _rng("actuals")
    out: dict[str, list] = {}
    for ini in case["initiatives"]:
        n = 24
        rows = []
        s = dt.datetime.fromisoformat(ini["start"].replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(ini["end"].replace("Z", "+00:00"))
        step = (e - s) / (n - 1)
        # Make procurement slightly behind plan; cross-sell on plan; back-office over plan.
        drift = {"Procurement synergies": -0.15, "Cross-sell revenue uplift": 0.0,
                 "Back-office rationalisation": 0.08, "EBITDA uplift vs plan": -0.07}.get(ini["name"], 0.0)
        for i in range(n):
            ts = s + step * i
            frac = i / (n - 1)
            mid = ini["start_value"] + (ini["end_value"] - ini["start_value"]) * frac
            value = mid * (1 + drift + noise * (r.random() - 0.5))
            rows.append({"ts": ts.isoformat(), "value": round(value, 2)})
        out[ini["name"]] = rows
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subject", default="SampleCo")
    p.add_argument("--sector", default="Consumer")
    p.add_argument("--revenue", type=float, default=600_000_000)
    p.add_argument("--cogs", type=float, default=400_000_000)
    p.add_argument("--out", default=str(ROOT / "data" / "synth"))
    args = p.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(dt.timezone.utc)
    (outdir / "ar.json").write_text(json.dumps(gen_ar(args.subject, args.revenue, now), indent=2))
    (outdir / "ap.json").write_text(json.dumps(gen_ap(args.subject, args.cogs, now), indent=2))
    (outdir / "inventory.json").write_text(json.dumps(gen_inventory(args.subject, args.cogs), indent=2))

    case_start = now - dt.timedelta(days=30)
    case_end = now + dt.timedelta(days=700)
    case = gen_deal_case(args.subject, case_start, case_end)
    (outdir / "deal_case.json").write_text(json.dumps(case, indent=2))

    actuals = gen_actuals(case)
    (outdir / "actuals.json").write_text(json.dumps(actuals, indent=2))

    print(f"Synthetic data written to {outdir}")


if __name__ == "__main__":
    main()
