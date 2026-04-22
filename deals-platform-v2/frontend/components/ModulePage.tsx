"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SectorHeatCell, SituationV2 } from "@/lib/types";
import { Heatmap } from "./Heatmap";
import { SituationCardV2 } from "./SituationCardV2";
import { SituationDetailV2 } from "./SituationDetailV2";
import { SourceStatusPanel } from "./SourceStatusPanel";

function normalizeModuleForApi(module: string): string {
  // Frontend uses hyphenated names like "carve-outs", backend expects "carve_outs"
  if (module === "carve-outs") return "carve_outs";
  if (module === "post-deal") return "post_deal";
  if (module === "working-capital") return "working_capital";
  return module;
}

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
  const [items, setItems] = useState<SituationV2[]>([]);
  const [heat, setHeat] = useState<SectorHeatCell[]>([]);
  const [selected, setSelected] = useState<SituationV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"live" | "offline">("offline");
  const [scanning, setScanning] = useState(false);

  const apiModule = normalizeModuleForApi(module);
  const isScanModule = apiModule === "origination" || apiModule === "carve_outs";

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      const [result, h, modeStatus] = await Promise.all([
        api.situationsV2({ module: apiModule, sort_by: "score" }),
        showHeatmap ? api.heatmap(module).catch(() => []) : Promise.resolve<SectorHeatCell[]>([]),
        api.getMode().catch(() => ({ effective_mode: "offline" as const })),
      ]);
      const list = result.situations || [];
      setItems(list);
      setHeat(h);
      setMode(modeStatus.effective_mode);
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
  }, [module]);

  const handleScan = async () => {
    setScanning(true);
    setErr(null);
    try {
      await api.triggerScan(mode, "worldwide");
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-neutral-white">{title}</h1>
          <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold px-2 py-1 rounded border ${
              mode === "live"
                ? "bg-data-green/20 border-data-green text-data-green"
                : "bg-neutral-dark-secondary border-neutral-dark-tertiary text-neutral-light-tertiary"
            }`}
          >
            {mode === "live" ? "📡 Live" : "📶 Offline (demo)"}
          </span>
          {isScanModule && (
            <button className="btn" onClick={handleScan} disabled={scanning || loading}>
              {scanning ? "Scanning…" : "Run scan"}
            </button>
          )}
          <button className="btn" onClick={load} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      {isScanModule && <SourceStatusPanel module={apiModule} />}

      {aboveList}

      {showHeatmap && heat.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-neutral-white mb-2">Sector heatmap</div>
          <Heatmap cells={heat} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div>
            <div className="text-sm font-semibold text-neutral-white">
              Ranked situations ({items.length})
            </div>
            <div className="text-xs text-neutral-dark-tertiary mt-1">
              {isScanModule
                ? "Top 15 ranked by score, tiebreaker: deal value. Country flags indicate data source (🇺🇸 S&P 500, 🇬🇧 FTSE 100)."
                : "All opportunities ranked by score."}
            </div>
          </div>
          {items.length === 0 && !loading && (
            <div className="panel p-3 text-sm text-neutral-dark-tertiary">
              {isScanModule
                ? "No situations yet. Click 'Run scan' above to start the continuous market scanner."
                : "No situations yet. Upload data via the relevant endpoint to populate."}
            </div>
          )}
          {items.map((s) => (
            <SituationCardV2
              key={s.id}
              situation={s}
              active={selected?.id === s.id}
              onSelect={setSelected}
            />
          ))}
        </div>
        <div className="lg:col-span-3">
          {selected ? (
            <SituationDetailV2 situation={selected} />
          ) : (
            <div className="panel p-4 text-sm text-neutral-dark-tertiary">
              Select a situation from the list to see details, signals, and generate an explanation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
