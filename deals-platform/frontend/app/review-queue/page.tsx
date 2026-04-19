"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SituationOut } from "@/lib/types";
import { SituationCard } from "@/components/SituationCard";
import { SituationDetail } from "@/components/SituationDetail";

const STATES = ["pending", "accepted", "edited", "rejected", "approved"];
const MODULES = ["", "origination", "carve_outs", "post_deal", "working_capital"];

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
        <h1 className="text-xl font-semibold">Review queue</h1>
        <p className="text-sm text-ink-soft mt-1 max-w-2xl">
          All situations across modules. Nothing is approved without a reviewer, a
          reason, and at least one evidence row.
        </p>
      </div>

      <div className="flex gap-3 items-center text-sm">
        <label className="text-ink-muted">State</label>
        <select
          className="border border-hairline rounded px-2 py-1 bg-white"
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
        <label className="text-ink-muted ml-3">Module</label>
        <select
          className="border border-hairline rounded px-2 py-1 bg-white"
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

      {err && <div className="panel p-3 text-sm text-status-risk">{err}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-2">
          <div className="text-sm font-semibold">Queue ({items.length})</div>
          {items.length === 0 && (
            <div className="panel p-3 text-sm text-ink-muted">
              Nothing in queue for this filter.
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
