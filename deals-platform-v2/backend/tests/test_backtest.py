import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.backtest import run_backtest  # noqa: E402


def test_backtest_runs_and_meets_tolerance():
    r = run_backtest()
    assert set(r.keys()) == {"ma", "carveout"}
    # Documented tolerance for this proxy dataset — any drift here flags a
    # regression in the fixtures or scoring proxy.
    assert r["ma"]["precision_at_top_n"] >= 0.80
    assert r["carveout"]["precision_at_top_n"] >= 0.80
    assert r["ma"]["n"] == 10
    assert r["carveout"]["n"] == 10
