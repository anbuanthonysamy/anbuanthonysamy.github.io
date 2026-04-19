import type { SectorHeatCell } from "@/lib/types";

function tone(avg: number): string {
  if (avg >= 0.6) return "bg-red-100 text-status-risk";
  if (avg >= 0.45) return "bg-amber-100 text-status-warn";
  if (avg >= 0.3) return "bg-emerald-50 text-status-ok";
  return "bg-paper text-ink-muted";
}

export function Heatmap({ cells }: { cells: SectorHeatCell[] }) {
  if (!cells.length) {
    return <div className="panel p-3 text-sm text-ink-muted">No sector data yet.</div>;
  }
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      {cells.map((c) => (
        <div key={c.sector} className={`panel p-3 ${tone(c.avg_score)}`}>
          <div className="text-xs uppercase tracking-wide">{c.sector}</div>
          <div className="text-2xl font-semibold mt-1">{c.avg_score.toFixed(2)}</div>
          <div className="text-xs text-ink-muted">{c.count} situations</div>
        </div>
      ))}
    </div>
  );
}
