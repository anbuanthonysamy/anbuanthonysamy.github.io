import clsx from "clsx";
import { scoreBand } from "@/lib/format";

export function ScoreBadge({ score, confidence }: { score: number; confidence?: number }) {
  const band = scoreBand(score);
  return (
    <div className="inline-flex items-center gap-2">
      <span
        className={clsx("inline-flex items-center px-2 py-0.5 text-xs rounded font-medium", {
          "bg-red-50 text-status-risk border border-red-200": band === "risk",
          "bg-amber-50 text-status-warn border border-amber-200": band === "warn",
          "bg-emerald-50 text-status-ok border border-emerald-200": band === "ok",
        })}
      >
        {score.toFixed(2)}
      </span>
      {confidence !== undefined && (
        <span className="text-xs text-ink-muted">conf {(confidence * 100).toFixed(0)}%</span>
      )}
    </div>
  );
}
