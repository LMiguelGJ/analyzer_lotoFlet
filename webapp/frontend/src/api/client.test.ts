import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError, NetworkError } from "./client";
import settingsFixture from "./__fixtures__/settings.json";
import type { ProfileAudazRequest, ProfileExperimentRequest, ProfileRecoveryRequest } from "./types";

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

  it("requests a bounded whole-run trajectory with an encoded identifier", async () => {
    const trajectory = { total: 1001, points: [], reduction_method: "minmax-even-v1" };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, trajectory));
    await expect(apiClient.getTrajectory("a/b", 2, 500)).resolves.toEqual(trajectory);
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/v1/experiments/a%2Fb/runs/2/trajectory?max_points=500", expect.anything());
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

  it("reads bounded profiles and partial template metadata without a write request", async () => {
    const page = {
      total: 1, offset: 0, limit: 20,
      items: [{ profile: { profile_id: "legacy-quiniela-80", revision: 1 }, execution_supported: true }],
      templates: [{ name: "Original70", known_fields: { universe_size: 100 },
        missing_fields: ["maximum_stake"], execution_supported: false }],
    };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, page))
      .mockResolvedValueOnce(jsonResponse(200, { ...page, offset: 2, limit: 1, items: [] }));
    await expect(apiClient.getProfiles()).resolves.toEqual(page);
    await expect(apiClient.getProfiles(2, 1)).resolves.toMatchObject({ offset: 2, limit: 1, items: [] });
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/catalog/profiles?offset=0&limit=20", "/api/v1/catalog/profiles?offset=2&limit=1",
    ]);
    expect(vi.mocked(globalThis.fetch).mock.calls.every(([, init]) => init?.method === undefined)).toBe(true);
  });

  it("registers a complete profile once and trusts the server response digest/readiness", async () => {
    const profile = { schema_version: 1, profile_id: "new-profile", revision: 1, universe_size: 100,
      positions: 1, allows_repeats: true, multipliers: [{ numerator: 5, denominator: 4 }],
      currency: "DOP", scale: 2, stake_increment: 4, minimum_stake: 4, maximum_stake: 100,
      max_coverage: 1, max_exposure: 100, best_rule: "maximum-payout/v1" as const };
    const item = { profile, profile_sha256: "a".repeat(64), execution_supported: false,
      profile_execution: { ready: true, selector_capabilities: ["static-numbers/v1"],
        staking_capabilities: ["flat-per-number/v1"], entry_policies: ["all_rows/v1"],
        settlements: ["all", "best"], requires_compatible_dataset: true,
        audaz_compatibility: { available: false, maximum_compatible_coverage: 0,
          coverage_rule: "selected coverage must be strictly less than multiplier[0]" } } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(201, item))
      .mockResolvedValueOnce(jsonResponse(409, { detail: "profile version conflicts with registered content" }))
      .mockResolvedValueOnce(jsonResponse(409, { detail: "profile quota has insufficient headroom" }))
      .mockResolvedValueOnce(jsonResponse(422, { detail: "invalid game profile" }));
    await expect(apiClient.registerProfile(profile)).resolves.toEqual(item);
    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe("/api/v1/catalog/profiles");
    expect(vi.mocked(globalThis.fetch).mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify(profile) });
    for (const status of [409, 409, 422]) await expect(apiClient.registerProfile(profile)).rejects.toMatchObject({ status });
  });

  it("reads bounded inert datasets through GET only", async () => {
    const page = { total: 1, offset: 0, limit: 20, items: [{
      dataset_sha256: "a".repeat(64), source_sha256: "b".repeat(64),
      source_id: "local", source_revision: "v1", profile_id: "test-draw",
      profile_revision: 1, positions: 3, universe_size: 100, records_total: 2,
      first_draw: "2025-01-01 05:10", last_draw: "2025-01-02 05:10",
      clock: { mode: "naive_legacy", zone: null }, execution_supported: false,
      created_at: "2025-01-03T00:00:00Z",
    }] };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, page))
      .mockResolvedValueOnce(jsonResponse(200, { ...page, offset: 3, limit: 1, items: [] }));
    await expect(apiClient.getDatasets()).resolves.toEqual(page);
    await expect(apiClient.getDatasets(3, 1)).resolves.toMatchObject({ offset: 3, items: [] });
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/datasets?offset=0&limit=20", "/api/v1/datasets?offset=3&limit=1",
    ]);
    expect(vi.mocked(globalThis.fetch).mock.calls.every(([, init]) => init?.method === undefined)).toBe(true);
  });

  it("keeps unfiltered starting draws compatible and encodes dated pagination and availability", async () => {
    const page = { total: 125, offset: 100, limit: 100, items: ["2025-09-03 08:00"] };
    const availability = { date: "2025-09-03", history_total: 150, ranked_total: 125 };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, page))
      .mockResolvedValueOnce(jsonResponse(200, page))
      .mockResolvedValueOnce(jsonResponse(200, availability));
    await expect(apiClient.getStartingDraws(100, 100)).resolves.toEqual(page);
    await expect(apiClient.getStartingDraws(100, 100, "2025-09-03")).resolves.toEqual(page);
    await expect(apiClient.getStartingDrawAvailability("2025-09-03")).resolves.toEqual(availability);
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/catalog/starting-draws?offset=100&limit=100",
      "/api/v1/catalog/starting-draws?offset=100&limit=100&date=2025-09-03",
      "/api/v1/catalog/starting-draws/availability?date=2025-09-03",
    ]);
    expect(vi.mocked(globalThis.fetch).mock.calls.every(([, init]) => init?.method === undefined)).toBe(true);
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

  it("submits the same explicit import envelope to preview and hash-bound promotion", async () => {
    const body = {
      raw_base64: "AP8K", format: "csv" as const,
      mapping: { date: "date", time: "time", positions: ["pos1"] },
      source: { source_id: "local", kind: "artificial" as const, revision: "r1", provenance: "manual" },
      clock: { mode: "naive_legacy" as const, zone: null }, profile: { profile_id: "saved", revision: 1 },
    };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { promotable: true, dataset_sha256: "a".repeat(64) }))
      .mockResolvedValueOnce(jsonResponse(200, { dataset_sha256: "a".repeat(64), created: true }));
    await apiClient.previewImport(body as never);
    await apiClient.promoteImport({ ...body, expected_dataset_sha256: "a".repeat(64) } as never);
    const calls = vi.mocked(globalThis.fetch).mock.calls;
    expect(calls.map(([url]) => url)).toEqual(["/api/v1/imports/preview", "/api/v1/imports/promote"]);
    expect(calls.map(([, init]) => init?.method)).toEqual(["POST", "POST"]);
    expect(JSON.parse(String(calls[0][1]?.body))).toEqual(body);
    expect(JSON.parse(String(calls[1][1]?.body))).toEqual({ ...body, expected_dataset_sha256: "a".repeat(64) });
  });

  it("posts an exact profile request document without the legacy request envelope", async () => {
    const body: ProfileExperimentRequest = { kind: "profile", schema_version: 1, name: "Local", dataset_sha256: "a".repeat(64),
      profile_id: "local", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
      conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 200, goal: 300,
        settlement: "all" as const, max_elapsed_draws: 12, max_bet_draws: null, end_minute: null, duration_minutes: null },
      selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1, numbers: [0], seed: null, algorithm_version: null },
      staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 1 } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(201, { id: "c".repeat(32), status: "pending" }));
    await expect(apiClient.createProfileExperiment(body)).resolves.toMatchObject({ status: "pending" });
    expect(vi.mocked(globalThis.fetch).mock.calls[0]).toMatchObject([
      "/api/v1/experiments/profiles", { method: "POST", body: JSON.stringify(body) },
    ]);
  });

  it("posts schema-3 Audaz with no fixed per-number stake", async () => {
    const body: ProfileAudazRequest = { kind: "profile", schema_version: 3, name: "Audaz", dataset_sha256: "a".repeat(64),
      profile_id: "rational", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
      conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 20000, goal: 30000,
        settlement: "all", max_elapsed_draws: 10, max_bet_draws: null, end_minute: null, duration_minutes: null },
      selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1, numbers: [0], seed: null, algorithm_version: null },
      staking: { schema_version: 1, capability: "profile-audaz/v1" } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(201, { id: "d".repeat(32), status: "pending" }));
    await apiClient.createProfileExperiment(body);
    expect(vi.mocked(globalThis.fetch).mock.calls[0]).toMatchObject([
      "/api/v1/experiments/profiles", { method: "POST", body: JSON.stringify(body) },
    ]);
    expect(JSON.stringify(body)).not.toContain("per_number_stake");
  });
  it("posts schema-4 recovery with explicit profile-generic parameters", async () => {
    const body: ProfileRecoveryRequest = { kind: "profile", schema_version: 4, name: "Recovery", dataset_sha256: "a".repeat(64),
      profile_id: "rational", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
      conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 20000, goal: 30000,
        settlement: "all", max_elapsed_draws: 10, max_bet_draws: null, end_minute: null, duration_minutes: null },
      selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2, numbers: [0, 1], seed: null, algorithm_version: null },
      staking: { schema_version: 1, target_margin: 250, rounds: 4, end_mode: "cycle" } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(201, { id: "e".repeat(32), status: "pending" }));
    await apiClient.createProfileExperiment(body);
    expect(vi.mocked(globalThis.fetch).mock.calls[0]).toMatchObject([
      "/api/v1/experiments/profiles", { method: "POST", body: JSON.stringify(body) },
    ]);
  });
  it("fetches verified dataset identity and paged draw labels with date encoding", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(200, { total: 1, items: ["2025-01-01 05:10"] }));
    await apiClient.getDataset("a".repeat(64));
    await apiClient.getDatasetDraws("a".repeat(64), 100, 100, "2025-01-01");
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      `/api/v1/datasets/${"a".repeat(64)}`,
      `/api/v1/datasets/${"a".repeat(64)}/draws?offset=100&limit=100&date=2025-01-01`,
    ]);
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
