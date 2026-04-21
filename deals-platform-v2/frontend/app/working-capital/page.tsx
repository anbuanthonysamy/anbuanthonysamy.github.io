"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DataProvenance } from "@/components/DataProvenance";
import { SituationCard } from "@/components/SituationCard";
import { SituationDetail } from "@/components/SituationDetail";
import type { SituationOut } from "@/lib/types";
import { money } from "@/lib/format";

function MetricCards({ items }: { items: SituationOut[] }) {
  if (!items.length) return null;
  const byKind: Record<string, SituationOut | undefined> = {};
  for (const s of items) {
    const k = (s.extras as Record<string, unknown>)?.metric as string | undefined;
    if (k && !byKind[k]) byKind[k] = s;
  }
  const keys = ["DSO", "DPO", "DIO"];
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {keys.map((k) => {
        const s = byKind[k];
        if (!s) {
          return (
            <div key={k} className="panel p-3">
              <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">{k}</div>
              <div className="text-neutral-dark-tertiary text-sm mt-2">No diagnostic yet.</div>
            </div>
          );
        }
        const e = s.extras as Record<string, number | string>;
        const value = e.subject_days as number | undefined;
        const benchmark = e.peer_p50 as number | undefined;
        const mid = e.unlock_mid_usd as number | undefined;
        return (
          <div key={k} className="panel p-3">
            <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">{k}</div>
            <div className="text-2xl font-semibold mt-1">
              {value !== undefined ? value.toFixed(1) : "—"}
              <span className="text-xs text-neutral-dark-tertiary ml-1">days</span>
            </div>
            <div className="text-xs text-neutral-dark-tertiary">
              peer median{" "}
              {benchmark !== undefined ? `${benchmark.toFixed(1)}d` : "—"}
            </div>
            <div className="text-xs mt-1">
              cash opportunity (mid): <span className="font-medium">{money(mid)}</span>
            </div>
          </div>
        );
      })}
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
      const list = await api.situations({ module: "working_capital", limit: 100 });
      setItems(list);
      if (list.length && !selected) setSelected(list[0]);
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
          <h1 className="text-xl font-semibold text-neutral-white">CS4 — Working Capital Diagnostic</h1>
          <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
            DSO / DPO / DIO from uploaded AR/AP/inventory vs XBRL peer benchmarks.
            Cash-opportunity bands computed from p60 / p50 / p40 peer quantiles.
            Horizon 3–9 months.
          </p>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}
      <DataProvenance module="working_capital" items={items} />
      <MetricCards items={items} />
      <div className="panel p-3 text-xs text-neutral-dark-tertiary">
        To run a new diagnostic, POST multipart to <code>/working-capital/diagnose</code> with
        AR, AP, and inventory files plus revenue + COGS. The demo seed produces a pre-computed
        diagnostic.
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="text-sm font-semibold text-neutral-white">Diagnostics ({items.length})</div>
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
