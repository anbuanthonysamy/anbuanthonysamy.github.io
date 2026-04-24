"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SituationOut, SituationV2 } from "@/lib/types";

function tierLabel(tier: string | null): string {
  if (!tier) return "Monitor";
  const parts = tier.split("_");
  return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export function SituationDetailV2({ situation, onReviewChange }: { situation: SituationV2; onReviewChange?: () => void }) {
  const [generatingExplanation, setGeneratingExplanation] = useState(false);
  const [explanation, setExplanation] = useState(situation.explanation);
  const [explanationError, setExplanationError] = useState<string | null>(null);

  // v1 situation data fetched on demand for review controls
  const [v1Sit, setV1Sit] = useState<SituationOut | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewErr, setReviewErr] = useState<string | null>(null);

  useEffect(() => {
    setExplanation(situation.explanation);
    setV1Sit(null);
    setReviewReason("");
    setReviewErr(null);
    api.situation(situation.id).then(setV1Sit).catch(() => null);
  }, [situation.id]);

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

  const submitReview = async (action: "accept" | "reject" | "edit" | "approve") => {
    if (!reviewReason.trim()) { setReviewErr("Reason is required."); return; }
    setReviewBusy(true);
    setReviewErr(null);
    try {
      const updated = await api.review(situation.id, {
        action,
        reason: reviewReason.trim(),
        reviewer: "demo.reviewer",
      });
      setV1Sit(updated);
      setReviewReason("");
      onReviewChange?.();
    } catch (e: unknown) {
      setReviewErr(e instanceof Error ? e.message : "review failed");
    } finally {
      setReviewBusy(false);
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
            <p className="text-xs text-neutral-light-tertiary">Score (0–1)</p>
          </div>
        </div>

        {/* Tier & Delta */}
        <div className="flex items-center gap-3">
          <span
            className={`text-xs font-semibold px-3 py-1 rounded ${
              situation.tier_colour === "red"
                ? "bg-red-900 text-red-100"
                : situation.tier_colour === "amber"
                  ? "bg-amber-900 text-amber-100"
                  : "bg-green-900 text-green-100"
            }`}
          >
            {tierLabel(situation.tier)}
          </span>
          {situation.score_delta !== 0 && (
            <span className={`text-sm font-semibold ${situation.score_delta > 0 ? "text-data-green" : "text-data-red"}`}>
              {situation.score_delta > 0 ? "↑" : "↓"} {Math.abs(situation.score_delta).toFixed(2)}
            </span>
          )}
          {situation.company?.equity_value != null && situation.company.equity_value > 0 && (
            <span className="text-sm text-neutral-light-tertiary">
              ${(situation.company.equity_value / 1e9).toFixed(1)}B equity
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
            Rules-based detection. Active signals (✓) contributed to the score above.
          </p>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(situation.signals)
              .sort((a, b) => {
                const aActive = typeof a[1] === "boolean" ? a[1] : !!a[1];
                const bActive = typeof b[1] === "boolean" ? b[1] : !!b[1];
                return Number(bActive) - Number(aActive);
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
                      {typeof val === "boolean"
                        ? val ? "Active" : "Inactive"
                        : typeof val === "number"
                          ? val.toFixed(2)
                          : String(val).slice(0, 30)}
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
          <div className="bg-data-red/10 border border-data-red rounded p-2 mb-2">
            <p className="text-xs text-data-red">{explanationError}</p>
          </div>
        )}
        {explanation ? (
          <div className="bg-neutral-dark-secondary rounded p-3 text-sm text-neutral-light-primary leading-relaxed">
            {explanation}
          </div>
        ) : (
          <div className="bg-neutral-dark-secondary rounded p-3 text-sm text-neutral-dark-tertiary italic">
            Click &ldquo;Generate&rdquo; to produce an LLM rationale from the signals above.
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

      {/* Review */}
      <div className="panel p-3 space-y-2 border border-neutral-dark-secondary rounded">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-neutral-white">Review</div>
          {v1Sit && (
            <span className="pill">state: {v1Sit.review.state}</span>
          )}
        </div>
        {v1Sit?.review.reviewer && (
          <div className="text-xs text-neutral-dark-tertiary">
            last: {v1Sit.review.reviewer} — {v1Sit.review.reason || "(no reason)"}
          </div>
        )}
        <textarea
          className="w-full text-sm border border-neutral-dark-secondary rounded p-2 bg-neutral-dark-secondary text-neutral-white placeholder-neutral-dark-tertiary"
          rows={2}
          placeholder="Reason for this action (required)…"
          value={reviewReason}
          onChange={(e) => setReviewReason(e.target.value)}
        />
        <div className="text-xs text-neutral-dark-tertiary bg-neutral-dark-secondary px-2 py-1 rounded">
          <strong>Workflow:</strong> Accept = confirmed opportunity, Approve = ready for MD/client, Reject = drop
        </div>
        {reviewErr && <div className="text-xs text-data-red">{reviewErr}</div>}
        <div className="flex gap-2 flex-wrap">
          <button className="btn" disabled={reviewBusy} onClick={() => submitReview("accept")}>Accept</button>
          <button className="btn" disabled={reviewBusy} onClick={() => submitReview("reject")}>Reject</button>
          <button className="btn-primary" disabled={reviewBusy} onClick={() => submitReview("approve")}>Approve</button>
        </div>
      </div>

      {/* Metadata */}
      <div className="text-xs text-neutral-dark-tertiary border-t border-neutral-dark-secondary pt-3">
        <div className="grid grid-cols-2 gap-2">
          <div><span className="text-neutral-light-tertiary">Company ID:</span> {situation.company_id}</div>
          <div><span className="text-neutral-light-tertiary">Situation ID:</span> {situation.id}</div>
        </div>
      </div>
    </div>
  );
}
