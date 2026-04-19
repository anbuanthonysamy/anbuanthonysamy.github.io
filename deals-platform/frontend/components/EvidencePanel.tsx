import type { EvidenceOut } from "@/lib/types";
import { relTime } from "@/lib/format";
import { ModePill, ScopePill } from "./ModePill";

export function EvidencePanel({ items }: { items: EvidenceOut[] }) {
  if (!items.length) {
    return (
      <div className="panel p-3 text-sm text-ink-muted">
        No evidence attached to this item.
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {items.map((e) => (
        <li key={e.id} className="panel p-3">
          <div className="flex items-center gap-2 mb-1">
            <ModePill mode={e.mode} />
            <ScopePill scope={e.scope} />
            <span className="text-xs text-ink-muted">{e.kind}</span>
            <span className="text-xs text-ink-muted ml-auto">
              retrieved {relTime(e.retrieved_at)}
            </span>
          </div>
          <div className="text-sm font-medium text-ink">{e.title || "(no title)"}</div>
          {e.snippet && (
            <div className="text-sm text-ink-soft mt-1 line-clamp-3">{e.snippet}</div>
          )}
          <div className="flex items-center gap-3 text-xs text-ink-muted mt-1">
            <span>source: {e.source_id}</span>
            {e.url && (
              <a
                href={e.url}
                target="_blank"
                rel="noreferrer"
                className="text-brand hover:underline"
              >
                open
              </a>
            )}
            {e.published_at && <span>published {relTime(e.published_at)}</span>}
            <span className="ml-auto font-mono">{e.id.slice(0, 8)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
