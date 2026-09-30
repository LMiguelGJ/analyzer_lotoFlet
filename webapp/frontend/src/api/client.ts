import type {
  Bet,
  Catalog,
  CompareResult,
  ConfigurationSummary,
  ExperimentRequest,
  ExperimentSummary,
  ExperimentStatus,
  Page,
  QueueStatus,
  SettingsView,
  Strategy,
} from "./types";

/** A single FastAPI/pydantic validation error entry, as sent in a 422 `detail` array. */
export interface ApiFieldError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

function isApiFieldError(value: unknown): value is ApiFieldError {
  return (
    !!value &&
    typeof value === "object" &&
    Array.isArray((value as ApiFieldError).loc) &&
    typeof (value as ApiFieldError).msg === "string" &&
    typeof (value as ApiFieldError).type === "string"
  );
}

/** A response the backend understood but rejected (400/403/404/409/422/507). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** Present only for a 422 whose `detail` was a pydantic field-error array. */
  readonly fieldErrors: ApiFieldError[] | null;

  constructor(status: number, detail: string, fieldErrors: ApiFieldError[] | null = null) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
  }
}

/**
 * The request never reached the server, or no response came back: the browser is
 * disconnected from the local server. This is distinct from ApiError: the UI must
 * never claim the server "stopped" for a case that might just be a dropped connection.
 * The dev proxy (vite.config.ts) also maps its own connection failures to this same
 * outcome by marking its error response with BACKEND_UNREACHABLE_HEADER.
 */
export class NetworkError extends Error {
  constructor() {
    super("No se pudo contactar al servidor local.");
    this.name = "NetworkError";
  }
}

const BASE_URL = "/api/v1";
export const BACKEND_UNREACHABLE_HEADER = "X-Laboratorio-Backend-Unreachable";
const INVALID_REQUEST_DETAIL = "La solicitud tiene datos inválidos.";
const UNEXPECTED_RESPONSE_DETAIL = "El servidor respondió con un formato inesperado.";

async function parseErrorBody(
  response: Response,
): Promise<{ detail: string; fieldErrors: ApiFieldError[] | null }> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const raw = (body as { detail: unknown }).detail;
      if (typeof raw === "string") {
        return { detail: raw, fieldErrors: null };
      }
      if (Array.isArray(raw) && raw.every(isApiFieldError)) {
        return { detail: INVALID_REQUEST_DETAIL, fieldErrors: raw };
      }
    }
  } catch {
    // no JSON body: fall through to the status text
  }
  return { detail: response.statusText || `HTTP ${response.status}`, fieldErrors: null };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    // A relative URL keeps every request same-origin, matching the backend's Host/Origin check.
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new NetworkError();
  }
  if (response.headers.get(BACKEND_UNREACHABLE_HEADER)) {
    // The dev proxy could not reach the backend at all: a disconnection, not a
    // real HTTP response from the API.
    throw new NetworkError();
  }
  if (!response.ok) {
    const { detail, fieldErrors } = await parseErrorBody(response);
    throw new ApiError(response.status, detail, fieldErrors);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, UNEXPECTED_RESPONSE_DETAIL);
  }
}

function query(params: Record<string, number | undefined>): string {
  const entries = Object.entries(params).filter((entry): entry is [string, number] => entry[1] !== undefined);
  if (entries.length === 0) return "";
  return `?${entries.map(([key, value]) => `${key}=${value}`).join("&")}`;
}

export interface ExperimentListParams {
  offset?: number;
  limit?: number;
  name_contains?: string;
  status?: ExperimentStatus;
  sort?: "created_at" | "name" | "status";
  order?: "asc" | "desc";
}

export interface CreateExperimentBody {
  request: ExperimentRequest;
  configuration_ids?: (string | null)[] | null;
}

export const apiClient = {
  getCatalog: () => request<Catalog>("/catalog"),

  getStartingDraws: (offset = 0, limit = 100) =>
    request<Page<string>>(`/catalog/starting-draws${query({ offset, limit })}`),

  createExperiment: (body: CreateExperimentBody) =>
    request<{ id: string; status: string }>("/experiments", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listExperiments: ({ offset = 0, limit = 20, name_contains, status, sort, order }: ExperimentListParams = {}) => {
    const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
    if (name_contains) params.set("name_contains", name_contains);
    if (status) params.set("status", status);
    if (sort) params.set("sort", sort);
    if (order) params.set("order", order);
    return request<Page<ExperimentSummary>>(`/experiments?${params}`);
  },

  getExperiment: (id: string) => request<ExperimentSummary>(`/experiments/${encodeURIComponent(id)}`),

  getReplay: (id: string, ordinal: number, offset = 0, limit = 20) =>
    request<Page<Bet>>(
      `/experiments/${encodeURIComponent(id)}/runs/${ordinal}/replay${query({ offset, limit })}`,
    ),

  compareExperiment: (id: string) => request<CompareResult>(`/experiments/${encodeURIComponent(id)}/compare`),

  deleteExperiment: (id: string, confirmId: string) =>
    request<void>(`/experiments/${encodeURIComponent(id)}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm_id: confirmId }),
    }),

  createConfiguration: (name: string, strategy: Strategy) =>
    request<ConfigurationSummary>("/configurations", {
      method: "POST",
      body: JSON.stringify({ name, strategy }),
    }),

  listConfigurations: (offset = 0, limit = 20) =>
    request<Page<ConfigurationSummary>>(`/configurations${query({ offset, limit })}`),

  getConfiguration: (id: string) => request<ConfigurationSummary>(`/configurations/${encodeURIComponent(id)}`),

  updateConfiguration: (id: string, name: string, strategy: Strategy) =>
    request<ConfigurationSummary>(`/configurations/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ name, strategy }),
    }),

  deleteConfiguration: (id: string, confirmId: string) =>
    request<void>(`/configurations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      body: JSON.stringify({ confirm_id: confirmId }),
    }),

  getQueue: (offset = 0, limit = 20) => request<QueueStatus>(`/queue${query({ offset, limit })}`),

  startHeld: (id: string) =>
    request<{ id: string; status: string }>(`/queue/${encodeURIComponent(id)}/start`, { method: "POST" }),

  cancelJob: (id: string) =>
    request<{ id: string; status: string }>(`/queue/${encodeURIComponent(id)}/cancel`, { method: "POST" }),

  getSettings: () => request<SettingsView>("/settings"),

  updateSettings: (quotaBytes: string) => request<SettingsView>("/settings", {
    method: "PUT",
    body: JSON.stringify({ quota_bytes: quotaBytes }),
  }),
};
