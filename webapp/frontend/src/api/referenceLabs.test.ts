import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "./client";
import { createReferenceRun, getReferenceLabs, listReferenceSessions } from "./referenceLabs";

afterEach(() => vi.unstubAllGlobals());
const response = (body: unknown, status = 200) => new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("reference laboratory API", () => {
  it("uses exact fixed-history create payload, preserves abort signals, and accepts 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ id: "run", summary: {} }, 201));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    await createReferenceRun("transicion_1_audaz", "a".repeat(64), { signal: controller.signal });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/reference-labs/transicion_1_audaz/runs");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", signal: controller.signal, body: JSON.stringify({ required_history_sha256: "a".repeat(64) }) });
  });

  it("encodes lab and run IDs, requests only the visible session page, and rejects invalid bounds", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await listReferenceSessions("lab/x", "run ?", { offset: 50, limit: 100 });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/reference-labs/lab%2Fx/runs/run%20%3F/sessions?offset=50&limit=100");
    expect(() => listReferenceSessions("lab", "run", { limit: 101 })).toThrow(RangeError);
  });

  it("keeps API conflict distinct and does not retry an ambiguous network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(createReferenceRun("transicion_1_audaz", "b".repeat(64))).rejects.toBeInstanceOf(NetworkError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "La historia requerida no coincide." }, 409)));
    await expect(getReferenceLabs()).rejects.toMatchObject({ status: 409, detail: "La historia requerida no coincide." } satisfies Partial<ApiError>);
  });
});
