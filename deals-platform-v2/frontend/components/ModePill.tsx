import clsx from "clsx";

export function ModePill({ mode }: { mode: string | null | undefined }) {
  if (!mode) return <span className="pill">unknown</span>;
  const cls = clsx("pill", {
    "pill-mock": mode === "fixture" || mode === "never_refreshed",
    "pill-ok": mode === "live",
    "pill-risk": mode === "blocked",
  });
  return <span className={cls}>{mode}</span>;
}

export function ScopePill({ scope }: { scope: string }) {
  return (
    <span className={clsx("pill", scope === "client" ? "pill-warn" : "pill-ok")}>
      {scope}
    </span>
  );
}
