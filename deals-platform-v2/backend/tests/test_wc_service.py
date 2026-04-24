import datetime as dt

import pandas as pd

from app.modules.working_capital.service import WCInputs, cash_opportunity, compute_metrics


def _ar_df():
    return pd.DataFrame([
        {"customer_id": "A", "invoice_id": "1", "amount_usd": 1000.0,
         "invoice_date": pd.Timestamp("2024-05-01", tz="UTC"),
         "due_date": pd.Timestamp("2024-06-15", tz="UTC"), "paid_date": pd.NaT},
        {"customer_id": "A", "invoice_id": "2", "amount_usd": 500.0,
         "invoice_date": pd.Timestamp("2024-01-05", tz="UTC"),
         "due_date": pd.Timestamp("2024-02-20", tz="UTC"), "paid_date": pd.NaT},
        {"customer_id": "B", "invoice_id": "3", "amount_usd": 200.0,
         "invoice_date": pd.Timestamp("2024-04-10", tz="UTC"),
         "due_date": pd.Timestamp("2024-05-25", tz="UTC"),
         "paid_date": pd.Timestamp("2024-05-20", tz="UTC")},
    ])


def _ap_df():
    return pd.DataFrame([
        {"supplier_id": "S1", "invoice_id": "b1", "amount_usd": 400.0,
         "invoice_date": pd.Timestamp("2024-05-01", tz="UTC"),
         "due_date": pd.Timestamp("2024-06-15", tz="UTC"), "paid_date": pd.NaT},
    ])


def _inv():
    return pd.DataFrame([{"sku": "S1", "value_usd": 1000.0, "days_held": 60}])


def test_metrics_basic():
    inp = WCInputs(
        revenue_annual_usd=10_000.0,
        cogs_annual_usd=6_000.0,
        ar_df=_ar_df(),
        ap_df=_ap_df(),
        inv_df=_inv(),
        as_of=dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc),
        sector="Generic",
    )
    m = compute_metrics(inp)
    # AR outstanding = 1000 + 500 = 1500
    assert m.ar_outstanding_usd == 1500
    # DSO = 1500 / (10000/365) ~= 54.75
    assert 54 < m.dso_days < 56
    # Top-5 concentration on a 2-customer book is 1.0
    assert m.customer_concentration_top5 == 1.0


def test_cash_opportunity_lower_better():
    low, mid, high = cash_opportunity(
        subject_days=70, p40=40, p50=50, p60=60, daily_driver=100.0, direction="lower",
    )
    # Gaps: 70-60=10, 70-50=20, 70-40=30 -> 1000, 2000, 3000
    assert (low, mid, high) == (1000, 2000, 3000)


def test_cash_opportunity_higher_better_clamps_at_zero():
    low, mid, high = cash_opportunity(
        subject_days=60, p40=40, p50=50, p60=60, daily_driver=100.0, direction="higher",
    )
    # Gaps: 40-60=-20, 50-60=-10, 60-60=0 -> clamped to 0
    assert (low, mid, high) == (0, 0, 0)
