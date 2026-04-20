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
      <body className="min-h-screen bg-neutral-dark-bg text-neutral-white">
        <div className="flex min-h-screen">
          <aside className="w-64 shrink-0 border-r border-neutral-dark-secondary bg-neutral-black">
            <div className="p-4 border-b border-neutral-dark-secondary">
              <div className="text-sm font-semibold text-neutral-white">Deals Platform</div>
              <div className="text-xs text-neutral-dark-tertiary">PoC · offline mode</div>
            </div>
            <nav className="p-2 text-sm space-y-0.5">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="block px-2 py-1.5 rounded hover:bg-neutral-dark-secondary text-neutral-light-tertiary"
                >
                  {n.label}
                </Link>
              ))}
              <div className="h-px bg-neutral-dark-secondary my-2" />
              {NAV_SEC.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="block px-2 py-1.5 rounded hover:bg-neutral-dark-secondary text-neutral-dark-tertiary"
                >
                  {n.label}
                </Link>
              ))}
            </nav>
            <div className="p-3 text-[11px] text-neutral-dark-tertiary border-t border-neutral-dark-secondary">
              Every output is evidence-linked. No approvals without a reason.
            </div>
          </aside>
          <main className="flex-1 min-w-0 bg-neutral-dark-bg">{children}</main>
        </div>
      </body>
    </html>
  );
}
