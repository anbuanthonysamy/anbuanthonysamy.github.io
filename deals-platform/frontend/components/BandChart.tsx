"use client";

type Point = { x: number; plan: number; low: number; high: number; actual?: number | null };

export function BandChart({
  points,
  title,
  unit,
}: {
  points: Point[];
  title: string;
  unit?: string;
}) {
  if (!points.length) {
    return <div className="panel p-3 text-sm text-ink-muted">No data.</div>;
  }
  const width = 420;
  const height = 180;
  const padding = 28;
  const xs = points.map((p) => p.x);
  const ys = points.flatMap((p) => [p.low, p.high, p.plan, p.actual ?? p.plan]);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const X = (x: number) =>
    padding + ((x - xMin) / Math.max(1e-9, xMax - xMin)) * (width - padding * 2);
  const Y = (y: number) =>
    height - padding - ((y - yMin) / Math.max(1e-9, yMax - yMin)) * (height - padding * 2);

  const bandPath = [
    `M ${X(points[0].x)} ${Y(points[0].high)}`,
    ...points.slice(1).map((p) => `L ${X(p.x)} ${Y(p.high)}`),
    ...points
      .slice()
      .reverse()
      .map((p) => `L ${X(p.x)} ${Y(p.low)}`),
    "Z",
  ].join(" ");

  const planPath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${X(p.x)} ${Y(p.plan)}`)
    .join(" ");

  return (
    <div className="panel p-3">
      <div className="text-sm font-semibold mb-1">
        {title} {unit && <span className="text-xs text-ink-muted">({unit})</span>}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
        <path d={bandPath} fill="rgba(99,102,241,0.12)" stroke="none" />
        <path d={planPath} stroke="#6366f1" strokeWidth="1.5" fill="none" />
        {points.map((p, i) =>
          p.actual !== null && p.actual !== undefined ? (
            <circle
              key={i}
              cx={X(p.x)}
              cy={Y(p.actual)}
              r={3}
              fill={
                p.actual >= p.low && p.actual <= p.high ? "#059669" : "#dc2626"
              }
            />
          ) : null,
        )}
      </svg>
      <div className="text-xs text-ink-muted mt-1">
        Plan with ±tolerance band; dots are actuals (green in band, red out of band).
      </div>
    </div>
  );
}
