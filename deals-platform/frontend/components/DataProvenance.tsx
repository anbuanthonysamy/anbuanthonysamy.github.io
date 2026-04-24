import type { SituationOut } from "@/lib/types";
import { relTime } from "@/lib/format";

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
  let modes = { live: 0, fixture: 0, blocked: 0 };
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
  return (
    <div className="panel p-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
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
      <div className="flex items-center gap-2">
        <span className="text-neutral-dark-tertiary uppercase tracking-wide">Mode</span>
        {modes.live > 0 && (
          <span className="pill" title="Live-fetched evidence">live {modes.live}</span>
        )}
        {modes.fixture > 0 && (
          <span className="pill" title="Fixture-backed evidence">fixture {modes.fixture}</span>
        )}
        {modes.blocked > 0 && (
          <span className="pill" title="Source blocked">blocked {modes.blocked}</span>
        )}
        {evidenceCount === 0 && <span className="text-neutral-dark-tertiary">none</span>}
      </div>
      <div className="ml-auto text-neutral-dark-tertiary">
        latest fetch: {latest ? relTime(latest) : "—"}
      </div>
    </div>
  );
}
