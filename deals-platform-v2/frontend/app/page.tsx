import Link from "next/link";

const MODULES = [
  {
    href: "/origination",
    tag: "CS1",
    tagTooltip: "Case Study 1 — M&A target origination",
    title: "M&A Origination",
    blurb:
      "Ranks public-company targets above a $1bn equity threshold on a 12–24m horizon using filings, news, and market signals.",
    scope: "Public only",
  },
  {
    href: "/carve-outs",
    tag: "CS2",
    tagTooltip: "Case Study 2 — distressed-portfolio carve-out detection",
    title: "Carve-Out Detection",
    blurb:
      "Scores segment-level divestiture readiness for groups above $750m equity on a 6–18m horizon, with a break-up tree.",
    scope: "Public only",
  },
  {
    href: "/post-deal",
    tag: "CS3",
    tagTooltip: "Case Study 3 — post-deal value tracking for completed acquisitions",
    title: "Post-Deal Value Tracker",
    blurb:
      "Uploaded deal cases vs trend-bands with deviation flags, interventions, and per-KPI review.",
    scope: "Uploaded + public context",
  },
  {
    href: "/working-capital",
    tag: "CS4",
    tagTooltip: "Case Study 4 — working-capital diagnostic (DSO/DPO/DIO)",
    title: "Working Capital Diagnostic",
    blurb:
      "DSO / DPO / DIO against XBRL peer benchmarks with cash-opportunity bands on a 3–9m horizon.",
    scope: "Uploaded + public benchmarks",
  },
];

export default function Page() {
  return (
    <div className="p-8 max-w-5xl">
      <h1 className="text-2xl font-semibold text-neutral-white">Deals Platform</h1>
      <p className="text-sm text-neutral-light-tertiary mt-1 max-w-2xl">
        One product, four modules for professional-services M&A work. Each surfaces a
        ranked list of evidence-linked situations with human-in-the-loop review.
      </p>
      <div className="grid md:grid-cols-2 gap-3 mt-6">
        {MODULES.map((m) => (
          <Link key={m.href} href={m.href} className="panel p-4 hover:bg-neutral-dark-secondary block">
            <div className="flex items-center gap-2">
              <span className="pill cursor-help" title={m.tagTooltip}>{m.tag}</span>
              <div className="text-lg font-semibold text-neutral-white">{m.title}</div>
            </div>
            <div className="text-sm text-neutral-light-tertiary mt-2">{m.blurb}</div>
            <div className="text-xs text-neutral-dark-tertiary mt-2">Data scope: {m.scope}</div>
          </Link>
        ))}
      </div>
      <div className="mt-8 text-sm text-neutral-light-tertiary max-w-2xl">
        Shared spine: evidence store, scoring engine, explain layer, review queue.
        All data scopes are enforced at both import-time (segregation tests) and
        row-level (Evidence.scope).
      </div>
    </div>
  );
}
