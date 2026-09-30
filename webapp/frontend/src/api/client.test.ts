import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError, NetworkError } from "./client";
import settingsFixture from "./__fixtures__/settings.json";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiClient error mapping", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it.each([400, 403, 404, 409, 422, 507])(
    "maps HTTP %i to an ApiError with that status and detail",
    async (status: number) => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(status, { detail: `error ${status}` }));

      await expect(apiClient.getCatalog()).rejects.toMatchObject(new ApiError(status, `error ${status}`));
    },
  );

  it("falls back to the status text when the error body has no detail", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response("not json", { status: 500, statusText: "Internal Server Error" }),
    );

    await expect(apiClient.getCatalog()).rejects.toMatchObject({
      status: 500,
      detail: "Internal Server Error",
    });
  });

  it("maps a fetch rejection to NetworkError, never claiming the server stopped", async () => {
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
    expect((error as Error).message).not.toMatch(/detuvo|stopped/i);
  });

  it("resolves with the parsed JSON body on success", async () => {
    const catalog = { game: { name: "Quiniela 80" } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, catalog));

    await expect(apiClient.getCatalog()).resolves.toEqual(catalog);
  });

  it("resolves with undefined on a 204 No Content", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(apiClient.deleteExperiment("abc", "abc")).resolves.toBeUndefined();
  });

  it("requests same-origin relative URLs under /api/v1", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}));

    await apiClient.getCatalog();

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(String(url)).toBe("/api/v1/catalog");
  });

  it("encodes server-side experiment filters, ordering and bounded offset without interpreting Unicode", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { total: 0, offset: 20, limit: 20, items: [] }));
    await apiClient.listExperiments({ offset: 20, limit: 20, name_contains: "Fríos & 50%", status: "running", sort: "name", order: "asc" });
    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe(
      "/api/v1/experiments?offset=20&limit=20&name_contains=Fr%C3%ADos+%26+50%25&status=running&sort=name&order=asc",
    );
  });

  it("sends confirm_id tied to the target resource on delete", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await apiClient.deleteExperiment("exp-1", "exp-1");

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({ confirm_id: "exp-1" });
  });

  it("encodes a path id that contains reserved URL characters", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}));

    await apiClient.getExperiment("a/b c");

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(String(url)).toBe(`/api/v1/experiments/${encodeURIComponent("a/b c")}`);
  });

  it("parses a FastAPI 422 array detail into field errors with a Spanish generic message", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      jsonResponse(422, {
        detail: [
          { type: "missing", loc: ["body", "request", "conditions"], msg: "Field required" },
          { type: "missing", loc: ["body", "request", "strategies"], msg: "Field required" },
        ],
      }),
    );

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.detail).not.toMatch(/loc|msg|type/);
    expect(apiError.fieldErrors).toEqual([
      { type: "missing", loc: ["body", "request", "conditions"], msg: "Field required" },
      { type: "missing", loc: ["body", "request", "strategies"], msg: "Field required" },
    ]);
  });

  it("still supports a plain string detail (no field errors)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(400, { detail: "start draw has no ranking" }));

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).fieldErrors).toBeNull();
    expect((error as ApiError).detail).toBe("start draw has no ranking");
  });

  it("maps a 2xx response with a non-JSON body to a typed ApiError, not a raw SyntaxError", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response("not json", { status: 200, headers: { "Content-Type": "text/plain" } }),
    );

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).not.toBeInstanceOf(SyntaxError);
  });

  it("GET and PUT settings use the full view, exact string payload and same-origin URL", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, settingsFixture)).mockResolvedValueOnce(jsonResponse(200, {
      ...settingsFixture, quota: { effective_bytes: "9223372036854775807", persisted_bytes: "9223372036854775807", source: "persisted", writable: true },
    }));
    await expect(apiClient.getSettings()).resolves.toEqual(settingsFixture);
    const updated = await apiClient.updateSettings("9223372036854775807");
    expect(updated.quota.effective_bytes).toBe("9223372036854775807");
    expect(updated.quota.persisted_bytes).toBe("9223372036854775807");
    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe("/api/v1/settings");
    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[1];
    expect(url).toBe("/api/v1/settings");
    expect(init?.method).toBe("PUT");
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(init?.body).toBe('{"quota_bytes":"9223372036854775807"}');
  });

  it("encodes queue action IDs, sends POST without a body, and reads acknowledgements only", async () => {
    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce(jsonResponse(200, { id: "a/b c", status: "queued" }))
      .mockResolvedValueOnce(jsonResponse(200, { id: "a/b c", status: "cancellation_requested" }));
    await expect(apiClient.startHeld("a/b c")).resolves.toEqual({ id: "a/b c", status: "queued" });
    await expect(apiClient.cancelJob("a/b c")).resolves.toEqual({ id: "a/b c", status: "cancellation_requested" });
    const calls = vi.mocked(globalThis.fetch).mock.calls;
    expect(calls.map(([url]) => url)).toEqual([
      "/api/v1/queue/a%2Fb%20c/start", "/api/v1/queue/a%2Fb%20c/cancel",
    ]);
    expect(calls.every(([, init]) => init?.method === "POST" && init.body === undefined)).toBe(true);
  });

  it("maps a proxy-marked disconnection response to NetworkError instead of ApiError", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "unreachable" }), {
        status: 502,
        headers: { "X-Laboratorio-Backend-Unreachable": "1", "Content-Type": "application/json" },
      }),
    );

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
  });
});
