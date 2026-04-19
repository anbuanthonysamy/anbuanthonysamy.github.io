"""CS4 — Working capital diagnostic.

Inputs: AR, AP, inventory, historical financials (uploaded). Benchmarks:
public EDGAR XBRL peers (optional) + configurable manual benchmarks.

Computes DSO/DPO/DIO, ageing, concentration and produces Recommendations
with cash-unlock bands.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.explain.explainer import generate_explanation
from app.models.enums import DataScope, Module, ReviewState, SourceMode
from app.models.orm import Benchmark, Evidence, KPI, KPIActual, Situation
from app.scoring.engine import compose, load_weights
from app.shared.evidence import upsert_evidence


@dataclass
class WCInputs:
    revenue_annual_usd: float
    cogs_annual_usd: float
    ar_df: pd.DataFrame  # columns: customer_id, invoice_id, amount_usd, invoice_date, due_date, paid_date (nullable)
    ap_df: pd.DataFrame  # columns: supplier_id, invoice_id, amount_usd, invoice_date, due_date, paid_date
    inv_df: pd.DataFrame  # columns: sku, value_usd, days_held
    as_of: dt.datetime
    sector: str = "Generic"


@dataclass
class WCMetrics:
    dso_days: float
    dpo_days: float
    dio_days: float
    ar_outstanding_usd: float
    ap_outstanding_usd: float
    inv_value_usd: float
    ar_aging: dict[str, float]  # bucket -> value
    customer_concentration_top5: float  # share of AR from top 5
    supplier_concentration_top5: float


def compute_metrics(inp: WCInputs) -> WCMetrics:
    ar_out = float(inp.ar_df.loc[inp.ar_df["paid_date"].isna(), "amount_usd"].sum()) \
        if "paid_date" in inp.ar_df.columns else float(inp.ar_df["amount_usd"].sum())
    ap_out = float(inp.ap_df.loc[inp.ap_df["paid_date"].isna(), "amount_usd"].sum()) \
        if "paid_date" in inp.ap_df.columns else float(inp.ap_df["amount_usd"].sum())
    inv_value = float(inp.inv_df["value_usd"].sum())

    revenue_per_day = inp.revenue_annual_usd / 365
    cogs_per_day = inp.cogs_annual_usd / 365

    dso = ar_out / revenue_per_day if revenue_per_day else 0.0
    dpo = ap_out / cogs_per_day if cogs_per_day else 0.0
    dio = inv_value / cogs_per_day if cogs_per_day else 0.0

    # AR aging buckets (0-30, 31-60, 61-90, 90+)
    aging = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    if "invoice_date" in inp.ar_df.columns:
        unpaid = inp.ar_df[inp.ar_df["paid_date"].isna()] if "paid_date" in inp.ar_df.columns else inp.ar_df
        for _, r in unpaid.iterrows():
            age = (inp.as_of - pd.to_datetime(r["invoice_date"], utc=True).to_pydatetime()).days
            amt = float(r["amount_usd"])
            if age <= 30:
                aging["0-30"] += amt
            elif age <= 60:
                aging["31-60"] += amt
            elif age <= 90:
                aging["61-90"] += amt
            else:
                aging["90+"] += amt

    # Concentration
    def _top5_share(df: pd.DataFrame, key: str) -> float:
        if df.empty or key not in df.columns:
            return 0.0
        s = df.groupby(key)["amount_usd"].sum().sort_values(ascending=False)
        top = s.head(5).sum()
        total = s.sum() or 1.0
        return round(top / total, 3)

    return WCMetrics(
        dso_days=round(dso, 1),
        dpo_days=round(dpo, 1),
        dio_days=round(dio, 1),
        ar_outstanding_usd=round(ar_out, 0),
        ap_outstanding_usd=round(ap_out, 0),
        inv_value_usd=round(inv_value, 0),
        ar_aging=aging,
        customer_concentration_top5=_top5_share(inp.ar_df, "customer_id"),
        supplier_concentration_top5=_top5_share(inp.ap_df, "supplier_id"),
    )


def get_or_fallback_benchmark(
    db: Session, sector: str, metric: str
) -> tuple[float, float, float, int]:
    """Return (p40, p50, p60, sample_size). Falls back to generic defaults
    if no peer benchmark is stored."""
    row = db.scalar(
        select(Benchmark)
        .where(Benchmark.sector == sector)
        .where(Benchmark.metric == metric)
        .order_by(Benchmark.computed_at.desc())
    )
    if row:
        return row.p40, row.p50, row.p60, row.sample_size

    # Very broad defaults — documented in docs/scoring-framework.md
    defaults = {
        "DSO": (42.0, 50.0, 60.0, 0),
        "DPO": (35.0, 45.0, 55.0, 0),
        "DIO": (40.0, 55.0, 75.0, 0),
    }
    return defaults.get(metric, (0, 0, 0, 0))


def cash_opportunity(
    subject_days: float, p40: float, p50: float, p60: float, daily_driver: float, direction: str
) -> tuple[float, float, float]:
    """For DSO/DIO, lower is better: gap = subject - peer. For DPO, higher is
    better: gap = peer - subject."""
    if direction == "lower":
        gaps = (subject_days - p60, subject_days - p50, subject_days - p40)
    else:  # "higher"
        gaps = (p40 - subject_days, p50 - subject_days, p60 - subject_days)
    low, mid, high = (max(0.0, g) * daily_driver for g in gaps)
    return round(low, 0), round(mid, 0), round(high, 0)


def diagnose(
    db: Session,
    *,
    inp: WCInputs,
    subject_name: str,
) -> list[Situation]:
    """Produce Recommendation situations for DSO, DPO, DIO plus ageing/concentration extras."""
    m = compute_metrics(inp)
    weights = load_weights(db, Module.WORKING_CAPITAL.value)
    revenue_per_day = inp.revenue_annual_usd / 365
    cogs_per_day = inp.cogs_annual_usd / 365

    situations: list[Situation] = []

    specs = [
        ("DSO", m.dso_days, revenue_per_day, "lower",
         "Reduce days-sales-outstanding through collections and credit-policy tightening.",
         _dso_action(m)),
        ("DPO", m.dpo_days, cogs_per_day, "higher",
         "Extend days-payable-outstanding where supplier relationship and procurement policy allow.",
         "Renegotiate terms on top-spend suppliers; avoid early-pay unless discount justifies it."),
        ("DIO", m.dio_days, cogs_per_day, "lower",
         "Reduce inventory days through SKU rationalisation and demand-led replenishment.",
         "Target obsolete/slow SKUs for clearance; review safety-stock policy by category."),
    ]

    for metric, subject, driver, direction, title_suffix, action in specs:
        p40, p50, p60, n_peers = get_or_fallback_benchmark(db, inp.sector, metric)
        low, mid, high = cash_opportunity(subject, p40, p50, p60, driver, direction)

        # Evidence: one per metric input (client scope) + one for benchmark (public scope)
        ev_input = upsert_evidence(
            db,
            source_id="upload.file",
            scope=DataScope.CLIENT,
            mode=SourceMode.LIVE,
            kind=f"wc_metric_{metric.lower()}",
            title=f"{subject_name} {metric} = {subject:.1f} days",
            snippet=f"{metric} computed from uploaded AR/AP/inventory",
            meta={
                "metric": metric, "value_days": subject,
                "ar_aging": m.ar_aging if metric == "DSO" else None,
                "top5_concentration": m.customer_concentration_top5 if metric == "DSO"
                else m.supplier_concentration_top5 if metric == "DPO" else None,
            },
        )
        ev_bench = upsert_evidence(
            db,
            source_id="benchmark.internal",
            scope=DataScope.PUBLIC,
            mode=SourceMode.FIXTURE if n_peers == 0 else SourceMode.LIVE,
            kind="benchmark",
            title=f"{inp.sector} {metric} benchmark (n={n_peers})",
            snippet=f"p40={p40:.1f} p50={p50:.1f} p60={p60:.1f} days",
            meta={"p40": p40, "p50": p50, "p60": p60, "n": n_peers},
        )

        # Dimensions
        gap = (subject - p50) if direction == "lower" else (p50 - subject)
        unlock_ratio = min(1.0, max(0.0, mid / (inp.revenue_annual_usd * 0.05 + 1)))
        dims = {
            "cash_unlock_potential": unlock_ratio,
            "ease_of_action": _ease(metric, m),
            "operational_risk": _op_risk(metric, m),
            "confidence": 0.4 if n_peers == 0 else 0.8,
            "implementation_priority": min(1.0, unlock_ratio + 0.2),
        }
        bundle = compose(dims, weights, dims["confidence"])

        explanation, cites = generate_explanation(
            db,
            title=f"Working capital opportunity: {metric}",
            dimensions=dims,
            evidence_ids=[ev_input.id, ev_bench.id],
        )

        situation = Situation(
            module=Module.WORKING_CAPITAL.value,
            kind="company",
            title=f"WC opportunity — {metric}: {title_suffix}",
            summary=(
                f"{metric}={subject:.1f} days vs peer p50={p50:.1f}. "
                f"Cash unlock band: ${low:,.0f} / ${mid:,.0f} / ${high:,.0f}."
            ),
            next_action=action,
            caveats=_wc_caveats(metric, m, n_peers),
            dimensions=bundle.dimensions,
            weights=bundle.weights,
            confidence=bundle.confidence,
            score=bundle.score,
            signal_ids=[],
            evidence_ids=[ev_input.id, ev_bench.id],
            explanation=explanation,
            explanation_cites=cites,
            extras={
                "metric": metric,
                "subject_days": subject,
                "peer_p40": p40, "peer_p50": p50, "peer_p60": p60,
                "peer_n": n_peers,
                "unlock_low_usd": low,
                "unlock_mid_usd": mid,
                "unlock_high_usd": high,
                "ar_aging": m.ar_aging if metric == "DSO" else None,
                "customer_concentration_top5": m.customer_concentration_top5 if metric == "DSO" else None,
                "supplier_concentration_top5": m.supplier_concentration_top5 if metric == "DPO" else None,
                "sector": inp.sector,
            },
            review_state=ReviewState.PENDING.value,
        )
        db.add(situation)
        db.flush()
        situations.append(situation)

        # Persist KPI rows for dashboard trending
        kpi = KPI(
            module=Module.WORKING_CAPITAL.value,
            name=f"{subject_name} {metric}",
            unit="days",
            curve="linear",
            target_band_low=p40, target_band_mid=p50, target_band_high=p60,
            meta={"subject": subject_name, "metric": metric, "sector": inp.sector},
        )
        db.add(kpi)
        db.flush()
        db.add(KPIActual(kpi_id=kpi.id, ts=inp.as_of, value=subject))

    db.commit()
    return situations


def _ease(metric: str, m: WCMetrics) -> float:
    # Higher concentration → easier: fewer counterparties to act on
    if metric == "DSO":
        return min(1.0, 0.3 + m.customer_concentration_top5)
    if metric == "DPO":
        return min(1.0, 0.3 + m.supplier_concentration_top5)
    # DIO: depends on ageing not available here
    return 0.5


def _op_risk(metric: str, m: WCMetrics) -> float:
    # Higher aging skew -> higher risk attached to DSO action
    if metric == "DSO":
        total = sum(m.ar_aging.values()) or 1.0
        skew = (m.ar_aging.get("90+", 0) + m.ar_aging.get("61-90", 0)) / total
        return round(skew, 3)
    return 0.3


def _dso_action(m: WCMetrics) -> str:
    if m.customer_concentration_top5 > 0.4:
        return "Prioritise top-5 customers for collections calls and term reviews."
    return "Launch aging-bucket collections sprint targeting the 61-90 and 90+ buckets."


def _wc_caveats(metric: str, m: WCMetrics, n_peers: int) -> list[str]:
    out: list[str] = []
    if n_peers == 0:
        out.append("Peer benchmark uses fallback defaults; precision limited.")
    if metric == "DSO" and m.customer_concentration_top5 < 0.15:
        out.append("Customer base is highly fragmented; actions distributed.")
    if metric == "DPO" and m.supplier_concentration_top5 < 0.15:
        out.append("Supplier base is highly fragmented; actions distributed.")
    return out
