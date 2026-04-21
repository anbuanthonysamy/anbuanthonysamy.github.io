"""End-to-end demo runner.

Seeds fixtures, invokes all four module pipelines in-process, and prints
a summary. Intended to be run inside the backend container via:

    python -m scripts.demo

or via `make demo` on the host, which invokes it through docker compose.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db import session_scope  # noqa: E402
from app.models.orm import Situation  # noqa: E402
from app.modules.carve_outs.service import CarveOutConfig, run_for_all as run_carve  # noqa: E402
from app.modules.origination.service import OriginationConfig, run_for_all as run_orig  # noqa: E402
from app.modules.post_deal.service import (  # noqa: E402
    compute_deviations,
    ingest_actuals,
    ingest_deal_case,
)
from app.modules.working_capital.service import WCInputs, diagnose  # noqa: E402
from scripts import seed_demo, seed_synth  # noqa: E402


def _to_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ("invoice_date", "due_date", "paid_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def _summary(sits: list[Situation], label: str) -> None:
    if not sits:
        print(f"  {label}: 0 situations")
        return
    top = max(sits, key=lambda s: s.score)
    print(f"  {label}: {len(sits)} situations; top score {top.score:.2f} — {top.title}")


def run() -> None:
    print("== Deals Platform demo ==")
    print("1) Seeding public evidence (fixtures only)…")
    seed_demo.run()

    print("2) Generating synthetic CS3/CS4 data…")
    synth_dir = ROOT / "data" / "synth"
    synth_dir.mkdir(parents=True, exist_ok=True)
    sys.argv = ["seed_synth", "--subject", "SampleCo", "--sector", "Consumer",
                "--out", str(synth_dir)]
    seed_synth.main()

    with session_scope() as db:
        print("3) CS1 Origination pipeline…")
        runs = run_orig(db, OriginationConfig())
        _summary([r.situation for r in runs], "CS1 origination")

        print("4) CS2 Carve-outs pipeline…")
        runs = run_carve(db, CarveOutConfig())
        _summary([r.situation for r in runs], "CS2 carve-outs")

        print("5) CS3 Post-deal ingest + deviations…")
        case = json.loads((synth_dir / "deal_case.json").read_text())
        kpis = ingest_deal_case(db, case, upload_id=str(synth_dir / "deal_case.json"))
        actuals = json.loads((synth_dir / "actuals.json").read_text())
        for name, rows in actuals.items():
            ingest_actuals(db, name, rows)
        db.commit()
        sits = compute_deviations(db)
        _summary(sits, f"CS3 post-deal ({len(kpis)} KPIs)")

        print("6) CS4 Working capital diagnostic…")
        ar = _to_df(json.loads((synth_dir / "ar.json").read_text()))
        ap = _to_df(json.loads((synth_dir / "ap.json").read_text()))
        inv = pd.DataFrame(json.loads((synth_dir / "inventory.json").read_text()))
        sits = diagnose(
            db,
            inp=WCInputs(
                revenue_annual_usd=600_000_000,
                cogs_annual_usd=400_000_000,
                ar_df=ar, ap_df=ap, inv_df=inv,
                as_of=dt.datetime.now(dt.timezone.utc),
                sector="Consumer",
            ),
            subject_name="SampleCo",
        )
        _summary(sits, "CS4 working capital")

    print("\nDone. Open http://localhost:3000 to explore.")


if __name__ == "__main__":
    run()
