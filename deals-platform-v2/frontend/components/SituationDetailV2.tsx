"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SituationV2 } from "@/lib/types";

function tierLabel(tier: string | null): string {
  if (!tier) return "Monitor";
  const parts = tier.split("_");
  return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export function SituationDetailV2({ situation }: { situation: SituationV2 }) {
  const [generatingExplanation, setGeneratingExplanation] = useState(false);
  const [explanation, setExplanation] = useState(situation.explanation);
  const [explanationError, setExplanationError] = useState<string | null>(null);

  const handleGenerateExplanation = async () => {
    setGeneratingExplanation(true);
    setExplanationError(null);
    try {
      const result = await api.generateExplanation(situation.id);
      setExplanation(result.explanation);
    } catch (e: unknown) {
      setExplanationError(e instanceof Error ? e.message : "Failed to generate explanation");
    } finally {
      setGeneratingExplanation(false);
    }
  };

  return (
    <div className="panel p-4 space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-neutral-white">
              {situation.company?.name || "Unknown Company"}
            </h2>
            <p className="text-sm text-neutral-light-tertiary mt-1">
              {situation.module.toUpperCase()} • {situation.company?.sector || "Unknown Sector"}
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-neutral-white">{situation.score.toFixed(2)}</div>
            <p className="text-xs text-neutral-light-tertiary">Opportunity Score</p>
          </div>
        </div>

        {/* Tier & Delta */}
        <div className="flex items-center gap-3">
          <span
            className={`
            text-xs font-semibold px-3 py-1 rounded
            ${
              situation.tier_colour === "red"
                ? "bg-red-900 text-red-100"
                : situation.tier_colour === "amber"
                  ? "bg-amber-900 text-amber-100"
                  : "bg-green-900 text-green-100"
            }
          `}
          >
            {tierLabel(situation.tier)}
          </span>
          {situation.score_delta !== 0 && (
            <span
              className={`text-sm font-semibold ${situation.score_delta > 0 ? "text-data-green" : "text-data-red"}`}
            >
              {situation.score_delta > 0 ? "↑" : "↓"} {Math.abs(situation.score_delta).toFixed(2)}
            </span>
          )}
        </div>
      </div>

      <hr className="border-neutral-dark-secondary" />

      {/* Timeline */}
      <div className="text-xs text-neutral-light-tertiary space-y-1">
        {situation.first_seen_at && (
          <div>
            <span className="text-neutral-white font-semibold">First detected:</span>{" "}
            {new Date(situation.first_seen_at).toLocaleString()}
          </div>
        )}
        {situation.last_updated_at && (
          <div>
            <span className="text-neutral-white font-semibold">Last updated:</span>{" "}
            {new Date(situation.last_updated_at).toLocaleString()}
          </div>
        )}
      </div>

      {/* Signals */}
      {situation.signals && Object.keys(situation.signals).length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-neutral-white mb-2">Deterministic Signals</h3>
          <p className="text-xs text-neutral-light-tertiary mb-2">
            Rules-based signal detection (no LLM required). Triggered automatically during scans.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(situation.signals)
              .sort((a, b) => {
                const aActive = typeof a[1] === "boolean" ? a[1] : !!a[1];
                const bActive = typeof b[1] === "boolean" ? b[1] : !!b[1];
                return bActive ? 1 : -1;
              })
              .map(([key, val]) => {
                const isActive = typeof val === "boolean" ? val : !!val;
                return (
                  <div
                    key={key}
                    className={`rounded p-2 text-xs border ${
                      isActive
                        ? "bg-green-900/20 border-green-700"
                        : "bg-neutral-dark-secondary border-neutral-dark-tertiary"
                    }`}
                  >
                    <div className="text-neutral-light-tertiary capitalize flex items-center gap-1">
                      {isActive ? <span className="text-data-green">✓</span> : <span className="text-neutral-dark-tertiary">○</span>}
                      {key.replace(/_/g, " ")}
                    </div>
                    <div className={`font-semibold mt-1 ${isActive ? "text-neutral-white" : "text-neutral-dark-tertiary"}`}>
                      {typeof val === "boolean" ? (val ? "Active" : "Inactive") : typeof val === "number" ? val.toFixed(2) : String(val).slice(0, 20)}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Explanation */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-neutral-white">Explanation</h3>
          {!explanation && (
            <button
              onClick={handleGenerateExplanation}
              disabled={generatingExplanation}
              className="text-xs btn px-2 py-1 disabled:opacity-50"
            >
              {generatingExplanation ? "Generating…" : "Generate"}
            </button>
          )}
        </div>

        {explanationError && (
          <div className="bg-data-red/10 border border-data-red rounded p-2">
            <p className="text-xs text-data-red">{explanationError}</p>
          </div>
        )}

        {explanation ? (
          <div className="bg-neutral-dark-secondary rounded p-3 text-sm text-neutral-light-primary leading-relaxed">
            {explanation}
          </div>
        ) : (
          <div className="bg-neutral-dark-secondary rounded p-3 text-sm text-neutral-dark-tertiary italic">
            Click "Generate" to create an LLM explanation based on the signals above.
          </div>
        )}
      </div>

      {/* Caveats */}
      {situation.caveats && situation.caveats.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-neutral-white mb-2">Caveats</h3>
          <ul className="text-xs text-neutral-light-tertiary space-y-1">
            {situation.caveats.map((c, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-data-yellow">⚠</span> {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Data Sources Quality */}
      <div className="bg-neutral-dark-secondary rounded p-3">
        <h3 className="text-sm font-semibold text-neutral-white mb-2">Data Sources</h3>
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-data-green">✓</span>
            <span className="text-neutral-light-tertiary">Data collected from multiple sources in <code className="bg-neutral-black px-1 rounded">live</code> mode</span>
          </div>
          <div className="text-neutral-dark-tertiary mt-2">
            <span className="text-xs">Includes: EDGAR filings, market data (yfinance), news feeds, and financial metrics APIs</span>
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div className="text-xs text-neutral-dark-tertiary border-t border-neutral-dark-secondary pt-3">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-neutral-light-tertiary">Company ID:</span> {situation.company_id}
          </div>
          <div>
            <span className="text-neutral-light-tertiary">Situation ID:</span> {situation.id}
          </div>
        </div>
      </div>
    </div>
  );
}
