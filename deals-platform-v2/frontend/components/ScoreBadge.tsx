import clsx from "clsx";
import { scoreBand } from "@/lib/format";

export function ScoreBadge({ score, confidence }: { score: number; confidence?: number }) {
  const band = scoreBand(score);
  return (
    <div className="inline-flex items-center gap-2">
      <span
        className={clsx("inline-flex items-center px-2 py-0.5 text-xs rounded font-medium border", {
          "bg-neutral-dark-secondary text-data-red border-neutral-dark-tertiary": band === "risk",
          "bg-neutral-dark-secondary text-data-yellow border-neutral-dark-tertiary": band === "warn",
          "bg-neutral-dark-secondary text-emerald-400 border-neutral-dark-tertiary": band === "ok",
        })}
      >
        {score.toFixed(2)}
      </span>
      {confidence !== undefined && (
        <span className="text-xs text-neutral-dark-tertiary">conf {(confidence * 100).toFixed(0)}%</span>
      )}
    </div>
  );
}
