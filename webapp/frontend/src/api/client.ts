/** A single FastAPI/pydantic validation error entry, as sent in a 422 `detail` array. */
import type { ApiFieldError } from "./types";
export type { ApiFieldError } from "./types";

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

function isAbortError(error: unknown): boolean {
  return !!error && typeof error === "object" && "name" in error && error.name === "AbortError";
}

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
  } catch (error) {
    if (isAbortError(error)) throw error;
    // malformed/no JSON body: fall through to the status text
  }
  return { detail: response.statusText || `HTTP ${response.status}`, fieldErrors: null };
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    // A relative URL keeps every request same-origin, matching the backend's Host/Origin check.
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
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
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(response.status, UNEXPECTED_RESPONSE_DETAIL);
  }
}
