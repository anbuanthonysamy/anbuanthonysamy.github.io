"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SourceHealthOut } from "@/lib/types";
import { ModePill } from "@/components/ModePill";
import { SourceVerifier } from "@/components/SourceVerifier";
import { relTime } from "@/lib/format";

export default function Page() {
  const [rows, setRows] = useState<SourceHealthOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [verifying, setVerifying] = useState<SourceHealthOut | null>(null);

  const load = async () => {
    setErr(null);
    try {
      setRows(await api.sources());
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "load failed");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const refresh = async (id: string) => {
    setBusy(id);
    setErr(null);
    try {
      await api.refreshSource(id);
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "refresh failed");
    } finally {
      setBusy(null);
    }
  };

  const realSources = rows.filter((r) => !r.is_stub);
  const stubSources = rows.filter((r) => r.is_stub);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-neutral-white">Sources</h1>
        <p className="text-sm text-neutral-light-tertiary mt-1 max-w-3xl">
          Every data source the platform consults. Real adapters attempt live API calls
          and fall back to fixtures if blocked or unavailable. Stubs are documented placeholders
          for sources that haven&apos;t been implemented yet. Click <strong>Test Now</strong> on
          any real source to verify it&apos;s actually returning live data.
        </p>
      </div>

      {err && <div className="panel p-3 text-sm text-data-red">{err}</div>}

      {/* Legend */}
      <div className="panel p-3 flex flex-wrap items-center gap-4 text-xs">
        <span className="text-neutral-dark-tertiary uppercase tracking-wide">Modes:</span>
        <span className="flex items-center gap-2">
          <ModePill mode="live" /> <span className="text-neutral-light-tertiary">real API data</span>
        </span>
        <span className="flex items-center gap-2">
          <ModePill mode="fixture" /> <span className="text-neutral-light-tertiary">fell back to local fixture</span>
        </span>
        <span className="flex items-center gap-2">
          <ModePill mode="stub" /> <span className="text-neutral-light-tertiary">adapter not implemented</span>
        </span>
        <span className="flex items-center gap-2">
          <ModePill mode="blocked" /> <span className="text-neutral-light-tertiary">blocked by robots/terms</span>
        </span>
      </div>

      <SourceTable
        title="Real adapters"
        description="These sources have implemented adapters that attempt live API calls."
        rows={realSources}
        busy={busy}
        onRefresh={refresh}
        onVerify={setVerifying}
      />

      <SourceTable
        title="Stubs (not yet implemented)"
        description="These sources are documented in source-matrix.md but the adapter code is not yet written. They always return placeholder data."
        rows={stubSources}
        busy={busy}
        onRefresh={refresh}
        onVerify={setVerifying}
        isStubGroup
      />

      {verifying && (
        <SourceVerifier source={verifying} onClose={() => setVerifying(null)} />
      )}
    </div>
  );
}

function SourceTable({
  title,
  description,
  rows,
  busy,
  onRefresh,
  onVerify,
  isStubGroup = false,
}: {
  title: string;
  description: string;
  rows: SourceHealthOut[];
  busy: string | null;
  onRefresh: (id: string) => void;
  onVerify: (s: SourceHealthOut) => void;
  isStubGroup?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div>
        <h2 className="text-sm font-semibold text-neutral-white">{title}</h2>
        <p className="text-xs text-neutral-dark-tertiary mt-0.5">{description}</p>
      </div>
      <div className="panel overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">Source</th>
              <th className="th">Mode</th>
              <th className="th">Last refresh</th>
              <th className="th">Status / Reason</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="td align-top">
                  <div className="font-medium text-neutral-white">{r.name}</div>
                  <div className="font-mono text-xs text-neutral-dark-tertiary mt-0.5">{r.id}</div>
                  {r.description && (
                    <div className="text-xs text-neutral-light-tertiary mt-1 max-w-md">
                      {r.description}
                    </div>
                  )}
                </td>
                <td className="td align-top">
                  <ModePill mode={r.mode} />
                </td>
                <td className="td text-xs text-neutral-dark-tertiary align-top">
                  {relTime(r.last_refresh_at)}
                </td>
                <td className="td text-xs align-top max-w-xs">
                  {r.last_error && (
                    <div className="text-data-red mb-1">{r.last_error}</div>
                  )}
                  {r.last_fallback_reason && (
                    <div className="text-amber-300">{r.last_fallback_reason}</div>
                  )}
                  {!r.last_error && !r.last_fallback_reason && (
                    <span className="text-neutral-dark-tertiary">{r.last_status || "—"}</span>
                  )}
                </td>
                <td className="td text-right align-top whitespace-nowrap">
                  <button
                    className="btn mr-2"
                    onClick={() => onVerify(r)}
                    title="Test the live API call and view raw result"
                  >
                    Verify
                  </button>
                  {!isStubGroup && (
                    <button
                      className="btn"
                      disabled={busy === r.id}
                      onClick={() => onRefresh(r.id)}
                    >
                      {busy === r.id ? "…" : "Refresh"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="td text-neutral-dark-tertiary" colSpan={5}>
                  No sources in this group.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
