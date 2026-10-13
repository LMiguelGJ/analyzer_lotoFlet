import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "./client";
import {
  createLaboratory,
  createLaboratoryRun,
  deleteLaboratory,
  getLaboratory,
  getLaboratoryRun,
  listLaboratories,
  listLaboratoryRuns,
  listLaboratorySessions,
} from "./laboratories";

afterEach(() => vi.unstubAllGlobals());
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ID = "3f2b8c4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f";
const config = {
  schema_version: 1,
  system: "transition",
  coverage: 1,
  stake_style: "bold" as const,
  capital: 2000,
  goal: 2800,
  prizes: [80, 8, 4, 2, 1],
  window_start: "2025-09-02 05:10",
  window_end: "2026-09-25 18:20",
};

describe("managed laboratory API", () => {
  it("creates a laboratory with the exact name and config payload and keeps the abort signal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: ID }, 201));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    await createLaboratory("Mi laboratorio", config, { signal: controller.signal });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/laboratories");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({ name: "Mi laboratorio", config }),
    });
  });

  it("lists and reads laboratories with bounded paging and encoded identifiers", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => response({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await listLaboratories({ offset: 20, limit: 100 });
    await getLaboratory("a/b");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/laboratories?offset=20&limit=100");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/laboratories/a%2Fb");
    expect(() => listLaboratories({ limit: 101 })).toThrow(RangeError);
    expect(() => listLaboratories({ offset: -1 })).toThrow(RangeError);
  });

  it("deletes with the confirmed run count in the body and rejects unsafe counts", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: ID }));
    vi.stubGlobal("fetch", fetchMock);
    await deleteLaboratory(ID, 3);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/laboratories/${ID}`);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "DELETE", body: JSON.stringify({ confirmed_run_count: 3 }) });
    expect(() => deleteLaboratory(ID, -1)).toThrow(RangeError);
    expect(() => deleteLaboratory(ID, 1.5)).toThrow(RangeError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("runs, lists and reads results only through the owning laboratory routes", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => response({ items: [] }, 200));
    vi.stubGlobal("fetch", fetchMock);
    await createLaboratoryRun(ID, "a".repeat(64));
    await listLaboratoryRuns(ID, { offset: 0, limit: 20 });
    await getLaboratoryRun(ID, "run ?");
    await listLaboratorySessions(ID, "run ?", { offset: 50, limit: 50 });
    const urls = fetchMock.mock.calls.map((call) => call[0]);
    expect(urls).toEqual([
      `/api/v1/laboratories/${ID}/runs`,
      `/api/v1/laboratories/${ID}/runs?offset=0&limit=20`,
      `/api/v1/laboratories/${ID}/runs/run%20%3F`,
      `/api/v1/laboratories/${ID}/runs/run%20%3F/sessions?offset=50&limit=50`,
    ]);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify({ required_history_sha256: "a".repeat(64) }) });
  });

  it("keeps conflicts distinct and never retries an ambiguous network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(createLaboratoryRun(ID, "b".repeat(64))).rejects.toBeInstanceOf(NetworkError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "El laboratorio cambió; recárgalo antes de eliminarlo." }, 409)));
    await expect(deleteLaboratory(ID, 2)).rejects.toMatchObject({ status: 409, detail: "El laboratorio cambió; recárgalo antes de eliminarlo." } satisfies Partial<ApiError>);
  });
});
