"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

export default function Page() {
  const [coverage, setCoverage] = useState<Record<string, Record<string, number>>>({});
  const [labels, setLabels] = useState<{
    total_reviews: number;
    rated: number;
    by_action: Record<string, number>;
  } | null>(null);
  const [llm, setLlm] = useState<{
    calls: number;
    offline: number;
    cost_usd: number;
    tokens_in: number;
    tokens_out: number;
  } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [c, l, m] = await Promise.all([api.coverage(), api.labels(), api.llm()]);
        setCoverage(c);
        setLabels(l);
        setLlm(m);
      } catch (e: unknown) {
        setErr(e instanceof Error ? e.message : "load failed");
      }
    })();
  }, []);

  const states = ["pending", "accepted", "edited", "rejected", "approved"];

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-neutral-white">Evaluation</h1>
        <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
          Review volume, reviewer ratings, LLM cost, and per-module coverage across
          review states. Offline calls still count for latency tracking but cost $0.
        </p>
      </div>
      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      <div className="grid md:grid-cols-3 gap-3">
        <div className="panel p-3">
          <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">Reviews</div>
          <div className="text-2xl font-semibold mt-1">
            {labels?.total_reviews ?? "—"}
          </div>
          <div className="text-xs text-neutral-dark-tertiary">{labels?.rated ?? 0} rated 1–10 (awaiting review)</div>
        </div>
        <div className="panel p-3">
          <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">LLM calls</div>
          <div className="text-2xl font-semibold mt-1">{llm?.calls ?? "—"}</div>
          <div className="text-xs text-neutral-dark-tertiary">
            {llm?.offline ?? 0} offline · spend {money(llm?.cost_usd)}
          </div>
        </div>
        <div className="panel p-3">
          <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">Tokens</div>
          <div className="text-2xl font-semibold mt-1">
            {(llm?.tokens_in ?? 0) + (llm?.tokens_out ?? 0)}
          </div>
          <div className="text-xs text-neutral-dark-tertiary">
            in {llm?.tokens_in ?? 0} · out {llm?.tokens_out ?? 0}
          </div>
        </div>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">Module</th>
              {states.map((s) => (
                <th key={s} className="th text-right">
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.keys(coverage).length === 0 ? (
              <tr>
                <td className="td text-neutral-dark-tertiary" colSpan={states.length + 1}>
                  No situations yet.
                </td>
              </tr>
            ) : (
              Object.entries(coverage).map(([mod, by]) => (
                <tr key={mod}>
                  <td className="td font-medium">{mod}</td>
                  {states.map((s) => (
                    <td key={s} className="td text-right">
                      {by[s] ?? 0}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {labels && (
        <div className="panel p-3 text-sm">
          <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary mb-1">
            Reviewer actions
          </div>
          <div className="flex gap-4 flex-wrap">
            {Object.entries(labels.by_action).map(([a, n]) => (
              <span key={a} className="pill">
                {a}: {n}
              </span>
            ))}
            {Object.keys(labels.by_action).length === 0 && (
              <span className="text-neutral-dark-tertiary">No reviewer actions recorded.</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
