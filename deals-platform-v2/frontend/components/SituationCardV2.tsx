"use client";
import type { SituationV2 } from "@/lib/types";

function tierToBadge(tier: string | null) {
  if (!tier) return { label: "Monitor", bg: "bg-green-900", text: "text-green-100" };
  if (tier.includes("p1")) return { label: "P1 Hot", bg: "bg-red-900", text: "text-red-100" };
  if (tier.includes("p2")) return { label: "P2 Monitor", bg: "bg-amber-900", text: "text-amber-100" };
  return { label: "P3 Early", bg: "bg-green-900", text: "text-green-100" };
}

function tierToColour(tier: string | null): "red" | "amber" | "green" {
  if (!tier) return "green";
  if (tier.includes("p1")) return "red";
  if (tier.includes("p2")) return "amber";
  return "green";
}

function countryToFlag(country: string | null): string {
  if (!country) return "";
  if (country.toUpperCase() === "US") return "🇺🇸";
  if (country.toUpperCase() === "UK" || country.toUpperCase() === "GB") return "🇬🇧";
  return "";
}

function formatEquityValue(value: number | null): string {
  if (!value) return "";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  return `$${value.toFixed(0)}`;
}

const colours: Record<string, Record<string, string>> = {
  red: {
    bg: "bg-red-900/20",
    border: "border-red-700",
    badge: "bg-red-900 text-red-100",
  },
  amber: {
    bg: "bg-amber-900/20",
    border: "border-amber-700",
    badge: "bg-amber-900 text-amber-100",
  },
  green: {
    bg: "bg-green-900/20",
    border: "border-green-700",
    badge: "bg-green-900 text-green-100",
  },
};

export function SituationCardV2({
  situation,
  active,
  onSelect,
}: {
  situation: SituationV2;
  active: boolean;
  onSelect: (s: SituationV2) => void;
}) {
  const colour = tierToColour(situation.tier);
  const style = colours[colour];

  return (
    <button
      onClick={() => onSelect(situation)}
      className={`
        w-full text-left panel p-3 transition-all
        ${active ? `${style.bg} ${style.border}` : "hover:border-neutral-dark-secondary"}
        ${style.border} border
      `}
    >
      <div className="flex items-start gap-2">
        <div className="flex-none">
          {situation.rank && (
            <div className="text-lg font-bold text-neutral-white bg-neutral-dark-secondary rounded-full w-8 h-8 flex items-center justify-center">
              {situation.rank}
            </div>
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-semibold px-2 py-1 rounded ${style.badge}`}>
              {situation.tier?.replace("_", " ").toUpperCase() || "MONITOR"}
            </span>
            <span className="text-sm font-mono text-neutral-light-tertiary">
              Score {situation.score.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center gap-1 mt-1">
            <p className="text-sm font-medium text-neutral-white">
              {situation.company?.name || "Unknown"}
            </p>
            {situation.company?.country && (
              <span className="text-sm">{countryToFlag(situation.company.country)}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-neutral-light-tertiary">
            <span>{situation.module.toUpperCase()}</span>
            {situation.company?.equity_value && (
              <>
                <span>•</span>
                <span className="font-mono">{formatEquityValue(situation.company.equity_value)}</span>
              </>
            )}
            {situation.company?.sector && (
              <>
                <span>•</span>
                <span>{situation.company.sector}</span>
              </>
            )}
          </div>
        </div>
        {situation.score_delta !== 0 && (
          <div className="text-right text-xs">
            <span className={situation.score_delta > 0 ? "text-data-green" : "text-data-red"}>
              {situation.score_delta > 0 ? "↑" : "↓"} {Math.abs(situation.score_delta).toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {situation.first_seen_at && (
        <div className="text-xs text-neutral-dark-tertiary mt-2">
          Detected {new Date(situation.first_seen_at).toLocaleDateString()}
        </div>
      )}

      {situation.signals && Object.keys(situation.signals).length > 0 && (
        <div className="mt-2 text-xs">
          <div className="text-neutral-light-tertiary mb-1">Signals triggered:</div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(situation.signals)
              .filter(([, val]) => {
                if (typeof val === "boolean") return val;
                if (typeof val === "number") return val > 0;
                return !!val;
              })
              .slice(0, 3)
              .map(([key, val]) => (
                <span
                  key={key}
                  className="bg-green-900/30 border border-green-700 px-1.5 py-0.5 rounded text-green-100 font-medium"
                >
                  {key.replace(/_/g, " ")}
                  {typeof val === "number" && val > 0 ? `: ${val.toFixed(1)}` : ""}
                </span>
              ))}
            {Object.entries(situation.signals).filter(([, val]) => {
              if (typeof val === "boolean") return val;
              if (typeof val === "number") return val > 0;
              return !!val;
            }).length > 3 && (
              <span className="text-neutral-dark-tertiary text-xs">
                +{
                  Object.entries(situation.signals).filter(([, val]) => {
                    if (typeof val === "boolean") return val;
                    if (typeof val === "number") return val > 0;
                    return !!val;
                  }).length - 3
                } more
              </span>
            )}
          </div>
        </div>
      )}
    </button>
  );
}
