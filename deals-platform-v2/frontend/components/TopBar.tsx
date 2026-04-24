"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Health = { ok: boolean; live_llm: boolean; offline: boolean };

export function TopBar() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const offline = failed || health?.offline === true;
  const label = failed
    ? "backend unreachable"
    : offline
    ? "offline mode"
    : "live";

  const tone = offline
    ? "border-neutral-dark-secondary text-neutral-dark-tertiary"
    : "border-brand-orange text-brand-orange";

  return (
    <header className="flex items-center justify-end gap-2 px-6 py-2 border-b border-neutral-dark-secondary bg-neutral-black/40">
      <span
        className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border ${tone}`}
        title={
          offline
            ? "LLM calls return deterministic fixtures; source refreshes still hit live adapters when payload is supplied."
            : "Backend reachable. Live LLM routing enabled where configured."
        }
      >
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            offline ? "bg-neutral-dark-tertiary" : "bg-brand-orange"
          }`}
        />
        {label}
      </span>
    </header>
  );
}
