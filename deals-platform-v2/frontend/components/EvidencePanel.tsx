"use client";
import { useState } from "react";
import type { EvidenceOut } from "@/lib/types";
import { relTime } from "@/lib/format";
import { ModePill, ScopePill } from "./ModePill";

export function EvidencePanel({ items }: { items: EvidenceOut[] }) {
  if (!items.length) {
    return (
      <div className="panel p-3 text-sm text-neutral-dark-tertiary">
        No evidence attached to this item.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((e, idx) => (
        <EvidenceCard key={e.id} evidence={e} index={idx} />
      ))}
    </ul>
  );
}

function EvidenceCard({ evidence: e, index: idx }: { evidence: EvidenceOut; index: number }) {
  const [showFull, setShowFull] = useState(false);
  const [showMeta, setShowMeta] = useState(false);

  const isLive = e.mode === "live";
  const isStub = e.mode === "stub";
  const hasFallbackReason = Boolean(e.fallback_reason);
  const hasMeta = e.meta && Object.keys(e.meta).length > 0;

  return (
    <li className="panel p-3">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-brand-orange text-neutral-black text-xs font-bold">
          {idx + 1}
        </span>
        <ModePill mode={e.mode} />
        <ScopePill scope={e.scope} />
        <span className="text-xs text-neutral-dark-tertiary">{e.kind}</span>
        <span className="text-xs text-neutral-dark-tertiary ml-auto">
          retrieved {relTime(e.retrieved_at)}
        </span>
      </div>
      <div className="text-sm font-medium text-neutral-white">{e.title || "(no title)"}</div>
      {e.snippet && (
        <div
          className={`text-sm text-neutral-light-tertiary mt-1 ${
            showFull ? "" : "line-clamp-3"
          } whitespace-pre-wrap`}
        >
          {e.snippet}
        </div>
      )}
      {e.snippet && e.snippet.length > 200 && (
        <button
          type="button"
          className="text-xs text-brand-orange hover:underline mt-1"
          onClick={() => setShowFull((v) => !v)}
        >
          {showFull ? "Show less" : "Show full snippet"}
        </button>
      )}

      {/* Fallback reason banner — explains WHY this isn't live data */}
      {hasFallbackReason && !isLive && (
        <div
          className={`mt-2 px-2 py-1.5 rounded text-xs border ${
            isStub
              ? "bg-purple-950 border-purple-800 text-purple-200"
              : "bg-amber-950 border-amber-800 text-amber-200"
          }`}
        >
          <span className="font-semibold">
            {isStub ? "Why STUB: " : "Why MOCK: "}
          </span>
          {e.fallback_reason}
        </div>
      )}

      {/* Source link — prominent button */}
      <div className="flex items-center gap-3 text-xs text-neutral-dark-tertiary mt-2 flex-wrap">
        <span>
          source: <span className="font-mono">{e.source_id}</span>
        </span>
        {e.url && (
          <a
            href={e.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-neutral-black transition-colors"
            title={isLive ? "Open the live source to verify" : "Open the (mock) URL"}
          >
            🔗 {isLive ? "Verify Source" : "Open URL"}
          </a>
        )}
        {e.published_at && <span>published {relTime(e.published_at)}</span>}
        {hasMeta && (
          <button
            type="button"
            className="text-brand-orange hover:underline"
            onClick={() => setShowMeta((v) => !v)}
          >
            {showMeta ? "Hide details" : "Show data"}
          </button>
        )}
        <span className="ml-auto font-mono text-xs opacity-50">{e.id.slice(0, 8)}</span>
      </div>

      {/* Expandable meta — shows extracted data values */}
      {hasMeta && showMeta && (
        <pre className="mt-2 p-2 bg-neutral-dark-secondary rounded text-xs text-neutral-light-tertiary overflow-auto max-h-48">
          {JSON.stringify(e.meta, null, 2)}
        </pre>
      )}
    </li>
  );
}
