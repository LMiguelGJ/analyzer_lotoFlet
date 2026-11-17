import { request } from "./client";
import type { NumberListInfo } from "./types";

export function getLists(options?: RequestInit): Promise<NumberListInfo[]> {
  return request("/lists", options);
}

export function setActiveList(id: string, options?: RequestInit): Promise<NumberListInfo[]> {
  return request("/lists/active", { ...options, method: "PUT", body: JSON.stringify({ id }) });
}

/** `null` restores the list's original prizes. */
export function setListPrizes(id: string, prizes: number[] | null, options?: RequestInit): Promise<NumberListInfo[]> {
  return request(`/lists/${encodeURIComponent(id)}/prizes`, { ...options, method: "PUT", body: JSON.stringify({ prizes }) });
}
