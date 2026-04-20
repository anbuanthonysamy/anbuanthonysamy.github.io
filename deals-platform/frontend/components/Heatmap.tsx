import type { SectorHeatCell } from "@/lib/types";

function tone(avg: number): string {
  if (avg >= 0.6) return "bg-neutral-dark-secondary text-data-red";
  if (avg >= 0.45) return "bg-neutral-dark-secondary text-data-yellow";
  if (avg >= 0.3) return "bg-neutral-dark-secondary text-emerald-400";
  return "bg-neutral-dark-secondary text-neutral-dark-tertiary";
}

export function Heatmap({ cells }: { cells: SectorHeatCell[] }) {
  if (!cells.length) {
    return <div className="panel p-3 text-sm text-neutral-dark-tertiary">No sector data yet.</div>;
  }
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      {cells.map((c) => (
        <div key={c.sector} className={`panel p-3 ${tone(c.avg_score)}`}>
          <div className="text-xs uppercase tracking-wide text-neutral-white">{c.sector}</div>
          <div className="text-2xl font-semibold mt-1">{c.avg_score.toFixed(2)}</div>
          <div className="text-xs text-neutral-dark-tertiary">{c.count} situations</div>
        </div>
      ))}
    </div>
  );
}
