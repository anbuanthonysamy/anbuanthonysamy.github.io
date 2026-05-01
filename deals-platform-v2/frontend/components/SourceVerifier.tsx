"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { SourceHealthOut, SourceTestOut } from "@/lib/types";
import { ModePill } from "./ModePill";
import { relTime } from "@/lib/format";

export function SourceVerifier({
  source,
  onClose,
}: {
  source: SourceHealthOut;
  onClose: () => void;
}) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SourceTestOut | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const runTest = async () => {
    setTesting(true);
    setErr(null);
    setResult(null);
    try {
      const out = await api.testSource(source.id);
      setResult(out);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "test failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="panel max-w-2xl w-full p-5 space-y-4 max-h-[90vh] overflow-y-auto"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-neutral-white">{source.name}</h2>
            <div className="text-xs font-mono text-neutral-dark-tertiary mt-1">{source.id}</div>
          </div>
          <button
            type="button"
            className="btn"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {source.description && (
          <div className="text-sm text-neutral-light-tertiary">{source.description}</div>
        )}

        <div className="flex items-center gap-3 text-xs flex-wrap">
          <ModePill mode={source.mode} />
          {source.is_stub && (
            <span className="text-purple-400">Adapter not yet implemented</span>
          )}
          {source.homepage_url && (
            <a
              href={source.homepage_url}
              target="_blank"
              rel="noreferrer"
              className="text-brand-orange hover:underline"
            >
              Source homepage ↗
            </a>
          )}
          <span className="text-neutral-dark-tertiary ml-auto">
            last refresh: {relTime(source.last_refresh_at)}
          </span>
        </div>

        {source.last_fallback_reason && (
          <div className="px-3 py-2 rounded bg-amber-950 border border-amber-800 text-amber-200 text-xs">
            <span className="font-semibold">Last fallback reason: </span>
            {source.last_fallback_reason}
          </div>
        )}

        <div className="border-t border-neutral-dark-secondary pt-4">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div>
              <div className="text-sm font-semibold text-neutral-white">Test live fetch</div>
              <div className="text-xs text-neutral-dark-tertiary">
                Forces a real API call right now and shows what comes back. Does not save to database.
              </div>
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={testing || source.is_stub}
              onClick={runTest}
              title={source.is_stub ? "Stub adapter — nothing to test" : "Test live fetch now"}
            >
              {testing ? "Testing…" : "Test Now"}
            </button>
          </div>

          {err && (
            <div className="px-3 py-2 rounded bg-red-950 border border-red-800 text-data-red text-xs">
              {err}
            </div>
          )}

          {result && <TestResult result={result} />}
        </div>
      </div>
    </div>
  );
}

function TestResult({ result }: { result: SourceTestOut }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <ModePill mode={result.mode} />
        <span className={`text-sm font-semibold ${result.success ? "text-emerald-400" : "text-data-red"}`}>
          {result.success ? "✓ LIVE — real data returned" : "✗ Not live"}
        </span>
        <span className="text-xs text-neutral-dark-tertiary">
          {result.duration_ms} ms · {result.item_count} items
        </span>
      </div>

      {result.fallback_reason && (
        <div className="px-3 py-2 rounded bg-amber-950 border border-amber-800 text-amber-200 text-xs">
          <span className="font-semibold">Fallback reason: </span>
          {result.fallback_reason}
        </div>
      )}

      {result.error && !result.fallback_reason && (
        <div className="px-3 py-2 rounded bg-red-950 border border-red-800 text-data-red text-xs">
          <span className="font-semibold">Error: </span>
          {result.error}
        </div>
      )}

      {result.sample_title && (
        <div className="panel p-3 space-y-2 bg-neutral-dark-secondary">
          <div className="text-xs uppercase tracking-wide text-neutral-dark-tertiary">
            Sample item (first of {result.item_count})
          </div>
          <div className="text-sm font-medium text-neutral-white">{result.sample_title}</div>
          {result.sample_snippet && (
            <div className="text-sm text-neutral-light-tertiary whitespace-pre-wrap">
              {result.sample_snippet}
            </div>
          )}
          <div className="flex items-center gap-3 text-xs flex-wrap">
            {result.sample_url && (
              <a
                href={result.sample_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-brand-orange text-brand-orange hover:bg-brand-orange hover:text-neutral-black transition-colors"
              >
                🔗 Open source
              </a>
            )}
            {result.sample_published_at && (
              <span className="text-neutral-dark-tertiary">
                published {relTime(result.sample_published_at)}
              </span>
            )}
            <span className="ml-auto text-neutral-dark-tertiary">
              tested {relTime(result.tested_at)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
