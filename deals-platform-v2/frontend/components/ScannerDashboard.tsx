"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SituationV2 } from "@/lib/types";
import { ScannerPanel } from "./ScannerPanel";
import { SituationCardV2 } from "./SituationCardV2";
import { SituationDetailV2 } from "./SituationDetailV2";

export function ScannerDashboard() {
  const [situations, setSituations] = useState<SituationV2[]>([]);
  const [selected, setSelected] = useState<SituationV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [module, setModule] = useState<string | undefined>(undefined);
  const [tier, setTier] = useState<string | undefined>(undefined);
  const [sortBy, setSortBy] = useState<"priority" | "value" | "score" | "recency">("priority");

  const loadSituations = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.situationsV2({
        module,
        tier,
        sort_by: sortBy,
        limit: 100,
      });
      setSituations(result.situations || []);
      if (result.situations && result.situations.length > 0 && !selected) {
        setSelected(result.situations[0]);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load situations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSituations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module, tier, sortBy]);

  const filteredCount = situations.length;

  return (
    <div className="space-y-4">
      <ScannerPanel />

      <div className="grid grid-cols-1 gap-4">
        {/* Filters */}
        <div className="panel p-4 space-y-3">
          <div className="text-sm font-semibold text-neutral-white">Filters & Sorting</div>
          <div className="flex flex-wrap gap-2">
            {/* Module Filter */}
            <select
              value={module || ""}
              onChange={(e) => setModule(e.target.value || undefined)}
              className="bg-neutral-dark-secondary text-neutral-white text-sm rounded px-2 py-1 border border-neutral-dark-secondary outline-none cursor-pointer"
            >
              <option value="">All Modules</option>
              <option value="origination">CS1 Origination</option>
              <option value="carve_outs">CS2 Carve-outs</option>
              <option value="post_deal">CS3 Post-Deal</option>
              <option value="working_capital">CS4 Working Capital</option>
            </select>

            {/* Tier Filter */}
            <select
              value={tier || ""}
              onChange={(e) => setTier(e.target.value || undefined)}
              className="bg-neutral-dark-secondary text-neutral-white text-sm rounded px-2 py-1 border border-neutral-dark-secondary outline-none cursor-pointer"
            >
              <option value="">All Tiers</option>
              <option value="p1">P1 (Hot/Ready/At-Risk/Quick Win)</option>
              <option value="p2">P2 (Target/Candidate/On-Track/Solid)</option>
              <option value="p3">P3 (Monitor)</option>
            </select>

            {/* Sort By */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-neutral-dark-secondary text-neutral-white text-sm rounded px-2 py-1 border border-neutral-dark-secondary outline-none cursor-pointer"
            >
              <option value="priority">Priority</option>
              <option value="score">Score</option>
              <option value="recency">Recency</option>
            </select>

            <button
              onClick={loadSituations}
              disabled={loading}
              className="btn text-sm px-3 py-1 disabled:opacity-50"
            >
              {loading ? "Loading…" : "Refresh List"}
            </button>
          </div>
        </div>

        {error && (
          <div className="panel p-3 bg-data-red/10 border border-data-red">
            <p className="text-sm text-data-red">{error}</p>
          </div>
        )}

        {/* List & Detail */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Situations List */}
          <div className="lg:col-span-1 space-y-2">
            <div className="panel p-3 bg-neutral-dark-secondary">
              <h3 className="text-sm font-semibold text-neutral-white">
                Situations ({filteredCount})
              </h3>
              <p className="text-xs text-neutral-light-tertiary mt-1">
                {module || "All modules"} • Sort by {sortBy}
              </p>
            </div>

            {situations.length === 0 && !loading && (
              <div className="panel p-3 text-sm text-neutral-dark-tertiary">
                No situations match your filters. Try adjusting the selection or running a scan.
              </div>
            )}

            <div className="space-y-2 max-h-96 overflow-y-auto">
              {situations.map((s) => (
                <SituationCardV2
                  key={s.id}
                  situation={s}
                  active={selected?.id === s.id}
                  onSelect={setSelected}
                />
              ))}
            </div>
          </div>

          {/* Detail View */}
          <div className="lg:col-span-2">
            {selected ? (
              <SituationDetailV2 situation={selected} />
            ) : (
              <div className="panel p-4 h-full flex items-center justify-center">
                <p className="text-neutral-dark-tertiary text-sm">
                  Select a situation to view details
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
