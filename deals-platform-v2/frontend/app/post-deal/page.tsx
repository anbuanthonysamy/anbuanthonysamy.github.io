"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { BandChart } from "@/components/BandChart";
import { SituationCard } from "@/components/SituationCard";
import { SituationDetail } from "@/components/SituationDetail";
import type { SituationOut } from "@/lib/types";

type KpiRow = Awaited<ReturnType<typeof api.postDealKpis>>[number];

function Bands({ onRecompute }: { onRecompute?: () => void }) {
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
      onRecompute?.();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "compute failed");
    } finally {
      setBusy(false);
    }
  };

  if (err) {
    return <div className="panel p-3 text-sm text-data-red">{err}</div>;
  }
  if (!rows.length) {
    return (
      <div className="panel p-3 text-sm text-neutral-dark-tertiary">
        No KPIs yet. Upload a deal case JSON via <code>POST /post-deal/upload/deal-case</code>.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <div className="text-sm font-semibold text-neutral-white">KPI trend bands vs actuals</div>
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
  const [items, setItems] = useState<SituationOut[]>([]);
  const [selected, setSelected] = useState<SituationOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      const list = await api.situations({ module: "post_deal", limit: 100 });
      setItems(list);
      if (list.length && !selected) setSelected(list[0]);
      if (list.length === 0) setSelected(null);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "load failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onUpdated = (u: SituationOut) => {
    setItems((prev) => prev.map((s) => (s.id === u.id ? u : s)));
    setSelected(u);
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-white">
            CS3 — Post-Deal Value Creation Tracker
          </h1>
          <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
            Uploaded deal cases with trend-shaped target bands (linear / S-curve / J-curve).
            Deviations are flagged after two consecutive out-of-band observations.
          </p>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "↻ Reload list"}
        </button>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      <Bands onRecompute={load} />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="text-sm font-semibold text-neutral-white">
            Ranked situations ({items.length})
          </div>
          <div className="text-xs text-neutral-dark-tertiary">
            All opportunities ranked by score.
          </div>
          {items.length === 0 && !loading && (
            <div className="panel p-3 text-sm text-neutral-dark-tertiary">
              No situations yet. Click &ldquo;Recompute deviations&rdquo; above to detect out-of-band KPIs.
            </div>
          )}
          {items.map((s) => (
            <SituationCard
              key={s.id}
              s={s}
              active={selected?.id === s.id}
              onSelect={setSelected}
            />
          ))}
        </div>
        <div className="lg:col-span-3">
          <SituationDetail s={selected} onChange={onUpdated} />
        </div>
      </div>
    </div>
  );
}
