import { request } from "./client";
import type { SettingsResponse } from "./types";

const CANONICAL_BYTES = /^[1-9][0-9]{0,18}$/;
const SQLITE_MAX = 9223372036854775807n;

export function getSettings(options?: RequestInit): Promise<SettingsResponse> {
  return request("/settings", options);
}

export function updateSettings(quotaBytes: string, options?: RequestInit): Promise<SettingsResponse> {
  if (!CANONICAL_BYTES.test(quotaBytes) || BigInt(quotaBytes) > SQLITE_MAX) {
    throw new RangeError("La cuota debe ser una cadena decimal canónica de bytes.");
  }
  return request("/settings", {
    ...options,
    method: "PUT",
    body: JSON.stringify({ quota_bytes: quotaBytes }),
  });
}
