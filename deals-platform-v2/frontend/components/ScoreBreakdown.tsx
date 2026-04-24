export function ScoreBreakdown({
  dimensions,
  weights,
}: {
  dimensions: Record<string, number>;
  weights: Record<string, number>;
}) {
  const keys = Array.from(
    new Set([...Object.keys(dimensions), ...Object.keys(weights)]),
  ).sort();
  if (keys.length === 0) {
    return <div className="text-sm text-neutral-dark-tertiary">No dimensions scored.</div>;
  }
  return (
    <table className="w-full">
      <thead>
        <tr>
          <th className="th">Dimension</th>
          <th className="th text-right">Weight</th>
          <th className="th text-right">Value</th>
          <th className="th">&nbsp;</th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const v = dimensions[k] ?? 0;
          const w = weights[k] ?? 0;
          return (
            <tr key={k}>
              <td className="td font-medium">{k.replaceAll("_", " ")}</td>
              <td className="td text-right">{w.toFixed(2)}</td>
              <td className="td text-right">{v.toFixed(2)}</td>
              <td className="td">
                <div className="w-full h-1.5 bg-neutral-dark-secondary rounded">
                  <div
                    className="h-1.5 rounded bg-brand-orange"
                    style={{ width: `${Math.min(100, Math.max(0, v * 100))}%` }}
                  />
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
