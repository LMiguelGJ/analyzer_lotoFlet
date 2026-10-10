import { afterEach, describe, expect, it, vi } from "vitest";
import { getRunOptions, listRuns, getRun, createRun, deleteRun, listRunSessions, listSessionBets } from "./runs";
import { getHistory, importHistory } from "./history";
import { getSettings, updateSettings } from "./settings";
import type { CreateRunRequest } from "./types";

const ok = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("typed API resources", () => {
  it("uses run pagination defaults and URL-encodes query values", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(ok({ total: 0, offset: 0, limit: 20, items: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await listRuns();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/runs?offset=0&limit=20");
    await listRunSessions("run/a ?", { outcome: "incomplete" });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/runs/run%2Fa%20%3F/sessions?offset=0&limit=50&outcome=incomplete");
    await listSessionBets("run/a", 2);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/runs/run%2Fa/sessions/2/bets?offset=0&limit=20");
  });

  it("accepts the backend's maximum page size and rejects larger requests", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(ok({ total: 0, offset: 0, limit: 100, items: [] })));
    vi.stubGlobal("fetch", fetchMock);
    await listRuns({ limit: 100 });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/runs?offset=0&limit=100");
    expect(() => listRuns({ limit: 101 })).toThrow(RangeError);
  });

  it("exposes options/get/create/delete and preserves 204 semantics", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(ok({ systems: [], defaults: {}, limits: {}, history: {} }))
      .mockResolvedValueOnce(ok({ id: "x" }))
      .mockResolvedValueOnce(ok({ id: "x" }, 201))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await getRunOptions();
    await getRun("run/a");
    const body: CreateRunRequest = { history_sha256: "a".repeat(64) };
    await createRun(body);
    await expect(deleteRun("run/a")).resolves.toBeUndefined();
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/runs/options", "/api/v1/runs/run%2Fa", "/api/v1/runs", "/api/v1/runs/run%2Fa",
    ]);
    expect(fetchMock.mock.calls[2][1]).toMatchObject({ method: "POST", body: JSON.stringify(body) });
    expect(fetchMock.mock.calls[3][1]).toMatchObject({ method: "DELETE" });
  });

  it("uploads the raw JSON document and exposes history read/import", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(ok({ active: {}, sources: [] })).mockResolvedValueOnce(ok({ created: true, added: 1, active: {} }, 201));
    vi.stubGlobal("fetch", fetchMock);
    await getHistory();
    const raw = '{"metadata":{},"sorteos_por_fecha":{}}';
    await importHistory(raw);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/history");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", body: raw, headers: { "Content-Type": "application/json" } });
    expect(fetchMock.mock.calls[1][1]?.body).not.toBeInstanceOf(FormData);
  });

  it("keeps quota bytes as a canonical decimal string", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(ok({ quota: { effective_bytes: "9007199254740993" } })).mockResolvedValueOnce(ok({ quota: { effective_bytes: "9007199254740993" } }));
    vi.stubGlobal("fetch", fetchMock);
    await getSettings();
    await updateSettings("9007199254740993");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "PUT", body: '{"quota_bytes":"9007199254740993"}' });
    expect(() => updateSettings("090")).toThrow(RangeError);
  });

  it("preserves API errors and AbortError instead of relabeling cancellation", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ detail: "No existe" }), { status: 404 })).mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(getRun("x")).rejects.toMatchObject({ name: "ApiError", status: 404, detail: "No existe" });
    await expect(getRun("x", { signal: AbortSignal.abort() })).rejects.toMatchObject({ name: "AbortError" });
  });
});
