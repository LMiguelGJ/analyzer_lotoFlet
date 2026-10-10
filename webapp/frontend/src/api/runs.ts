import { request } from "./client";
import type { CreateRunRequest, Page, RunOptions, RunReport, RunSession, RunOutcome, SessionBetsPage } from "./types";

export interface PageParams { offset?: number; limit?: number }
export interface SessionParams extends PageParams { outcome?: RunOutcome }

function paging(params: PageParams, defaultLimit: number): string {
  const { offset = 0, limit = defaultLimit } = params;
  const resolvedLimit = limit;
  if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(resolvedLimit) || resolvedLimit < 1 || resolvedLimit > 100) {
    throw new RangeError("La paginación debe usar un desplazamiento válido y un límite entre 1 y 100.");
  }
  return `offset=${offset}&limit=${resolvedLimit}`;
}

export function getRunOptions(options?: RequestInit): Promise<RunOptions> {
  return request("/runs/options", options);
}

export function listRuns(params: PageParams = {}, options?: RequestInit): Promise<Page<RunReport>> {
  const query = paging(params, 20);
  return request(`/runs?${query}`, options);
}

export function getRun(runId: string, options?: RequestInit): Promise<RunReport> {
  return request(`/runs/${encodeURIComponent(runId)}`, options);
}

export function createRun(body: CreateRunRequest, options?: RequestInit): Promise<RunReport> {
  return request("/runs", { ...options, method: "POST", body: JSON.stringify(body) });
}

export function deleteRun(runId: string, options?: RequestInit): Promise<void> {
  return request(`/runs/${encodeURIComponent(runId)}`, { ...options, method: "DELETE" });
}

export function listRunSessions(runId: string, params: SessionParams = {}, options?: RequestInit): Promise<Page<RunSession>> {
  const { outcome, ...page } = params;
  const query = new URLSearchParams(paging(page, 50));
  if (outcome) query.set("outcome", outcome);
  return request(`/runs/${encodeURIComponent(runId)}/sessions?${query.toString()}`, options);
}

export function listSessionBets(runId: string, ordinal: number, params: PageParams = {}, options?: RequestInit): Promise<SessionBetsPage> {
  if (!Number.isSafeInteger(ordinal) || ordinal < 1) throw new RangeError("La sesión debe ser un ordinal positivo.");
  const query = paging(params, 20);
  return request(`/runs/${encodeURIComponent(runId)}/sessions/${ordinal}/bets?${query}`, options);
}
