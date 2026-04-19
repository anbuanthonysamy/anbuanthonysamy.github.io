"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { WeightsResponse } from "@/lib/types";

const MODULES = ["origination", "carve_outs", "post_deal", "working_capital"];

function WeightsEditor({ module }: { module: string }) {
  const [data, setData] = useState<WeightsResponse | null>(null);
  const [edit, setEdit] = useState<Record<string, number>>({});
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = async () => {
    setErr(null);
    setSaved(false);
    try {
      const w = await api.weights(module);
      setData(w);
      setEdit({ ...w.weights });
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "load failed");
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module]);

  const save = async () => {
    setErr(null);
    try {
      const w = await api.setWeights(module, edit);
      setData(w);
      setEdit({ ...w.weights });
      setSaved(true);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "save failed");
    }
  };

  const reset = () => {
    if (!data) return;
    setEdit({ ...data.defaults });
  };

  if (!data) {
    return <div className="panel p-3 text-sm text-ink-muted">Loading {module}…</div>;
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold">{module.replace("_", "-")}</div>
        <div className="text-xs text-ink-muted">
          defaults editable; sum is normalised at scoring time
        </div>
      </div>
      {err && <div className="text-sm text-status-risk mb-2">{err}</div>}
      {saved && <div className="text-sm text-status-ok mb-2">Saved.</div>}
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="th">Dimension</th>
            <th className="th text-right">Default</th>
            <th className="th text-right">Current</th>
            <th className="th text-right">New</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(data.defaults).map((k) => (
            <tr key={k}>
              <td className="td">{k}</td>
              <td className="td text-right text-ink-muted">
                {data.defaults[k].toFixed(2)}
              </td>
              <td className="td text-right">{data.weights[k]?.toFixed(2) ?? "—"}</td>
              <td className="td text-right">
                <input
                  type="number"
                  step="0.05"
                  min={0}
                  max={5}
                  className="w-20 border border-hairline rounded px-1 py-0.5 text-right"
                  value={edit[k] ?? 0}
                  onChange={(e) =>
                    setEdit((prev) => ({ ...prev, [k]: Number(e.target.value) }))
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-3">
        <button className="btn-primary" onClick={save}>
          Save
        </button>
        <button className="btn" onClick={reset}>
          Reset to defaults
        </button>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Settings — scoring weights</h1>
        <p className="text-sm text-ink-soft mt-1 max-w-2xl">
          Each module composes a score from named dimensions via a weighted sum,
          then dampens by confidence. Change weights here and rerun a module to see
          the effect. Defaults are from <code>scoring/engine.py</code>.
        </p>
      </div>
      <div className="space-y-4">
        {MODULES.map((m) => (
          <WeightsEditor key={m} module={m} />
        ))}
      </div>
    </div>
  );
}
