// Mirrors of backend Pydantic schemas. Keep in sync with backend/app/models/schemas.py.

export type DataScope = "public" | "client";
export type SourceMode = "live" | "fixture" | "blocked";
export type ReviewState = "pending" | "accepted" | "rejected" | "edited" | "approved";

export interface EvidenceOut {
  id: string;
  source_id: string;
  scope: DataScope;
  mode: SourceMode;
  kind: string;
  title: string | null;
  snippet: string | null;
  url: string | null;
  file_ref: string | null;
  retrieved_at: string;
  parsed_at: string | null;
  published_at: string | null;
  ok: boolean;
}

export interface ReviewOut {
  state: ReviewState;
  reviewer: string | null;
  ts: string | null;
  reason: string | null;
}

export interface SituationOut {
  id: string;
  module: string;
  kind: string;
  company_id: string | null;
  segment_id: string | null;
  title: string;
  summary: string;
  next_action: string | null;
  caveats: string[];
  score: number;
  dimensions: Record<string, number>;
  weights: Record<string, number>;
  confidence: number;
  signal_ids: string[];
  evidence_ids: string[];
  evidence: EvidenceOut[];
  explanation: string;
  explanation_cites: string[];
  extras: Record<string, unknown>;
  review: ReviewOut;
  created_at: string;
}

export interface SectorHeatCell {
  sector: string;
  count: number;
  avg_score: number;
  top_situation_ids: string[];
}

export interface SourceHealthOut {
  id: string;
  name: string;
  mode: string;
  last_refresh_at: string | null;
  last_status: string | null;
  last_error: string | null;
}

export interface WeightsResponse {
  module: string;
  weights: Record<string, number>;
  defaults: Record<string, number>;
}

export interface CoverageResponse {
  [module: string]: Record<string, number>;
}
