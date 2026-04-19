"use client";
import type { SituationOut } from "@/lib/types";
import { EvidencePanel } from "./EvidencePanel";
import { ReviewControls } from "./ReviewControls";
import { ScoreBadge } from "./ScoreBadge";
import { ScoreBreakdown } from "./ScoreBreakdown";

export function SituationDetail({
  s,
  onChange,
}: {
  s: SituationOut | null;
  onChange?: (s: SituationOut) => void;
}) {
  if (!s) {
    return (
      <div className="panel p-6 text-sm text-ink-muted">
        Select a situation to see its evidence, score breakdown, and review controls.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="panel p-4">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-xs text-ink-muted uppercase tracking-wide">
              {s.module} · {s.kind}
            </div>
            <div className="text-lg font-semibold mt-1">{s.title}</div>
            <div className="text-sm text-ink-soft mt-1">{s.summary}</div>
          </div>
          <ScoreBadge score={s.score} confidence={s.confidence} />
        </div>
        {s.next_action && (
          <div className="mt-3 text-sm">
            <span className="text-ink-muted">Next action: </span>
            <span className="text-ink">{s.next_action}</span>
          </div>
        )}
        {s.caveats.length > 0 && (
          <ul className="mt-2 text-xs text-ink-muted list-disc list-inside">
            {s.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel p-4">
        <div className="text-sm font-semibold mb-2">Score breakdown</div>
        <ScoreBreakdown dimensions={s.dimensions} weights={s.weights} />
      </div>
      <div className="panel p-4">
        <div className="text-sm font-semibold mb-2">Explanation</div>
        <div className="text-sm text-ink-soft whitespace-pre-wrap">{s.explanation}</div>
        {s.explanation_cites.length > 0 && (
          <div className="text-xs text-ink-muted mt-2">
            Cites: {s.explanation_cites.map((c) => c.slice(0, 8)).join(", ")}
          </div>
        )}
      </div>
      <div>
        <div className="text-sm font-semibold mb-2">Evidence ({s.evidence.length})</div>
        <EvidencePanel items={s.evidence} />
      </div>
      <ReviewControls situation={s} onChange={onChange} />
    </div>
  );
}
