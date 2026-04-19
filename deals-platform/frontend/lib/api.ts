import type {
  CoverageResponse,
  SectorHeatCell,
  SituationOut,
  SourceHealthOut,
  WeightsResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${body}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export const api = {
  situations: (params: { module?: string; state?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.module) q.set("module", params.module);
    if (params.state) q.set("state", params.state);
    if (params.limit) q.set("limit", String(params.limit));
    return req<SituationOut[]>(`/situations${q.toString() ? `?${q}` : ""}`);
  },
  situation: (id: string) => req<SituationOut>(`/situations/${id}`),
  review: (id: string, body: Record<string, unknown>) =>
    req<SituationOut>(`/situations/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  heatmap: (module: string) =>
    req<SectorHeatCell[]>(`/situations/sector/heatmap?module=${module}`),
  sources: () => req<SourceHealthOut[]>("/sources"),
  refreshSource: (id: string) =>
    req<{ source: string; ingested: number }>(`/sources/${id}/refresh`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  weights: (module: string) => req<WeightsResponse>(`/settings/weights/${module}`),
  setWeights: (module: string, weights: Record<string, number>) =>
    req<WeightsResponse>(`/settings/weights/${module}`, {
      method: "PUT",
      body: JSON.stringify({ weights }),
    }),
  coverage: () => req<CoverageResponse>("/eval/coverage"),
  labels: () => req<{ total_reviews: number; rated: number; by_action: Record<string, number> }>(
    "/eval/labels",
  ),
  llm: () =>
    req<{ calls: number; offline: number; cost_usd: number; tokens_in: number; tokens_out: number }>(
      "/eval/llm",
    ),
  // Module-specific
  runOrigination: () => req<SituationOut[]>("/origination/run", { method: "POST" }),
  postDealKpis: () =>
    req<
      Array<{
        id: string;
        name: string;
        unit: string;
        curve: string;
        target_band_low: number | null;
        target_band_high: number | null;
        target_start: string | null;
        target_end: string | null;
        actuals: Array<[string, number]>;
        target_curve: Array<[string, number, number, number]>;
      }>
    >("/post-deal/kpis"),
  postDealCompute: () => req<SituationOut[]>("/post-deal/compute", { method: "POST" }),
  health: () => req<{ ok: boolean; live_llm: boolean; offline: boolean }>("/health"),
};

export { BASE as BACKEND_BASE };
