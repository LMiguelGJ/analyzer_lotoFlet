import { request } from "./client";
import type { ReferenceCapabilities, ReferencePage, ReferenceSessionPage, ReferenceTotals, PageParams } from "./referenceLabs";

export type StakeStyle = "bold" | "ladder" | "flat";

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
}
export interface LaboratoryDefinition {
  schema_version: number;
  id: string;
  name: string;
  reference_id: string | null;
  config: LaboratoryConfig;
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
export interface LaboratoryRunSummary {
  eligible_draws: number;
  gaps: number;
  first: string | null;
  last: string | null;
  session_sha256: string;
  session_count: number;
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

const MAX_SAFE = Number.MAX_SAFE_INTEGER;

function paging({ offset = 0, limit }: PageParams, defaultLimit: number): string {
  const resolvedLimit = limit ?? defaultLimit;
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(resolvedLimit) || resolvedLimit < 1 || resolvedLimit > 100) {
    throw new RangeError("La paginación debe usar un desplazamiento válido y un límite entre 1 y 100.");
  }
  return `offset=${offset}&limit=${resolvedLimit}`;
}
const base = (id: string) => `/laboratories/${encodeURIComponent(id)}`;

export function listLaboratories(params: PageParams = {}, options?: RequestInit): Promise<ReferencePage<LaboratoryDefinition>> {
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
