import { request } from "./client";

export interface ReferenceLab {
  lab_id: string;
  system: string;
  coverage: number;
  stake_style: "bold" | "ladder" | "flat";
  selection_kind: "ranking" | "parity";
  capital: number;
  goal: number;
  prizes: number[];
  window: { start: string; end: string };
  duration_cap: null;
  editable: false;
}
export interface ReferenceHistory {
  sha256: string;
  origin: "frozen_reference";
  draws: number;
  ranked_draws: number;
  first_label: string | null;
  last_label: string | null;
}
export interface ReferenceCapabilities { session_summary: true; per_bet_trace: false }
export interface ReferenceCatalog {
  contract_version: number;
  reference_history: ReferenceHistory;
  capabilities: ReferenceCapabilities;
  items: ReferenceLab[];
}
export interface ReferenceLabDetail {
  contract_version: number;
  reference_history: ReferenceHistory;
  capabilities: ReferenceCapabilities;
  lab: ReferenceLab;
}
export interface ReferenceTotals {
  completed: number;
  incomplete: number;
  goals: number;
  ruins: number;
  sessions_total: number;
  total_wagered: number;
  total_paid: number;
  total_net: number;
  total_steps: number;
  mean_net_closed: number | null;
}
export interface ReferenceRunSummary {
  eligible_draws: number;
  gaps: number;
  first: string | null;
  last: string | null;
  session_sha256: string;
  session_count: number;
  totals: ReferenceTotals;
}
export interface ReferenceRunListItem {
  id: string;
  lab_id: string;
  contract_version: number;
  created_at: string;
  summary: Pick<ReferenceRunSummary, "eligible_draws" | "gaps" | "totals">;
}
export interface ReferenceRun {
  id: string;
  lab_id: string;
  contract_version: number;
  created_at: string;
  config: ReferenceLab;
  provenance: { history_sha256: string; history_origin: "frozen"; [key: string]: unknown };
  summary: ReferenceRunSummary;
  capabilities: ReferenceCapabilities;
}
export interface ReferenceSession {
  outcome: "goal" | "ruin" | "incomplete";
  start_index: number;
  end_index: number;
  draws: number;
  final_balance: number;
  wagered: number;
  paid: number;
}
export interface ReferenceSessionPage {
  run_id: string;
  total: number;
  offset: number;
  limit: number;
  items: { ordinal: number; summary: ReferenceSession }[];
}
export interface ReferencePage<T> { total: number; offset: number; limit: number; items: T[] }
export interface PageParams { offset?: number; limit?: number }

function paging({ offset = 0, limit }: PageParams, defaultLimit: number): string {
  const resolvedLimit = limit ?? defaultLimit;
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(resolvedLimit) || resolvedLimit < 1 || resolvedLimit > 100) {
    throw new RangeError("La paginación debe usar un desplazamiento válido y un límite entre 1 y 100.");
  }
  return `offset=${offset}&limit=${resolvedLimit}`;
}

export function getReferenceLabs(options?: RequestInit): Promise<ReferenceCatalog> {
  return request("/reference-labs", options);
}
export function getReferenceLab(labId: string, options?: RequestInit): Promise<ReferenceLabDetail> {
  return request(`/reference-labs/${encodeURIComponent(labId)}`, options);
}
export function listReferenceRuns(labId: string, params: PageParams = {}, options?: RequestInit): Promise<ReferencePage<ReferenceRunListItem>> {
  return request(`/reference-labs/${encodeURIComponent(labId)}/runs?${paging(params, 20)}`, options);
}
export function createReferenceRun(labId: string, requiredHistorySha256: string, options?: RequestInit): Promise<ReferenceRun> {
  return request(`/reference-labs/${encodeURIComponent(labId)}/runs`, {
    ...options, method: "POST", body: JSON.stringify({ required_history_sha256: requiredHistorySha256 }),
  });
}
export function getReferenceRun(labId: string, runId: string, options?: RequestInit): Promise<ReferenceRun> {
  return request(`/reference-labs/${encodeURIComponent(labId)}/runs/${encodeURIComponent(runId)}`, options);
}
export function listReferenceSessions(labId: string, runId: string, params: PageParams = {}, options?: RequestInit): Promise<ReferenceSessionPage> {
  return request(`/reference-labs/${encodeURIComponent(labId)}/runs/${encodeURIComponent(runId)}/sessions?${paging(params, 50)}`, options);
}
export function deleteReferenceRun(labId: string, runId: string, options?: RequestInit): Promise<void> {
  return request(`/reference-labs/${encodeURIComponent(labId)}/runs/${encodeURIComponent(runId)}`, { ...options, method: "DELETE" });
}
