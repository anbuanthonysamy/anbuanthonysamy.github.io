"use client";
import type { SituationOut } from "@/lib/types";
import { ScoreBadge } from "./ScoreBadge";
import { ModePill } from "./ModePill";

export function SituationCard({
  s,
  active,
  onSelect,
}: {
  s: SituationOut;
  active?: boolean;
  onSelect?: (s: SituationOut) => void;
}) {
  const modes = Array.from(new Set(s.evidence.map((e) => e.mode)));
  return (
    <button
      type="button"
      className={`text-left w-full panel p-3 hover:bg-neutral-dark-secondary transition-colors ${
        active ? "ring-1 ring-brand-orange" : ""
      }`}
      onClick={() => onSelect?.(s)}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-neutral-white truncate">{s.title}</div>
          <div className="text-xs text-neutral-dark-tertiary truncate">{s.summary}</div>
        </div>
        <ScoreBadge score={s.score} confidence={s.confidence} />
      </div>
      <div className="mt-2 flex items-center gap-1 flex-wrap">
        <span className="pill">{s.kind}</span>
        {modes.map((m) => (
          <ModePill key={m} mode={m} />
        ))}
        <span className="text-xs text-neutral-dark-tertiary ml-auto">
          {s.evidence.length} evidence · conf {(s.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </button>
  );
}
