import { request } from "./client";
import type { HistoryImportResponse, HistoryResponse } from "./types";

export function getHistory(options?: RequestInit): Promise<HistoryResponse> {
  return request("/history", options);
}

/** Sends the file's raw JSON text as the POST body; the endpoint is not multipart. */
export function importHistory(rawJson: string, options?: RequestInit): Promise<HistoryImportResponse> {
  return request("/history", { ...options, method: "POST", body: rawJson });
}
