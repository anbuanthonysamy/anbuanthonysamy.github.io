"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BandChart } from "@/components/BandChart";
import { ModulePage } from "@/components/ModulePage";

type KpiRow = Awaited<ReturnType<typeof api.postDealKpis>>[number];

function Bands() {
  const [rows, setRows] = useState<KpiRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    setErr(null);
    try {
      setRows(await api.postDealKpis());
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "load failed");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const recompute = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.postDealCompute();
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "compute failed");
    } finally {
      setBusy(false);
    }
  };

  if (err) {
    return <div className="panel p-3 text-sm text-status-risk">{err}</div>;
  }
  if (!rows.length) {
    return (
      <div className="panel p-3 text-sm text-ink-muted">
        No KPIs yet. Upload a deal case JSON via <code>POST /post-deal/upload/deal-case</code>.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <div className="text-sm font-semibold">KPI trend bands vs actuals</div>
        <button className="btn" onClick={recompute} disabled={busy}>
          {busy ? "Computing…" : "Recompute deviations"}
        </button>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {rows.map((k) => {
          const mids = new Map(
            k.target_curve.map(([ts, , mid]) => [ts, mid] as const),
          );
          const lows = new Map(
            k.target_curve.map(([ts, low]) => [ts, low] as const),
          );
          const highs = new Map(
            k.target_curve.map(([ts, , , high]) => [ts, high] as const),
          );
          const points = k.actuals.map(([ts, value], i) => ({
            x: i,
            plan: mids.get(ts) ?? value,
            low: lows.get(ts) ?? value,
            high: highs.get(ts) ?? value,
            actual: value,
          }));
          return (
            <BandChart
              key={k.id}
              title={`${k.name} (${k.curve})`}
              unit={k.unit}
              points={points}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <ModulePage
      module="post_deal"
      title="CS3 — Post-Deal Value Creation Tracker"
      subtitle="Uploaded deal cases with trend-shaped target bands (linear / S-curve / J-curve). Deviations are flagged after two consecutive out-of-band observations."
      showHeatmap={false}
      aboveList={<Bands />}
    />
  );
}
