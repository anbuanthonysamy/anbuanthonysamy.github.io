import clsx from "clsx";

const MODE_CONFIG: Record<
  string,
  { label: string; cls: string; tooltip: string; icon: string }
> = {
  live: {
    label: "LIVE",
    cls: "pill-ok",
    tooltip: "Real data fetched from a live API at the timestamp shown. Click 'open' to verify.",
    icon: "✓",
  },
  fixture: {
    label: "MOCK",
    cls: "pill-mock",
    tooltip:
      "Mock/test data from a local fixture file. The live API was tried but failed, " +
      "blocked, or no API key was provided. See fallback reason below.",
    icon: "⚠",
  },
  blocked: {
    label: "BLOCKED",
    cls: "pill-risk",
    tooltip:
      "The source's robots.txt or terms blocked this fetch. No data was returned " +
      "for this evidence record.",
    icon: "✕",
  },
  stub: {
    label: "STUB",
    cls: "pill-stub",
    tooltip:
      "This source adapter is documented but not yet implemented. The data here " +
      "is a placeholder, not real and not from a fixture.",
    icon: "⊙",
  },
  never_refreshed: {
    label: "NEVER FETCHED",
    cls: "pill-mock",
    tooltip: "This source has never been refreshed in this database.",
    icon: "○",
  },
};

export function ModePill({
  mode,
  showIcon = true,
}: {
  mode: string | null | undefined;
  showIcon?: boolean;
}) {
  if (!mode) return <span className="pill" title="Mode unknown">unknown</span>;
  const cfg = MODE_CONFIG[mode] ?? {
    label: mode.toUpperCase(),
    cls: "pill",
    tooltip: `Mode: ${mode}`,
    icon: "?",
  };
  return (
    <span
      className={clsx("pill inline-flex items-center gap-1", cfg.cls)}
      title={cfg.tooltip}
      role="status"
      aria-label={`Data mode: ${cfg.label}. ${cfg.tooltip}`}
    >
      {showIcon && <span aria-hidden="true">{cfg.icon}</span>}
      <span>{cfg.label}</span>
    </span>
  );
}

export function ScopePill({ scope }: { scope: string }) {
  return (
    <span
      className={clsx("pill", scope === "client" ? "pill-warn" : "pill-ok")}
      title={
        scope === "client"
          ? "Client-uploaded data (CS3/CS4 only)"
          : "Public data, available to all modules"
      }
    >
      {scope}
    </span>
  );
}
