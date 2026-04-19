import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Deals Platform",
  description: "AI-enabled M&A origination, carve-outs, post-deal tracker, WC diagnostic.",
};

const NAV = [
  { href: "/", label: "Home" },
  { href: "/origination", label: "CS1 · Origination" },
  { href: "/carve-outs", label: "CS2 · Carve-Outs" },
  { href: "/post-deal", label: "CS3 · Post-Deal" },
  { href: "/working-capital", label: "CS4 · Working Capital" },
];
const NAV_SEC = [
  { href: "/review-queue", label: "Review queue" },
  { href: "/sources", label: "Sources" },
  { href: "/settings", label: "Settings" },
  { href: "/eval", label: "Evaluation" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <aside className="w-64 shrink-0 border-r border-hairline bg-white">
            <div className="p-4 border-b border-hairline">
              <div className="text-sm font-semibold text-ink">Deals Platform</div>
              <div className="text-xs text-ink-muted">PoC · offline mode</div>
            </div>
            <nav className="p-2 text-sm space-y-0.5">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="block px-2 py-1.5 rounded hover:bg-paper text-ink-soft"
                >
                  {n.label}
                </Link>
              ))}
              <div className="h-px bg-hairline my-2" />
              {NAV_SEC.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="block px-2 py-1.5 rounded hover:bg-paper text-ink-muted"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <div className="p-3 text-[11px] text-ink-muted border-t border-hairline">
              Every output is evidence-linked. No approvals without a reason.
            </div>
          </aside>
          <main className="flex-1 min-w-0">{children}</main>
        </div>
      </body>
    </html>
  );
}
