import { ScannerDashboard } from "@/components/ScannerDashboard";

export default function Page() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-neutral-white">Continuous Market Scanner (v2)</h1>
        <p className="text-sm text-neutral-light-tertiary mt-2 max-w-3xl">
          Real-time market scanning across S&P 500 + FTSE 100. Detects M&A origination opportunities
          ($1B+) and carve-out candidates ($750M+) via deterministic signals. No LLM during scanning;
          explanations generated on-demand when you review a situation.
        </p>
      </div>

      <ScannerDashboard />
    </div>
  );
}
