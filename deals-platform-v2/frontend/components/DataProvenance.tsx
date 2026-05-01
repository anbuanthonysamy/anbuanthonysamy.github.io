import type { SituationOut } from "@/lib/types";
import { relTime } from "@/lib/format";
import { ModePill } from "./ModePill";

const SCOPE_LABELS: Record<string, string> = {
  origination: "Public only",
  carve_outs: "Public only",
  post_deal: "Uploaded + public context",
  working_capital: "Uploaded + public benchmarks",
};

export function DataProvenance({
  module,
  items,
}: {
  module: string;
  items: SituationOut[];
}) {
  const scope = SCOPE_LABELS[module] ?? "Mixed";
  const sources = new Set<string>();
  let latest: string | null = null;
  const modes = { live: 0, fixture: 0, stub: 0, blocked: 0 };
  let evidenceCount = 0;
  for (const s of items) {
    for (const e of s.evidence) {
      sources.add(e.source_id);
      evidenceCount += 1;
      if (e.mode in modes) modes[e.mode as keyof typeof modes] += 1;
      if (e.retrieved_at && (!latest || e.retrieved_at > latest)) {
        latest = e.retrieved_at;
      }
    }
  }
  const liveRatio = evidenceCount > 0 ? Math.round((modes.live / evidenceCount) * 100) : 0;
  const liveColor =
    liveRatio >= 70
      ? "text-emerald-400"
      : liveRatio >= 30
      ? "text-data-yellow"
      : "text-data-red";
  return (
    <div className="panel p-3 space-y-2 text-xs">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div>
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Scope</span>
          <span className="ml-2 text-neutral-white font-medium">{scope}</span>
        </div>
        <div>
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Sources</span>
          <span className="ml-2 text-neutral-white font-medium">{sources.size}</span>
        </div>
        <div>
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Evidence rows</span>
          <span className="ml-2 text-neutral-white font-medium">{evidenceCount}</span>
        </div>
        <div
          className="flex items-center gap-2"
          title="Percentage of evidence rows that came from real, live API calls. Higher = more verifiable."
        >
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Data quality</span>
          <span className={`font-semibold ${liveColor}`}>{liveRatio}% live</span>
        </div>
        <div className="ml-auto text-neutral-dark-tertiary">
          latest fetch: {latest ? relTime(latest) : "—"}
        </div>
      </div>
      {evidenceCount > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-neutral-dark-tertiary uppercase tracking-wide">Mode breakdown</span>
          {modes.live > 0 && (
            <span title={`${modes.live} evidence rows from live APIs`}>
              <ModePill mode="live" /> <span className="text-neutral-white">{modes.live}</span>
            </span>
          )}
          {modes.fixture > 0 && (
            <span title={`${modes.fixture} evidence rows from local fixtures (live fetch failed)`}>
              <ModePill mode="fixture" /> <span className="text-neutral-white">{modes.fixture}</span>
            </span>
          )}
          {modes.stub > 0 && (
            <span title={`${modes.stub} evidence rows from stub sources (adapter not implemented)`}>
              <ModePill mode="stub" /> <span className="text-neutral-white">{modes.stub}</span>
            </span>
          )}
          {modes.blocked > 0 && (
            <span title={`${modes.blocked} evidence rows blocked (robots.txt or terms)`}>
              <ModePill mode="blocked" /> <span className="text-neutral-white">{modes.blocked}</span>
            </span>
          )}
          {/* Data quality bar */}
          <div className="ml-auto flex h-2 w-48 rounded overflow-hidden border border-neutral-dark-tertiary">
            {modes.live > 0 && (
              <div
                className="bg-emerald-500"
                style={{ width: `${(modes.live / evidenceCount) * 100}%` }}
                title={`${modes.live} live`}
              />
            )}
            {modes.fixture > 0 && (
              <div
                className="bg-amber-500"
                style={{ width: `${(modes.fixture / evidenceCount) * 100}%` }}
                title={`${modes.fixture} mock`}
              />
            )}
            {modes.stub > 0 && (
              <div
                className="bg-purple-500"
                style={{ width: `${(modes.stub / evidenceCount) * 100}%` }}
                title={`${modes.stub} stub`}
              />
            )}
            {modes.blocked > 0 && (
              <div
                className="bg-red-500"
                style={{ width: `${(modes.blocked / evidenceCount) * 100}%` }}
                title={`${modes.blocked} blocked`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
