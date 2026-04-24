import datetime as dt

from app.models.enums import CurveShape
from app.modules.post_deal.curves import compute_band, detect_deviation


def test_linear_midpoint():
    t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    t1 = dt.datetime(2024, 12, 31, tzinfo=dt.timezone.utc)
    mid = compute_band(
        shape=CurveShape.LINEAR,
        start_value=0, end_value=100,
        start=t0, end=t1,
        timestamps=[t0 + (t1 - t0) / 2],
        tolerance=0.1,
    )
    assert 48 < mid[0].mid < 52


def test_s_curve_is_flat_at_start_and_steep_midway():
    t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    t1 = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    pts = compute_band(
        shape=CurveShape.S_CURVE,
        start_value=0, end_value=100,
        start=t0, end=t1,
        timestamps=[
            t0 + dt.timedelta(days=30),
            t0 + dt.timedelta(days=183),
            t0 + dt.timedelta(days=335),
        ],
        tolerance=0.1,
    )
    early, mid, late = pts
    assert early.mid < mid.mid < late.mid
    # Early growth should be slower than middle growth for an S curve
    assert (mid.mid - early.mid) > (late.mid - mid.mid) * 0.9  # steep around the middle


def test_j_curve_dips_before_recovering():
    t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    t1 = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    pts = compute_band(
        shape=CurveShape.J_CURVE,
        start_value=0, end_value=100,
        start=t0, end=t1,
        timestamps=[t0 + dt.timedelta(days=50), t0 + dt.timedelta(days=300)],
        tolerance=0.1,
    )
    dip, recovered = pts
    assert dip.mid < 0
    assert recovered.mid > 50


def test_detect_deviation():
    t = dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc)
    band = compute_band(
        shape=CurveShape.LINEAR, start_value=0, end_value=100,
        start=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
        end=dt.datetime(2024, 12, 31, tzinfo=dt.timezone.utc),
        timestamps=[t], tolerance=0.1,
    )[0]
    assert detect_deviation(band.mid, band) == "in_band"
    assert detect_deviation(band.mid * 2, band) == "above_band"
    assert detect_deviation(-999, band) == "below_band"
