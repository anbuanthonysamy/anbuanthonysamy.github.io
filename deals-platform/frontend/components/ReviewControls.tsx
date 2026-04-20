"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SituationOut } from "@/lib/types";

type Action = "accept" | "reject" | "edit" | "approve";

export function ReviewControls({
  situation,
  onChange,
}: {
  situation: SituationOut;
  onChange?: (s: SituationOut) => void;
}) {
  const [reason, setReason] = useState("");
  const [rating, setRating] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (action: Action) => {
    if (!reason.trim()) {
      setErr("Reason is required.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const updated = await api.review(situation.id, {
        action,
        reason: reason.trim(),
        reviewer: "demo.reviewer",
        rating_1_to_10: rating === "" ? null : Number(rating),
      });
      onChange?.(updated);
      setReason("");
      setRating("");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "review failed");
    } finally {
      setBusy(false);
    }
  };

  const state = situation.review.state;
  return (
    <div className="panel p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-neutral-white">Review</div>
        <span className="pill">state: {state}</span>
      </div>
      {situation.review.reviewer && (
        <div className="text-xs text-neutral-dark-tertiary">
          last: {situation.review.reviewer} — {situation.review.reason || "(no reason)"}
        </div>
      )}
      <textarea
        className="w-full text-sm border border-neutral-dark-secondary rounded p-2 bg-neutral-dark-secondary text-neutral-white placeholder-neutral-dark-tertiary"
        rows={2}
        placeholder="Reason for this action (required)…"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="flex items-center gap-2 text-xs">
        <label className="text-neutral-dark-tertiary">Rating 1–10</label>
        <input
          type="number"
          min={1}
          max={10}
          className="w-14 border border-neutral-dark-secondary rounded px-1 py-0.5 bg-neutral-dark-secondary text-neutral-white"
          value={rating}
          onChange={(e) => setRating(e.target.value === "" ? "" : Number(e.target.value))}
        />
      </div>
      {err && <div className="text-xs text-data-red">{err}</div>}
      <div className="flex gap-2 flex-wrap">
        <button className="btn" disabled={busy} onClick={() => submit("accept")}>
          Accept
        </button>
        <button className="btn" disabled={busy} onClick={() => submit("reject")}>
          Reject
        </button>
        <button className="btn" disabled={busy} onClick={() => submit("edit")}>
          Edit
        </button>
        <button className="btn-primary" disabled={busy} onClick={() => submit("approve")}>
          Approve
        </button>
      </div>
    </div>
  );
}
