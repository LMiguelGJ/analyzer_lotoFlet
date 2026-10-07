import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError, NetworkError } from "./client";
import settingsFixture from "./__fixtures__/settings.json";
import type { ProfileAudazRequest, ProfileExperimentRequest, ProfileRecoveryRequest } from "./types";

const agentApi = apiClient as typeof apiClient & {
  getAgentCredential: () => Promise<{ token: string }>;
};

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
    "# F-API-001 maps HTTP %i to an ApiError with that status and detail",
    async (status: number) => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(status, { detail: `error ${status}` }));

      await expect(apiClient.getCatalog()).rejects.toMatchObject(new ApiError(status, `error ${status}`));
    },
  );

  it("# F-API-002 falls back to the status text when the error body has no detail", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response("not json", { status: 500, statusText: "Internal Server Error" }),
    );

    await expect(apiClient.getCatalog()).rejects.toMatchObject({
      status: 500,
      detail: "Internal Server Error",
    });
  });

  it("# F-API-003 maps a fetch rejection to NetworkError, never claiming the server stopped", async () => {
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(NetworkError);
    expect((error as Error).message).not.toMatch(/detuvo|stopped/i);
  });

  it("# F-API-009 F-API-010 requests a bounded whole-run trajectory with an encoded identifier", async () => {
    const trajectory = { total: 1001, points: [], reduction_method: "minmax-even-v1" };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, trajectory));
    await expect(apiClient.getTrajectory("a/b", 2, 500)).resolves.toEqual(trajectory);
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/v1/experiments/a%2Fb/runs/2/trajectory?max_points=500", expect.anything());
  });
  it("# F-API-005 resolves with the parsed JSON body on success", async () => {
    const catalog = { game: { name: "Quiniela 80" } };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, catalog));

    await expect(apiClient.getCatalog()).resolves.toEqual(catalog);
  });

  it("# F-API-005 resolves with undefined on a 204 No Content", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(apiClient.deleteExperiment("abc", "abc")).resolves.toBeUndefined();
  });

  it("# F-API-008 requests same-origin relative URLs under /api/v1", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}));

    await apiClient.getCatalog();

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(String(url)).toBe("/api/v1/catalog");
  });

  it("# F-API-011 reads bounded profiles and partial template metadata without a write request", async () => {
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

  it("# F-API-015 registers a complete profile once and trusts the server response digest/readiness", async () => {
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

  it("# F-API-011 reads bounded inert datasets through GET only", async () => {
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

  it("# F-API-012 keeps unfiltered starting draws compatible and encodes dated pagination and availability", async () => {
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

  it("# F-API-026 encodes canonical simulation scope and server-side filters, ordering and offset", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { total: 0, offset: 20, limit: 20, items: [] }));
    await apiClient.listSimulations({ scope: "historical", offset: 20, limit: 20, name_contains: "Fríos & 50%", status: "completed", sort: "name", order: "asc" });
    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe(
      "/api/v1/simulations?offset=20&limit=20&scope=historical&name_contains=Fr%C3%ADos+%26+50%25&status=completed&sort=name&order=asc",
    );
    expect(vi.mocked(globalThis.fetch).mock.calls[0][1]?.method).toBeUndefined();
  });

  it("# F-API-013 encodes server-side experiment filters, ordering and bounded offset without interpreting Unicode", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { total: 0, offset: 20, limit: 20, items: [] }));
    await apiClient.listExperiments({ offset: 20, limit: 20, name_contains: "Fríos & 50%", status: "running", sort: "name", order: "asc" });
    expect(vi.mocked(globalThis.fetch).mock.calls[0][0]).toBe(
      "/api/v1/experiments?offset=20&limit=20&name_contains=Fr%C3%ADos+%26+50%25&status=running&sort=name&order=asc",
    );
  });

  it("# F-API-014 sends confirm_id tied to the target resource on delete", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));

    await apiClient.deleteExperiment("exp-1", "exp-1");

    const [, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({ confirm_id: "exp-1" });
  });

  it("# F-API-009 encodes a path id that contains reserved URL characters", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}));

    await apiClient.getExperiment("a/b c");

    const [url] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(String(url)).toBe(`/api/v1/experiments/${encodeURIComponent("a/b c")}`);
  });

  it("# F-API-007 parses a FastAPI 422 array detail into field errors with a Spanish generic message", async () => {
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

  it("# F-API-007 still supports a plain string detail (no field errors)", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(400, { detail: "start draw has no ranking" }));

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).fieldErrors).toBeNull();
    expect((error as ApiError).detail).toBe("start draw has no ranking");
  });

  it("# F-API-006 maps a 2xx response with a non-JSON body to a typed ApiError, not a raw SyntaxError", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response("not json", { status: 200, headers: { "Content-Type": "text/plain" } }),
    );

    const error = await apiClient.getCatalog().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).not.toBeInstanceOf(SyntaxError);
  });

  it("# F-API-016 GET and PUT settings use the full view, exact string payload and same-origin URL", async () => {
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

  it("# F-API-017 encodes queue action IDs, sends POST without a body, and reads acknowledgements only", async () => {
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

  it("# F-API-018 uploads canonical history as original Blob bytes with registered profile and exact metadata headers", async () => {
    const file = new Blob(["{\\\"metadata\\\":{}}"], { type: "application/json" });
    const profile = { profile: { profile_id: "saved", revision: 3 }, profile_sha256: "b".repeat(64) } as never;
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { promotable: true }))
      .mockResolvedValueOnce(jsonResponse(200, { dataset_sha256: "a".repeat(64) }));
    await apiClient.previewHistoryImport(file, profile, "operator", "America/Santo_Domingo");
    await apiClient.promoteHistoryImport(file, profile, "operator", "America/Santo_Domingo", "a".repeat(64));
    const calls = vi.mocked(globalThis.fetch).mock.calls;
    expect(calls.map(([url]) => url)).toEqual(["/api/v1/imports/preview", "/api/v1/imports/promote"]);
    for (const [, init] of calls) {
      expect(init?.body).toBe(file);
      expect(init?.body).not.toBe(JSON.stringify(file));
      expect(init?.headers).toMatchObject({ "X-Import-Mode": "history", "X-Profile-Id": "saved", "X-Profile-Revision": "3",
        "X-Profile-Sha256": "b".repeat(64), "X-Confirm-Source": "operator",
        "X-Confirm-Timezone": "America/Santo_Domingo" });
    }
    expect(calls[1][1]?.headers).toMatchObject({ "X-Expected-Dataset-Sha256": "a".repeat(64) });
  });

  it("# F-API-019 submits the same explicit import envelope to preview and hash-bound promotion", async () => {
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
    for (const [, init] of calls) expect(init?.headers).toMatchObject({ "X-Import-Mode": "records" });
  });

  it("# F-API-020 posts an exact profile request document without the legacy request envelope", async () => {
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

  it("# F-API-020 posts schema-3 Audaz with no fixed per-number stake", async () => {
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
  it("# F-API-020 posts schema-4 recovery with explicit profile-generic parameters", async () => {
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
  it("# F-API-021 fetches verified dataset identity and paged draw labels with date encoding", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(200, { total: 1, items: ["2025-01-01 05:10"] }));
    await apiClient.getDataset("a".repeat(64));
    await apiClient.getDatasetDraws("a".repeat(64), 100, 100, "2025-01-01");
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      `/api/v1/datasets/${"a".repeat(64)}`,
      `/api/v1/datasets/${"a".repeat(64)}/draws?offset=100&limit=100&date=2025-01-01`,
    ]);
  });

  it("# F-API-022 uses the closed v1 batch routes and exact client identity for validation, submit and recovery lookup", async () => {
    const body = { schema_version: 1 as const, profile: { id: "local", revision: 2, sha256: "a".repeat(64) },
      dataset_sha256: "b".repeat(64), strategies: [{ id: "s/1", revision: 3, definition_sha256: "c".repeat(64) }],
      conditions: { schema_version: 1 as const, start_draw: "2025-01-01 05:10", capital: 100, goal: 200,
        settlement: "all" as const, max_elapsed_draws: 20, max_bet_draws: null, end_minute: null, duration_minutes: null },
      max_draws: 20, client_request_id: "client id/1" };
    const validation = { valid: true, reservation_created: false };
    const created = { id: "a".repeat(32), status: "pending" as const };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, validation))
      .mockResolvedValueOnce(jsonResponse(201, created)).mockResolvedValueOnce(jsonResponse(200, created));
    await expect(apiClient.validateProfileBatch(body)).resolves.toEqual(validation);
    await expect(apiClient.createProfileBatch(body)).resolves.toEqual(created);
    await expect(apiClient.getProfileBatchByClientRequestId(body.client_request_id)).resolves.toEqual(created);
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/profile-batches/validate", "/api/v1/profile-batches", "/api/v1/profile-batches/by-client-request/client%20id%2F1",
    ]);
    expect(JSON.parse(String(vi.mocked(globalThis.fetch).mock.calls[0][1]?.body))).toEqual(body);
    expect(vi.mocked(globalThis.fetch).mock.calls[1][1]).toMatchObject({ method: "POST", body: JSON.stringify(body) });
  });

  it("# F-API-023 reads strategies, exact profile compatibility, revisions and policy without changing legacy requests", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, { items: [], total: 0, offset: 0, limit: 20 }))
      .mockResolvedValueOnce(jsonResponse(200, {})).mockResolvedValueOnce(jsonResponse(200, {}))
      .mockResolvedValueOnce(jsonResponse(200, {})).mockResolvedValueOnce(jsonResponse(200, {}));
    await apiClient.listProfileBatchStrategies();
    await apiClient.getProfileBatchStrategy("preset/a", { id: "local", revision: 2, sha256: "d".repeat(64) });
    await apiClient.getProfileBatchStrategyRevisions("preset/a", 20, 10);
    await apiClient.getProfileBatchExecutionPolicy();
    await apiClient.createProfileBatchStrategy({ definition_version: 1, name: "Custom", selector: "static-numbers/v1",
      coverage: 1, staking: "flat-per-number/v1", selector_parameters: { numbers: [3] }, staking_parameters: { per_number_stake: 1 }, closing_defaults: {} });
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/strategies?offset=0&limit=20",
      `/api/v1/strategies/preset%2Fa?profile_id=local&profile_revision=2&profile_sha256=${"d".repeat(64)}`,
      "/api/v1/strategies/preset%2Fa/revisions?offset=20&limit=10", "/api/v1/execution-policy", "/api/v1/strategies",
    ]);
  });

  it("# F-API-025 creates, lists and reads backtests with the backend paths and typed payload", async () => {
    const body = { name: "Prueba", strategy: { name: "Transición", selector: "system" as const, system: "transition" as const, coverage: 1, staking: "bold" as const },
      game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 }, conditions: { capital: 2000, goal: 2800 },
      inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) } };
    const created = { id: "run/1", status: "completed" as const, report: { id: "run/1" } };
    const page = { total: 1, offset: 0, limit: 20, items: [{ id: "run/1" }] };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(201, created)).mockResolvedValueOnce(jsonResponse(200, page)).mockResolvedValueOnce(jsonResponse(200, page.items[0]));
    await expect(apiClient.createBacktest(body)).resolves.toEqual(created);
    await expect(apiClient.listBacktests(0, 20)).resolves.toEqual(page);
    await expect(apiClient.getBacktest("run/1")).resolves.toEqual(page.items[0]);
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/backtests", "/api/v1/backtests?offset=0&limit=20", "/api/v1/backtests/run%2F1",
    ]);
    expect(vi.mocked(globalThis.fetch).mock.calls[0][1]).toMatchObject({ method: "POST", body: JSON.stringify(body) });
  });

  it("R2 encodes historical trace IDs and requests only bounded sessions and bets pages", async () => {
    const page = { id: "a/b c", trace: { status: "not_stored", reason: "legacy" },
      total: 0, offset: 0, limit: 20, items: [] };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, page))
      .mockResolvedValueOnce(jsonResponse(200, { ...page, ordinal: 17, offset: 40, limit: 100 }));
    await expect(apiClient.getBacktestSessions("a/b c")).resolves.toEqual(page);
    await expect(apiClient.getBacktestSessionBets("a/b c", 17, 40, 100)).resolves.toMatchObject({ ordinal: 17 });
    expect(vi.mocked(globalThis.fetch).mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/backtests/a%2Fb%20c/sessions?offset=0&limit=20",
      "/api/v1/backtests/a%2Fb%20c/sessions/17/bets?offset=40&limit=100",
    ]);
    expect(vi.mocked(globalThis.fetch).mock.calls.every(([, init]) => init?.method === undefined)).toBe(true);
  });

  it.each([404, 409])("R2 preserves trace HTTP %s without converting it to an empty page", async (status) => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(status, { detail: "unavailable" }));
    await expect(apiClient.getBacktestSessionBets("saved", 0)).rejects.toMatchObject({ status });
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });

  it("# F-API-024 retrieves the actual agent credential by same-origin POST with an empty JSON body", async () => {
    const credential = { token: "test-only-agent-token" };
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(200, credential));

    await expect(agentApi.getAgentCredential()).resolves.toEqual(credential);

    const [url, init] = vi.mocked(globalThis.fetch).mock.calls[0];
    expect(url).toBe("/api/v1/settings/agent-credential");
    expect(init).toMatchObject({ method: "POST", body: "{}" });
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(init?.headers).not.toHaveProperty("Authorization");
  });

  it("# F-API-004 maps a proxy-marked disconnection response to NetworkError instead of ApiError", async () => {
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
