"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { WeightsResponse } from "@/lib/types";

const MODULES = ["origination", "carve_outs", "post_deal", "working_capital"];

const EQUITY_THRESHOLDS = {
  origination: { name: "CS1 — Origination", min: 500_000_000, max: 10_000_000_000, default: 1_000_000_000 },
  carve_outs: { name: "CS2 — Carve-outs", min: 100_000_000, max: 5_000_000_000, default: 750_000_000 },
};

function EquityThresholdsEditor() {
  const [thresholds, setThresholds] = useState<Record<string, number>>(
    Object.keys(EQUITY_THRESHOLDS).reduce((acc, module) => {
      acc[module] = EQUITY_THRESHOLDS[module as keyof typeof EQUITY_THRESHOLDS].default;
      return acc;
    }, {} as Record<string, number>)
  );
  const [saved, setSaved] = useState(false);

  const save = async () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  function formatCurrency(value: number) {
    if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
    return `$${value}`;
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-neutral-white">Equity Value Thresholds</div>
        <div className="text-xs text-neutral-dark-tertiary">
          Minimum company size for each module
        </div>
      </div>
      {saved && <div className="text-sm text-status-ok mb-2">Settings applied locally.</div>}
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="th">Module</th>
            <th className="th text-right">Default</th>
            <th className="th text-right">Current</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(EQUITY_THRESHOLDS).map(([module, config]) => (
            <tr key={module}>
              <td className="td">{config.name}</td>
              <td className="td text-right text-neutral-dark-tertiary">{formatCurrency(config.default)}</td>
              <td className="td text-right">
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={config.min}
                    max={config.max}
                    step={50_000_000}
                    className="w-32"
                    value={thresholds[module]}
                    onChange={(e) => {
                      setThresholds((prev) => ({ ...prev, [module]: Number(e.target.value) }));
                      setSaved(false);
                    }}
                  />
                  <span className="w-20 text-right font-mono">{formatCurrency(thresholds[module])}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 mt-3">
        <button className="btn-primary" onClick={save}>
          Apply
        </button>
      </div>
      <p className="text-xs text-neutral-dark-tertiary mt-2">
        Note: These thresholds only affect display filtering and are applied locally in this session.
        To persist changes, update the backend equity value filters in the API.
      </p>
    </div>
  );
}

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
    return <div className="panel p-3 text-sm text-neutral-dark-tertiary">Loading {module}…</div>;
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-neutral-white">{module.replace("_", "-")}</div>
        <div className="text-xs text-neutral-dark-tertiary">
          defaults editable; sum is normalised at scoring time
        </div>
      </div>
      {err && <div className="text-sm text-data-red mb-2">{err}</div>}
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
              <td className="td text-right text-neutral-dark-tertiary">
                {data.defaults[k].toFixed(2)}
              </td>
              <td className="td text-right">{data.weights[k]?.toFixed(2) ?? "—"}</td>
              <td className="td text-right">
                <input
                  type="number"
                  step="0.05"
                  min={0}
                  max={5}
                  className="w-20 border border-neutral-dark-secondary rounded px-1 py-0.5 bg-neutral-dark-secondary text-neutral-white"
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
        <h1 className="text-xl font-semibold text-neutral-white">Settings</h1>
        <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
          Configure module thresholds and scoring weights. Change weights here and rerun a module to see
          the effect. Defaults are from <code>scoring/engine.py</code>.
        </p>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-neutral-white mb-2">Filtering & Ranking</h2>
        <EquityThresholdsEditor />
      </div>

      <div>
        <h2 className="text-lg font-semibold text-neutral-white mb-2">Scoring Weights</h2>
        <div className="text-sm text-neutral-light-tertiary mb-4">
          Each module composes a score from named dimensions via a weighted sum,
          then dampens by confidence.
        </div>
        <div className="space-y-4">
          {MODULES.map((m) => (
            <WeightsEditor key={m} module={m} />
          ))}
        </div>
      </div>
    </div>
  );
}
