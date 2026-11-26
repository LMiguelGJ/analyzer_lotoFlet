import { request } from "./client";
import type { SystemOption } from "./types";
import type { ReferenceCapabilities, ReferencePage, ReferenceSessionPage, ReferenceTotals, PageParams } from "./referenceLabs";

export type StakeStyle = "bold" | "ladder" | "flat" | "martingale" | "paroli" | "dalembert" | "fibonacci" | "oscars_grind";

/** Optional overrides of the ranking system of a lab (absent = the fixed defaults). Not for Chance Express. */
export interface RankingParams {
  /** Draws of the window (freq_recent, freq_hist, digits). */
  window?: number | null;
  /** Draws of the fallback window (transition). */
  fallback_window?: number;
  /** Half-life in draws (decay). */
  half_life?: number;
  /** Which prize positions count (cold, freq_hist). */
  scope?: "position" | "any";
  /** Ensemble voters (at least two of the seven rankings). */
  components?: string[];
  component_params?: Record<string, Record<string, unknown>>;
  /** Equal scores: fixed order (default) or a seeded permutation per draw. */
  tie_break?: "fixed" | "seeded";
}

export interface LaboratoryConfig {
  schema_version: number;
  system: string;
  coverage: number;
  stake_style: StakeStyle;
  capital: number;
  goal: number;
  prizes: number[];
  window_start: string;
  window_end: string;
  /** Optional deadline in draws per session (one draw per day on Leidsa); absent = no limit. */
  max_session_draws?: number;
  /** Optional bank cap: no number receives more than this per draw; absent = no cap. */
  max_stake_per_number?: number;
  /** Optional ranking overrides (window, half-life, scope, components, tie-break). */
  ranking_params?: RankingParams;
  /** Stake rules: absent = 1 (historical); 2 = corrected ladder and progressions (new labs send 2). */
  stake_rules?: 1 | 2;
}
export interface LaboratoryDefinition {
  schema_version: number;
  id: string;
  name: string;
  reference_id: string | null;
  config: LaboratoryConfig;
}
/** Totals of a laboratory's most recent saved run, as the list reports them. */
export interface LaboratoryLastRun {
  id: string;
  created_at: string;
  total_net: number;
  total_wagered: number;
  total_paid: number;
}
/** A list item: the definition plus its latest run result (null/absent: never run). */
export interface LaboratoryListItem extends LaboratoryDefinition {
  last_run?: LaboratoryLastRun | null;
}
export interface LaboratoryDetail {
  definition: LaboratoryDefinition;
  owned_run_count: number;
  owned_session_count: number;
}
export interface LaboratoryDeleted {
  id: string;
  name: string;
  [key: string]: unknown;
}
export interface LaboratoryWallet {
  policy: "retain-gains-top-up-v1";
  out_of_pocket: number;
  final_wealth: number;
}
/** Result of the sessions that closed in one calendar year; the open session counts in its last draw's year. */
export interface LaboratoryYearResult {
  year: number;
  net: number;
  goals: number;
  ruins: number;
  timeouts: number;
  sessions_closed: number;
  /** Percentage points of the starting capital. */
  return_pct: number;
}
export interface LaboratoryRunSummary {
  eligible_draws: number;
  gaps: number;
  first: string | null;
  last: string | null;
  session_sha256: string;
  session_count: number;
  wallet?: LaboratoryWallet;
  /** Computed on read; null when the history no longer matches the run, absent on older servers. */
  by_year?: LaboratoryYearResult[] | null;
  totals: ReferenceTotals;
}
export interface LaboratoryRun {
  id: string;
  owner_laboratory_id: string;
  lab_id: string;
  contract_version: number;
  created_at: string;
  snapshot: {
    schema_version: number;
    kind: "owned_laboratory_run";
    definition: LaboratoryDefinition;
    provenance: { history_sha256: string; rankings_sha256: string; history_origin: "frozen" };
  };
  summary: LaboratoryRunSummary;
  capabilities: ReferenceCapabilities;
}
export interface LaboratoryRunListItem {
  id: string;
  created_at: string;
  summary: Pick<LaboratoryRunSummary, "eligible_draws" | "gaps" | "totals">;
  [key: string]: unknown;
}

/** GET /laboratories/options: what a new laboratory can use on the active list. */
export interface LaboratoryOptions {
  list: { id: string; name: string; positions: number };
  systems: SystemOption[];
  prizes: number[];
  window: { start: string | null; end: string | null };
  history_sha256: string;
  /** Stake styles the server offers; older servers omit it and the form uses its local map. */
  stake_styles?: { id: string; label: string }[];
}

const MAX_SAFE = Number.MAX_SAFE_INTEGER;

/** Backend ceiling per page (laboratorio.storage.paging.MAX_PAGE_SIZE). */
export const MAX_PAGE_SIZE = 500;
function paging({ offset = 0, limit }: PageParams, defaultLimit: number): string {
  const resolvedLimit = limit ?? defaultLimit;
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(resolvedLimit) || resolvedLimit < 1 || resolvedLimit > MAX_PAGE_SIZE) {
    throw new RangeError("La paginación debe usar un desplazamiento válido y un límite entre 1 y 500.");
  }
  return `offset=${offset}&limit=${resolvedLimit}`;
}
const base = (id: string) => `/laboratories/${encodeURIComponent(id)}`;

export function getLaboratoryOptions(options?: RequestInit): Promise<LaboratoryOptions> {
  return request("/laboratories/options", options);
}
export function listLaboratories(params: PageParams = {}, options?: RequestInit): Promise<ReferencePage<LaboratoryListItem>> {
  return request(`/laboratories?${paging(params, 20)}`, options);
}
export function createLaboratory(name: string, config: LaboratoryConfig, options?: RequestInit): Promise<LaboratoryDefinition> {
  return request("/laboratories", { ...options, method: "POST", body: JSON.stringify({ name, config }) });
}
export function getLaboratory(id: string, options?: RequestInit): Promise<LaboratoryDetail> {
  return request(base(id), options);
}
export function deleteLaboratory(id: string, confirmedRunCount: number, options?: RequestInit): Promise<LaboratoryDeleted> {
  if (!Number.isSafeInteger(confirmedRunCount) || confirmedRunCount < 0 || confirmedRunCount > MAX_SAFE) {
    throw new RangeError("El número de corridas a eliminar debe ser un entero no negativo.");
  }
  return request(base(id), { ...options, method: "DELETE", body: JSON.stringify({ confirmed_run_count: confirmedRunCount }) });
}
export function listLaboratoryRuns(id: string, params: PageParams = {}, options?: RequestInit): Promise<ReferencePage<LaboratoryRunListItem>> {
  return request(`${base(id)}/runs?${paging(params, 20)}`, options);
}
export function createLaboratoryRun(id: string, requiredHistorySha256: string, options?: RequestInit): Promise<LaboratoryRun> {
  return request(`${base(id)}/runs`, { ...options, method: "POST", body: JSON.stringify({ required_history_sha256: requiredHistorySha256 }) });
}
export function getLaboratoryRun(id: string, runId: string, options?: RequestInit): Promise<LaboratoryRun> {
  return request(`${base(id)}/runs/${encodeURIComponent(runId)}`, options);
}
export function listLaboratorySessions(id: string, runId: string, params: PageParams = {}, options?: RequestInit): Promise<ReferenceSessionPage> {
  return request(`${base(id)}/runs/${encodeURIComponent(runId)}/sessions?${paging(params, 50)}`, options);
}
