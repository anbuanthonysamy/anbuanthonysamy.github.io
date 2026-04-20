"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SectorHeatCell, SituationOut } from "@/lib/types";
import { Heatmap } from "./Heatmap";
import { SituationCard } from "./SituationCard";
import { SituationDetail } from "./SituationDetail";

export function ModulePage({
  module,
  title,
  subtitle,
  showHeatmap = true,
  aboveList,
}: {
  module: string;
  title: string;
  subtitle: string;
  showHeatmap?: boolean;
  aboveList?: React.ReactNode;
}) {
  const [items, setItems] = useState<SituationOut[]>([]);
  const [heat, setHeat] = useState<SectorHeatCell[]>([]);
  const [selected, setSelected] = useState<SituationOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      const [list, h] = await Promise.all([
        api.situations({ module, limit: 100 }),
        showHeatmap ? api.heatmap(module) : Promise.resolve<SectorHeatCell[]>([]),
      ]);
      setItems(list);
      setHeat(h);
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
  }, [module]);

  const onUpdated = (updated: SituationOut) => {
    setItems((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    setSelected(updated);
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-white">{title}</h1>
          <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">{subtitle}</p>
        </div>
        <button className="btn" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}
      {aboveList}
      {showHeatmap && (
        <div>
          <div className="text-sm font-semibold text-neutral-white mb-2">Sector heatmap</div>
          <Heatmap cells={heat} />
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="text-sm font-semibold text-neutral-white">
            Ranked situations ({items.length})
          </div>
          {items.length === 0 && !loading && (
            <div className="panel p-3 text-sm text-neutral-dark-tertiary">
              No situations yet. Run <code>make demo</code> to seed the database.
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
