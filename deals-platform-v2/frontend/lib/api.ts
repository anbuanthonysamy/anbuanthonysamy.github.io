import type {
  CoverageResponse,
  SectorHeatCell,
  SituationOut,
  SituationV2,
  SourceHealthOut,
  WeightsResponse,
} from "./types";

const STATIC_BASE = process.env.NEXT_PUBLIC_STATIC_API_BASE;
const LIVE_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Mutation =
  | "review"
  | "refreshSource"
  | "setWeights"
  | "runOrigination"
  | "postDealCompute";

function staticReadOnlyError(name: Mutation): Error {
  return new Error(
    `This is a read-only demo build. '${name}' requires a live backend. ` +
      `Run 'make demo' locally to exercise the write path.`,
  );
}

async function liveReq<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${LIVE_BASE}${path}`, {
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

async function staticReq<T>(resource: string): Promise<T> {
  const res = await fetch(`${STATIC_BASE}/${resource}.json`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Static API ${res.status} ${resource}`);
  }
  return (await res.json()) as T;
}

const isStatic = Boolean(STATIC_BASE);

export const api = {
  situations: async (
    params: { module?: string; state?: string; limit?: number } = {},
  ): Promise<SituationOut[]> => {
    if (!isStatic) {
      const q = new URLSearchParams();
      if (params.module) q.set("module", params.module);
      if (params.state) q.set("state", params.state);
      if (params.limit) q.set("limit", String(params.limit));
      return liveReq<SituationOut[]>(`/situations${q.toString() ? `?${q}` : ""}`);
    }
    const modules = params.module
      ? [params.module]
      : ["origination", "carve_outs", "post_deal", "working_capital"];
    const lists = await Promise.all(
      modules.map((m) => staticReq<SituationOut[]>(`situations_${m}`).catch(() => [])),
    );
    let merged: SituationOut[] = lists.flat();
    if (params.state) merged = merged.filter((s) => s.review?.state === params.state);
    merged.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    if (params.limit) merged = merged.slice(0, params.limit);
    return merged;
  },
  situation: async (id: string): Promise<SituationOut> => {
    if (!isStatic) return liveReq<SituationOut>(`/situations/${id}`);
    const all = await api.situations({});
    const hit = all.find((s) => s.id === id);
    if (!hit) throw new Error(`Situation ${id} not found in static demo`);
    return hit;
  },
  review: async (id: string, body: Record<string, unknown>): Promise<SituationOut> => {
    if (!isStatic)
      return liveReq<SituationOut>(`/situations/${id}/review`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    throw staticReadOnlyError("review");
  },
  heatmap: async (module: string): Promise<SectorHeatCell[]> => {
    if (!isStatic)
      return liveReq<SectorHeatCell[]>(`/situations/sector/heatmap?module=${module}`);
    return staticReq<SectorHeatCell[]>(`heatmap_${module}`).catch(() => []);
  },
  sources: async (): Promise<SourceHealthOut[]> => {
    if (!isStatic) return liveReq<SourceHealthOut[]>("/sources");
    return staticReq<SourceHealthOut[]>("sources");
  },
  refreshSource: async (id: string) => {
    if (!isStatic)
      return liveReq<{ source: string; ingested: number }>(`/sources/${id}/refresh`, {
        method: "POST",
        body: JSON.stringify({}),
      });
    throw staticReadOnlyError("refreshSource");
  },
  weights: async (module: string): Promise<WeightsResponse> => {
    if (!isStatic) return liveReq<WeightsResponse>(`/settings/weights/${module}`);
    return staticReq<WeightsResponse>(`weights_${module}`);
  },
  setWeights: async (module: string, weights: Record<string, number>) => {
    if (!isStatic)
      return liveReq<WeightsResponse>(`/settings/weights/${module}`, {
        method: "PUT",
        body: JSON.stringify({ weights }),
      });
    throw staticReadOnlyError("setWeights");
  },
  coverage: async (): Promise<CoverageResponse> => {
    if (!isStatic) return liveReq<CoverageResponse>("/eval/coverage");
    return staticReq<CoverageResponse>("coverage");
  },
  labels: async () => {
    if (!isStatic)
      return liveReq<{ total_reviews: number; rated: number; by_action: Record<string, number> }>(
        "/eval/labels",
      );
    return staticReq<{
      total_reviews: number;
      rated: number;
      by_action: Record<string, number>;
    }>("labels");
  },
  llm: async () => {
    if (!isStatic)
      return liveReq<{
        calls: number;
        offline: number;
        cost_usd: number;
        tokens_in: number;
        tokens_out: number;
      }>("/eval/llm");
    return staticReq<{
      calls: number;
      offline: number;
      cost_usd: number;
      tokens_in: number;
      tokens_out: number;
    }>("llm");
  },
  runOrigination: async () => {
    if (!isStatic) return liveReq<SituationOut[]>("/origination/run", { method: "POST" });
    throw staticReadOnlyError("runOrigination");
  },
  postDealKpis: async () => {
    type Row = {
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
    };
    if (!isStatic) return liveReq<Row[]>("/post-deal/kpis");
    return staticReq<Row[]>("post_deal_kpis");
  },
  postDealCompute: async () => {
    if (!isStatic) return liveReq<SituationOut[]>("/post-deal/compute", { method: "POST" });
    throw staticReadOnlyError("postDealCompute");
  },
  health: async () => {
    if (!isStatic) return liveReq<{ ok: boolean; live_llm: boolean; offline: boolean }>("/health");
    return staticReq<{ ok: boolean; live_llm: boolean; offline: boolean }>("health");
  },
  triggerScan: async (apiMode: "live" | "offline", geography: "worldwide" | "uk_only") => {
    if (!isStatic) {
      return liveReq<{
        status: string;
        timestamp: string;
        geography: string;
        counts: Record<string, number>;
        total: number;
      }>(`/api/v2/scan/run?api_mode=${apiMode}&geography=${geography}`, { method: "POST" });
    }
    throw staticReadOnlyError("triggerScan");
  },
  situationsV2: async (params: {
    module?: string;
    tier?: string;
    new_since?: string;
    sort_by?: string;
    limit?: number;
    offset?: number;
  } = {}) => {
    if (!isStatic) {
      const q = new URLSearchParams();
      if (params.module) q.set("module", params.module);
      if (params.tier) q.set("tier", params.tier);
      if (params.new_since) q.set("new_since", params.new_since);
      if (params.sort_by) q.set("sort_by", params.sort_by || "priority");
      if (params.limit) q.set("limit", String(params.limit || 50));
      if (params.offset) q.set("offset", String(params.offset || 0));
      return liveReq<{
        total: number;
        limit: number;
        offset: number;
        situations: SituationV2[];
      }>(`/api/v2/scan/situations${q.toString() ? `?${q}` : ""}`);
    }
    throw staticReadOnlyError("situationsV2");
  },
  situationV2: async (id: string) => {
    if (!isStatic) {
      return liveReq<SituationV2>(`/api/v2/scan/situations/${id}`);
    }
    throw staticReadOnlyError("situationV2");
  },
  generateExplanation: async (id: string) => {
    if (!isStatic) {
      return liveReq<{ id: string; explanation: string; cached: boolean }>(
        `/api/v2/scan/situations/${id}/explain`,
        { method: "POST" },
      );
    }
    throw staticReadOnlyError("generateExplanation");
  },
};

export { LIVE_BASE as BACKEND_BASE };
