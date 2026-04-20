"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SituationOut } from "@/lib/types";
import { SituationCard } from "@/components/SituationCard";
import { SituationDetail } from "@/components/SituationDetail";

const STATES = ["pending", "accepted", "edited", "rejected", "approved"];
const MODULES = ["", "origination", "carve_outs", "post_deal", "working_capital"];
const MODULE_LABELS: Record<string, string> = {
  origination: "CS1 · Origination",
  carve_outs: "CS2 · Carve-Outs",
  post_deal: "CS3 · Post-Deal",
  working_capital: "CS4 · Working Capital",
};
const MODULE_ORDER = ["origination", "carve_outs", "post_deal", "working_capital"];

export default function Page() {
  const [state, setState] = useState("pending");
  const [module, setModule] = useState("");
  const [items, setItems] = useState<SituationOut[]>([]);
  const [selected, setSelected] = useState<SituationOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setErr(null);
    try {
      const list = await api.situations({
        state: state || undefined,
        module: module || undefined,
        limit: 200,
      });
      setItems(list);
      setSelected(list[0] ?? null);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "load failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, module]);

  const onUpdated = (u: SituationOut) => {
    setItems((prev) => prev.filter((s) => s.id !== u.id || s.review.state === state));
    setSelected(u);
  };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-neutral-white">Review queue</h1>
        <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
          All situations across modules. Nothing is approved without a reviewer, a
          reason, and at least one evidence row.
        </p>
      </div>

      <div className="flex gap-3 items-center text-sm">
        <label className="text-neutral-dark-tertiary">State</label>
        <select
          className="border border-neutral-dark-secondary rounded px-2 py-1 bg-neutral-dark-secondary text-neutral-white"
          value={state}
          onChange={(e) => setState(e.target.value)}
        >
          <option value="">any</option>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="text-neutral-dark-tertiary ml-3">Module</label>
        <select
          className="border border-neutral-dark-secondary rounded px-2 py-1 bg-neutral-dark-secondary text-neutral-white"
          value={module}
          onChange={(e) => setModule(e.target.value)}
        >
          {MODULES.map((m) => (
            <option key={m} value={m}>
              {m || "any"}
            </option>
          ))}
        </select>
        <button className="btn ml-auto" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="text-sm font-semibold text-neutral-white">Queue ({items.length})</div>
          {items.length === 0 && (
            <div className="panel p-3 text-sm text-neutral-dark-tertiary">
              Nothing in queue for this filter.
            </div>
          )}
          {module === ""
            ? MODULE_ORDER.map((m) => {
                const group = items.filter((s) => s.module === m);
                if (!group.length) return null;
                return (
                  <div key={m} className="space-y-2">
                    <div className="sticky top-0 z-10 bg-neutral-dark-bg py-1 flex items-center gap-2 border-b border-neutral-dark-secondary">
                      <span className="pill">{MODULE_LABELS[m] ?? m}</span>
                      <span className="text-xs text-neutral-dark-tertiary">
                        {group.length} item{group.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    {group.map((s) => (
                      <SituationCard
                        key={s.id}
                        s={s}
                        active={selected?.id === s.id}
                        onSelect={setSelected}
                      />
                    ))}
                  </div>
                );
              })
            : items.map((s) => (
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
