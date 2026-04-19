"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SourceHealthOut } from "@/lib/types";
import { ModePill } from "@/components/ModePill";
import { relTime } from "@/lib/format";

export default function Page() {
  const [rows, setRows] = useState<SourceHealthOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

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

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Sources</h1>
        <p className="text-sm text-ink-soft mt-1 max-w-2xl">
          Every adapter maps to a real named service. Where live fetch is unavailable,
          a fixture is returned and the row is marked <code>fixture</code>. Nothing is
          fabricated.
        </p>
      </div>
      {err && <div className="panel p-3 text-sm text-status-risk">{err}</div>}
      <div className="panel overflow-hidden">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">ID</th>
              <th className="th">Name</th>
              <th className="th">Mode</th>
              <th className="th">Last refresh</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="td font-mono text-xs">{r.id}</td>
                <td className="td">{r.name}</td>
                <td className="td">
                  <ModePill mode={r.mode} />
                </td>
                <td className="td text-xs text-ink-muted">{relTime(r.last_refresh_at)}</td>
                <td className="td text-xs">
                  {r.last_error ? (
                    <span className="text-status-risk">{r.last_error}</span>
                  ) : (
                    r.last_status || "—"
                  )}
                </td>
                <td className="td text-right">
                  <button
                    className="btn"
                    disabled={busy === r.id}
                    onClick={() => refresh(r.id)}
                  >
                    {busy === r.id ? "…" : "Refresh"}
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="td text-ink-muted" colSpan={6}>
                  No sources registered.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
