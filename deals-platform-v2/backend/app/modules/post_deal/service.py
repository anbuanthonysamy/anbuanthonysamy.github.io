"""CS3 — Post-deal value creation tracker.

Uploaded client data (deal case + actuals). Produces:
- KPI rows with target bands (curve-shaped)
- Deviation Situations where actuals exit the band for 2+ consecutive points
- Intervention-priority score per deviation
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.explain.explainer import generate_explanation
from app.models.enums import CurveShape, DataScope, Module, ReviewState, SourceMode
from app.models.orm import KPI, Evidence, KPIActual, Situation
from app.modules.post_deal.curves import BandPoint, compute_band, detect_deviation
from app.scoring.engine import compose, load_weights
from app.shared.evidence import upsert_evidence


@dataclass
class DealCaseInitiative:
    name: str
    unit: str
    curve: CurveShape
    start_value: float
    end_value: float
    start: dt.datetime
    end: dt.datetime
    tolerance: float = 0.10


def ingest_deal_case(db: Session, case: dict, upload_id: str) -> list[KPI]:
    """Persist KPIs + target envelopes from a deal-case upload."""
    kpis: list[KPI] = []
    for i in case.get("initiatives", []):
        curve = CurveShape(i.get("curve", "linear"))
        k = KPI(
            module=Module.POST_DEAL.value,
            name=i["name"],
            unit=i.get("unit", "USD"),
            curve=curve.value,
            target_band_low=float(i["start_value"]),
            target_band_mid=None,
            target_band_high=float(i["end_value"]),
            target_start=_parse_dt(i["start"]),
            target_end=_parse_dt(i["end"]),
            meta={"upload_id": upload_id, "tolerance": i.get("tolerance", 0.10)},
        )
        db.add(k)
        db.flush()
        kpis.append(k)
    return kpis


def ingest_actuals(db: Session, kpi_name: str, rows: list[dict]) -> int:
    kpi = db.scalar(
        select(KPI).where(KPI.module == Module.POST_DEAL.value).where(KPI.name == kpi_name)
    )
    if kpi is None:
        return 0
    n = 0
    for r in rows:
        ts = _parse_dt(r["ts"])
        if ts is None:
            continue
        db.add(KPIActual(kpi_id=kpi.id, ts=ts, value=float(r["value"])))
        n += 1
    return n


def compute_deviations(db: Session) -> list[Situation]:
    """Run deviation detection across all CS3 KPIs and create Situations."""
    out: list[Situation] = []
    weights = load_weights(db, Module.POST_DEAL.value)

    kpis = db.scalars(select(KPI).where(KPI.module == Module.POST_DEAL.value)).all()
    for kpi in kpis:
        actuals = db.scalars(
            select(KPIActual).where(KPIActual.kpi_id == kpi.id).order_by(KPIActual.ts.asc())
        ).all()
        if not actuals:
            continue

        ts_list = [a.ts for a in actuals]
        band: list[BandPoint] = compute_band(
            shape=CurveShape(kpi.curve),
            start_value=float(kpi.target_band_low or 0),
            end_value=float(kpi.target_band_high or 0),
            start=kpi.target_start or ts_list[0],
            end=kpi.target_end or ts_list[-1],
            timestamps=ts_list,
            tolerance=float((kpi.meta or {}).get("tolerance", 0.10)),
        )

        # Consecutive out-of-band count
        run = 0
        last_state = "in_band"
        worst_actual = None
        worst_point = None
        for a, p in zip(actuals, band):
            state = detect_deviation(a.value, p)
            if state != "in_band":
                run += 1
                if worst_actual is None or abs(a.value - p.mid) > abs(worst_actual - worst_point.mid):
                    worst_actual, worst_point = a.value, p
                last_state = state
            else:
                run = 0
                worst_actual, worst_point = None, None

            if run >= 2 and worst_actual is not None:
                dev_pct = (worst_actual - worst_point.mid) / (worst_point.mid or 1)
                # Create evidence row that ties this deviation to a client-scope source
                ev = upsert_evidence(
                    db,
                    source_id="upload.file",
                    scope=DataScope.CLIENT,
                    mode=SourceMode.LIVE,
                    kind="kpi_actual",
                    title=f"{kpi.name} actual {a.value:.2f} vs mid {worst_point.mid:.2f} ({last_state})",
                    snippet=f"deviation={dev_pct:.2%} at {a.ts.date()}",
                    published_at=a.ts,
                    meta={"kpi_id": kpi.id, "value": a.value, "mid": worst_point.mid},
                )

                # Dimensions
                dims = {
                    "value_at_risk": min(1.0, abs(dev_pct)),
                    "urgency": 0.6 if run >= 3 else 0.4,
                    "business_impact": min(1.0, abs(dev_pct) * 0.8),
                    "confidence": 0.7,
                    "intervention_priority": min(1.0, abs(dev_pct) + 0.2),
                }
                bundle = compose(dims, weights, dims["confidence"])

                title = f"Post-deal deviation: {kpi.name} {last_state.replace('_', ' ')}"
                try:
                    explanation, cites = generate_explanation(
                        db,
                        title=title,
                        dimensions=dims,
                        evidence_ids=[ev.id],
                    )
                except Exception:
                    explanation, cites = None, []

                sit = Situation(
                    module=Module.POST_DEAL.value,
                    kind="company",
                    title=title,
                    summary=f"{kpi.name} has been {last_state.replace('_', ' ')} for {run} consecutive observations.",
                    next_action=_intervention_hint(last_state, kpi.name),
                    caveats=_caveats(last_state, dev_pct),
                    dimensions=bundle.dimensions,
                    weights=bundle.weights,
                    confidence=bundle.confidence,
                    score=bundle.score,
                    signal_ids=[],
                    evidence_ids=[ev.id],
                    explanation=explanation,
                    explanation_cites=cites,
                    extras={
                        "kpi_id": kpi.id,
                        "kpi_name": kpi.name,
                        "unit": kpi.unit,
                        "deviation_pct": dev_pct,
                        "run_length": run,
                        "state": last_state,
                        "curve": kpi.curve,
                    },
                    review_state=ReviewState.PENDING.value,
                )
                db.add(sit)
                db.flush()
                out.append(sit)
                # Avoid duplicate flags for the same continuing deviation
                run = 0
                worst_actual, worst_point = None, None

    db.commit()
    return out


def _intervention_hint(state: str, kpi_name: str) -> str:
    if state == "below_band":
        return f"Escalate {kpi_name} to programme lead; review mitigation options and re-baseline if needed."
    if state == "above_band":
        return f"Validate {kpi_name} overperformance — is it sustainable, or masking risk elsewhere?"
    return "Continue monitoring."


def _caveats(state: str, dev_pct: float) -> list[str]:
    caveats = []
    if state == "above_band" and dev_pct > 0.25:
        caveats.append("Large overperformance may mask underinvestment or pull-forward.")
    if abs(dev_pct) < 0.05:
        caveats.append("Deviation is marginal; may be within measurement noise.")
    return caveats


def band_view(db: Session, kpi_id: str) -> dict:
    kpi = db.get(KPI, kpi_id)
    if kpi is None:
        return {}
    actuals = db.scalars(
        select(KPIActual).where(KPIActual.kpi_id == kpi.id).order_by(KPIActual.ts.asc())
    ).all()
    ts_list = [a.ts for a in actuals] or []
    band = compute_band(
        shape=CurveShape(kpi.curve),
        start_value=float(kpi.target_band_low or 0),
        end_value=float(kpi.target_band_high or 0),
        start=kpi.target_start or (ts_list[0] if ts_list else dt.datetime.now(dt.timezone.utc)),
        end=kpi.target_end or (ts_list[-1] if ts_list else dt.datetime.now(dt.timezone.utc)),
        timestamps=ts_list,
        tolerance=float((kpi.meta or {}).get("tolerance", 0.10)),
    )
    return {
        "kpi": {
            "id": kpi.id, "name": kpi.name, "unit": kpi.unit, "curve": kpi.curve,
            "target_start": kpi.target_start, "target_end": kpi.target_end,
            "start_value": kpi.target_band_low, "end_value": kpi.target_band_high,
        },
        "actuals": [{"ts": a.ts, "value": a.value} for a in actuals],
        "band": [{"ts": p.ts, "low": p.low, "mid": p.mid, "high": p.high} for p in band],
    }


def _parse_dt(s: str | dt.datetime | None) -> dt.datetime | None:
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s if s.tzinfo else s.replace(tzinfo=dt.timezone.utc)
    if isinstance(s, dt.date):
        return dt.datetime.combine(s, dt.time.min, tzinfo=dt.timezone.utc)
    try:
        out = pd.to_datetime(s, utc=True).to_pydatetime()
        return out
    except Exception:
        return None
