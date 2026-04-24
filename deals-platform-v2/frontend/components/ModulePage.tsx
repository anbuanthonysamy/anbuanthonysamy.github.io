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
  const [scanning, setScanning] = useState(false);

  const apiModule = normalizeModuleForApi(module);
  const isScanModule = apiModule === "origination" || apiModule === "carve_outs";

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      let list: SituationV2[] = [];
      let h: SectorHeatCell[] = [];

      // CS1/CS2 use v2 scanner endpoint; CS3/CS4 use v1 endpoint
      if (isScanModule) {
        const result = await api.situationsV2({ module: apiModule, sort_by: "score" });
        list = result.situations || [];
      } else {
        const v1Situations = await api.situations({ module: apiModule, limit: 100 });
        // Convert v1 SituationOut to v2 display format
        list = v1Situations.map(s => ({
          id: s.id,
          module: s.module,
          company_id: s.company_id,
          company: undefined, // v1 doesn't have company object; would need separate fetch
          tier: "p3",
          tier_colour: "green" as const,
          score: s.score,
          score_delta: 0,
          signals: {},
          first_seen_at: null,
          last_updated_at: null,
          explanation: s.explanation || null,
          caveats: s.caveats || [],
        })) as SituationV2[];
      }

      if (showHeatmap) {
        h = await api.heatmap(module).catch(() => []);
      }

      setItems(list);
      setHeat(h);
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
      await api.triggerScan("live", "worldwide");
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
          {isScanModule && (
            <button
              className="btn-primary"
              onClick={handleScan}
              disabled={scanning || loading}
              title="Trigger a fresh scan of the company universe; re-fetches EDGAR, market, news, Companies House data and recomputes signals."
            >
              {scanning ? "Scanning…" : "Run scan"}
            </button>
          )}
          <button
            className="btn text-xs"
            onClick={load}
            disabled={loading}
            title="Re-render the list from the database (no external API calls)."
          >
            {loading ? "Loading…" : "↻ Reload list"}
          </button>
        </div>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      {isScanModule && <SourceStatusPanel module={apiModule} />}

      {isScanModule && (
        <div className="panel p-4 bg-neutral-dark-secondary/50">
          <div className="text-sm font-semibold text-neutral-white mb-2">Priority tiers</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="flex items-start gap-2">
              <span className="inline-block w-3 h-3 rounded-full bg-data-red shrink-0 mt-0.5"></span>
              <div>
                <span className="font-semibold text-neutral-white">P1 Hot</span>
                <p className="text-neutral-dark-tertiary">Urgent catalyst present; recommend immediate action.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="inline-block w-3 h-3 rounded-full bg-data-yellow shrink-0 mt-0.5"></span>
              <div>
                <span className="font-semibold text-neutral-white">P2 Monitor</span>
                <p className="text-neutral-dark-tertiary">Material signals; monitor for catalysts or escalation.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="inline-block w-3 h-3 rounded-full bg-status-ok shrink-0 mt-0.5"></span>
              <div>
                <span className="font-semibold text-neutral-white">P3 Monitor</span>
                <p className="text-neutral-dark-tertiary">Early-stage signals; longer horizon, no immediate catalyst.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {aboveList}

      {showHeatmap && heat.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-neutral-white mb-2">Sector heatmap</div>
          <Heatmap cells={heat} />
        </div>
      )}

      <div className="panel p-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs border border-neutral-dark-secondary">
        <div>
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Score</span>
          <span className="ml-2 text-neutral-white font-medium">0–1 scale</span>
          <span className="ml-2 text-neutral-dark-tertiary">· higher = stronger opportunity</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-data-red inline-block"></span><span className="text-neutral-light-tertiary">&ge; 0.6 high</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-data-yellow inline-block"></span><span className="text-neutral-light-tertiary">0.4–0.6 medium</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-status-ok inline-block"></span><span className="text-neutral-light-tertiary">&lt; 0.4 low</span></span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div>
            <div className="text-sm font-semibold text-neutral-white">
              Ranked situations ({items.length})
            </div>
            <div className="text-xs text-neutral-dark-tertiary mt-1">
              {isScanModule
                ? "Ranked by score (0–1). Country flags: 🇺🇸 S&P 500, 🇬🇧 FTSE 100."
                : "Ranked by score (0–1). Higher score = stronger opportunity."}
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
