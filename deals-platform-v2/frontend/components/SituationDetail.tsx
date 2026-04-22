"use client";
import { useState } from "react";
import { api } from "@/lib/api";
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
  const [explanation, setExplanation] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genErr, setGenErr] = useState<string | null>(null);

  if (!s) {
    return (
      <div className="panel p-6 text-sm text-neutral-dark-tertiary">
        Select a situation to see its evidence, score breakdown, and review controls.
      </div>
    );
  }

  const displayExplanation = explanation ?? s.explanation;

  const explanationWithCites = displayExplanation
    ? displayExplanation.replace(
        /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/g,
        (uuid) => {
          const idx = s.evidence_ids.indexOf(uuid);
          return idx >= 0 ? `[${idx + 1}]` : `[?]`;
        }
      )
    : "";

  const handleGenerate = async () => {
    setGenerating(true);
    setGenErr(null);
    try {
      const result = await api.generateExplanationV1(s.id);
      setExplanation(result.explanation);
    } catch (e: unknown) {
      setGenErr(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="panel p-4">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-xs text-neutral-dark-tertiary uppercase tracking-wide">
              {s.module} · {s.kind}
            </div>
            <div className="text-lg font-semibold mt-1 text-neutral-white">{s.title}</div>
            <div className="text-sm text-neutral-light-tertiary mt-1">{s.summary}</div>
          </div>
          <div className="text-right shrink-0">
            <ScoreBadge score={s.score} confidence={s.confidence} />
            <div className="text-xs text-neutral-dark-tertiary mt-1">Score 0–1</div>
          </div>
        </div>
        {s.next_action && (
          <div className="mt-3 border-l-4 border-brand-orange bg-neutral-dark-secondary px-3 py-2 rounded-r">
            <div className="text-xs font-semibold text-brand-orange uppercase tracking-wide">Next action</div>
            <div className="text-sm text-neutral-white mt-1">{s.next_action}</div>
          </div>
        )}
        {s.caveats.length > 0 && (
          <ul className="mt-2 text-xs text-neutral-dark-tertiary list-disc list-inside">
            {s.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </div>
      <div className="panel p-4">
        <div className="text-sm font-semibold mb-2 text-neutral-white">Score breakdown</div>
        <div className="text-xs text-neutral-dark-tertiary mb-2">Each dimension scored 0–1; weighted sum gives the opportunity score above.</div>
        <ScoreBreakdown dimensions={s.dimensions} weights={s.weights} />
      </div>
      <div className="panel p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-semibold text-neutral-white">Explanation</div>
          {!displayExplanation && (
            <button
              className="text-xs btn px-2 py-1 disabled:opacity-50"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          )}
        </div>
        {genErr && <div className="text-xs text-data-red mb-2">{genErr}</div>}
        {explanationWithCites ? (
          <div className="text-sm text-neutral-light-tertiary whitespace-pre-wrap">{explanationWithCites}</div>
        ) : (
          <div className="text-sm text-neutral-dark-tertiary italic">
            Click &ldquo;Generate&rdquo; to produce an LLM rationale (requires ANTHROPIC_API_KEY).
          </div>
        )}
        {s.explanation_cites.length > 0 && (
          <div className="text-xs text-neutral-dark-tertiary mt-2">
            Cites: {s.explanation_cites.map((c) => c.slice(0, 8)).join(", ")}
          </div>
        )}
      </div>
      <div>
        <div className="text-sm font-semibold mb-2 text-neutral-white">Evidence ({s.evidence.length})</div>
        <EvidencePanel items={s.evidence} />
      </div>
      <ReviewControls situation={s} onChange={onChange} />
    </div>
  );
}
