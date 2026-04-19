"""Trend-band curves for post-deal KPIs.

Given a (start_value, end_value, start_date, end_date) pair and a curve
shape (linear, S-curve, J-curve), produces the expected mid-value and
±tolerance band at every point in between.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from app.models.enums import CurveShape


@dataclass
class BandPoint:
    ts: dt.datetime
    low: float
    mid: float
    high: float


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _frac(t: dt.datetime, t0: dt.datetime, t1: dt.datetime) -> float:
    t, t0, t1 = _aware(t), _aware(t0), _aware(t1)
    span = (t1 - t0).total_seconds()
    if span <= 0:
        return 1.0
    x = (t - t0).total_seconds() / span
    return max(0.0, min(1.0, x))


def _linear(x: float) -> float:
    return x


def _s_curve(x: float) -> float:
    # Logistic mapped to [0,1] on input [0,1]; k=10 => steep midpoint
    k = 10.0
    x0 = 0.5
    denom = 1 + math.exp(-k * (x - x0))
    y = 1 / denom
    # normalise so y(0)=0, y(1)=1
    y0 = 1 / (1 + math.exp(k * x0))
    y1 = 1 / (1 + math.exp(-k * (1 - x0)))
    return (y - y0) / (y1 - y0) if (y1 - y0) != 0 else x


def _j_curve(x: float) -> float:
    # Dip then recovery. dip at 0.3 down to -0.2 of final, back to 1 at x=1.
    if x < 0.3:
        # Smooth dip: from 0 -> -0.2
        return (-0.2) * (x / 0.3)
    # Recovery: from -0.2 at x=0.3 to 1 at x=1
    k = (x - 0.3) / 0.7
    return -0.2 + (1.2) * k


def curve_value(shape: CurveShape, x: float) -> float:
    if shape == CurveShape.LINEAR:
        return _linear(x)
    if shape == CurveShape.S_CURVE:
        return _s_curve(x)
    if shape == CurveShape.J_CURVE:
        return _j_curve(x)
    return _linear(x)


def compute_band(
    *,
    shape: CurveShape,
    start_value: float,
    end_value: float,
    start: dt.datetime,
    end: dt.datetime,
    timestamps: list[dt.datetime],
    tolerance: float = 0.10,
) -> list[BandPoint]:
    delta = end_value - start_value
    out: list[BandPoint] = []
    for t in timestamps:
        f = _frac(t, start, end)
        mid = start_value + delta * curve_value(shape, f)
        band = abs(mid) * tolerance + abs(delta) * 0.02  # small absolute floor
        out.append(BandPoint(ts=t, low=mid - band, mid=mid, high=mid + band))
    return out


def detect_deviation(actual: float, point: BandPoint) -> str:
    """Return one of 'in_band' | 'below_band' | 'above_band'."""
    if actual < point.low:
        return "below_band"
    if actual > point.high:
        return "above_band"
    return "in_band"
