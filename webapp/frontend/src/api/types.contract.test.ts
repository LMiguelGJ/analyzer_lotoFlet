import { describe, expect, it } from "vitest";
import experimentDetailFixture from "./__fixtures__/experiment-detail.json";
import replayFixture from "./__fixtures__/replay.json";
import settingsFixture from "./__fixtures__/settings.json";
import { isProfileComparison, isProfileExperiment, isProfileReplay, isProfileRun } from "./types";
import type { Bet, DatasetListing, ExperimentSummary, Page, ProfileCatalog, ProfileCompareResult, ProfileExperimentSummary, ReplayPage, SettingsView } from "./types";

/**
 * Captured from a real backend response (webapp/backend, in-process
 * TestClient against create_app + CatalogStub, 2026-09-29): GET
 * /api/v1/experiments/{id} and GET /api/v1/experiments/{id}/runs/0/replay.
 * See ./__fixtures__/*.json for the raw response bytes this was transcribed
 * from (`resolveJsonModule` widens JSON string fields to plain `string`, so
 * a raw JSON import can't be narrowed by `satisfies`; `as const` here
 * restores the literal types without changing a single field name or
 * value). `satisfies` checks these captured literals against frontend types.
 * This static test does not execute the backend or detect backend-only schema
 * changes. Live contract verification is required when backend responses change.
 */
const experimentDetail = {
  id: "db2b35a1b9644a8aa34ae1e93f4c3852",
  status: "completed",
  request: {
    name: "Trial",
    conditions: {
      start_draw: "2025-01-01 05:10",
      capital: 100,
      goal: 200,
      settlement: "all",
      max_bets: null,
      max_minutes: null,
      seed: 42,
    },
    strategies: [
      {
        name: "Cold",
        selector: "system",
        system: "cold",
        components: null,
        coverage: 1,
        staking: "flat",
      },
    ],
  },
  sources: {
    history_id: "history",
    history_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    rankings_id: "rankings",
    rankings_sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    code_version: "v1",
  },
  runs: [
    {
      ordinal: 0,
      configuration_id: null,
      status: "completed",
      result: {
        outcome: "goal",
        bets_count: 1,
        wagered: 1,
        paid: 80,
        final_balance: 179,
        delta: 79,
      },
      bets_count: 1,
    },
  ],
} as const satisfies ExperimentSummary;

// Schema-shaped projection of the current backend profile endpoint. Unlike the older
// captured experiment fixture above, this does not claim to be a live capture.
const legacyProfile = {
  schema_version: 1, profile_id: "legacy-quiniela-80", revision: 1,
  universe_size: 100, positions: 5, allows_repeats: true,
  multipliers: [80, 8, 4, 2, 1].map((numerator) => ({ numerator, denominator: 1 })),
  currency: "DOP", scale: 0, stake_increment: 1, minimum_stake: 1,
  maximum_stake: 1_000_000_000, max_coverage: 50, max_exposure: 1_000_000_000,
  best_rule: "first-match/v0",
} as const;

const readiness = { ready: true, selector_capabilities: ["static-numbers/v1"],
  staking_capabilities: ["flat-per-number/v1"], entry_policies: ["all_rows/v1"],
  settlements: ["all", "best"], requires_compatible_dataset: true,
  audaz_compatibility: { available: false, maximum_compatible_coverage: 0,
    coverage_rule: "selected coverage must be strictly less than multiplier[0]" } } as const;

const profileCatalog = {
  total: 1, offset: 0, limit: 20,
  items: [{ profile: legacyProfile, profile_sha256: "a".repeat(64), execution_supported: true, profile_execution: readiness }],
  templates: [
    {
      name: "Original70", provenance: "repo_ref/strategy_tests/rules.py: ORIGINAL70 and payout_matrix",
      known_fields: {
        universe_size: 100, positions: 5,
        multipliers: [70, 8, 4, 2, 1].map((numerator) => ({ numerator, denominator: 1 })),
      },
      missing_fields: ["schema_version", "profile_id", "revision", "allows_repeats", "currency",
        "scale", "stake_increment", "minimum_stake",
        "maximum_stake", "max_coverage", "max_exposure", "best_rule"],
      execution_supported: false,
    },
    {
      name: "User example 60/10/5", provenance: "docs/especificaciones-laboratorio-integral.md: E01",
      known_fields: {
        universe_size: 100, positions: 3, allows_repeats: true,
        multipliers: [60, 10, 5].map((numerator) => ({ numerator, denominator: 1 })),
        currency: "DOP", minimum_stake: 1,
      },
      missing_fields: ["schema_version", "profile_id", "revision", "scale", "stake_increment",
        "maximum_stake", "max_coverage",
        "max_exposure", "best_rule"],
      execution_supported: false,
    },
  ],
} as const satisfies ProfileCatalog;

const datasetPage = {
  total: 1, offset: 0, limit: 20,
  items: [{
    dataset_sha256: "a".repeat(64), source_sha256: "b".repeat(64),
    created_at: "2025-01-03T00:00:00Z", source_id: "local-1", source_revision: "v1",
    profile_id: "test-draw", profile_revision: 1, positions: 3, universe_size: 100,
    records_total: 2, first_draw: "2025-01-01 05:10", last_draw: "2025-01-02 05:10",
    clock: { mode: "naive_legacy", zone: null }, execution_supported: false,
    profile_sha256: "a".repeat(64), profile_execution: readiness,
  }],
} as const satisfies Page<DatasetListing>;

const currentExperiment = { ...experimentDetail, profile: legacyProfile } satisfies ExperimentSummary;

const profileExperiment: ProfileExperimentSummary = {
  id: "profile-1", status: "completed", request_kind: "profile", created_at: null,
  request: {
    kind: "profile", schema_version: 1, name: "Profile trial", dataset_sha256: "a".repeat(64),
    profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
    conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 3, max_bet_draws: 2, end_minute: null, duration_minutes: null },
    selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1, numbers: [7], seed: null, algorithm_version: null },
    staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 100 },
  },
  profile: { ...legacyProfile, profile_id: "test", currency: "USD", scale: 2, positions: 3, multipliers: [{ numerator: 80, denominator: 1 }, { numerator: 8, denominator: 1 }, { numerator: 4, denominator: 1 }] },
  display: { name: "Profile trial", currency: "USD", scale: 2, capital: 10000, goal: 20000, selector_label: "static-numbers/v1", staking_label: "flat-per-number/v1" },
  sources: { history_id: "a", history_sha256: "a", rankings_id: "", rankings_sha256: "", code_version: "profile-v1" },
  runs: [{ ordinal: 0, configuration_id: null, status: "completed", result_kind: "profile", bets_count: 1,
    result: { schema_version: 1, profile_id: "test", profile_revision: 1, outcome: "limit", collisions: ["max_elapsed_draws"], elapsed_draws: 3, bet_draws: 1, wagered: 100, paid: 0, final_balance: 9900, delta: -100 },
  }],
};
const cyclingExperiment: ProfileExperimentSummary = {
  ...profileExperiment, status: "completed",
  request: { ...profileExperiment.request, schema_version: 2, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } },
  display: { ...profileExperiment.display, staking_label: "Escalera cíclica Q80 · apuesta dinámica por sorteo" },
  runs: [{ ...profileExperiment.runs[0], status: "completed", result: { ...profileExperiment.runs[0].result!, schema_version: 2 } }],
};
const cyclingReplay: ReplayPage = { result_kind: "profile", schema_version: 2, total: 1, offset: 0, limit: 20,
  items: [{ label: "2025-01-01 05:10", stakes: [[7, 1]], results: [7, 8, 9], wagered: 1, paid: 0, balance: 99 }],
};
const profileReplay: ReplayPage = { result_kind: "profile", total: 1, offset: 0, limit: 20,
  items: [{ label: "2025-01-01 05:10", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }],
};
const profileCompare: ProfileCompareResult = { id: "profile-1", status: "completed", request_kind: "profile", completed: 1, requested: 1, complete: true, runs: profileExperiment.runs };

const replayBets = [
  {
    label: "2025-01-01 05:10",
    numbers: [7],
    per_number: 1,
    wagered: 1,
    results: [7, 8, 9, 10, 11],
    paid: 80,
    balance: 179,
  },
] as const satisfies Bet[];

// Schema-shaped specimen transcribed from api/settings.py response keys, not a live capture.
// The imported fixture is a pre-profile-accounting capture: compare its legacy subset only.
// Exact quota bytes stay strings; numeric fields are compatibility-only.
const settingsView = {
  storage: {
    limit_bytes: 5368709120, logical_used_bytes: 1024, logical_used_bytes_exact: "1024",
    profile_artifact_bytes: 256, profile_artifact_bytes_exact: "256",
    dataset_artifact_bytes_exact: "0", admission_logical_bytes_exact: "1280",
    logical_margin_bytes: 1048576, free_disk_bytes: 987654321, disk_margin_bytes: 67108864,
    database_bytes: 8192, wal_bytes: 4096, shm_bytes: 32768, temp_bytes: 0,
    sqlite_bytes: 45056, warning: false,
  },
  quota: { effective_bytes: "5368709120", persisted_bytes: null, source: "default", writable: true },
  sources: {
    history_id: "chance_express_history.json", history_sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    rankings_id: "pos1.npz", rankings_sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    code_version: "0.1.0",
  },
  connection: { host: "127.0.0.1", port: 8765, version: "0.1.0" },
} as const satisfies SettingsView;

describe("API response contract (types.ts vs backend serialization)", () => {
  it("discriminates profile detail, comparison, run and replay while retaining omitted legacy markers", () => {
    const legacy: ExperimentSummary = experimentDetail;
    const oldReplay: ReplayPage = { total: 1, offset: 0, limit: 20, items: replayBets.map((bet) => ({ ...bet, numbers: [...bet.numbers], results: [...bet.results] })) };
    expect(isProfileExperiment(legacy)).toBe(false);
    expect(isProfileRun(legacy.runs[0])).toBe(false);
    expect(isProfileReplay(oldReplay)).toBe(false);
    expect(isProfileExperiment(profileExperiment)).toBe(true);
    expect(isProfileRun(profileExperiment.runs[0])).toBe(true);
    expect(isProfileComparison(profileCompare)).toBe(true);
    expect(isProfileReplay(profileReplay)).toBe(true);
    expect(profileExperiment.runs[0].result).not.toHaveProperty("kind");
    expect(profileReplay.items[0]).not.toHaveProperty("per_number");
  });
  it("narrows cycling requests without inventing a flat stake or v1 result discriminator", () => {
    expect(isProfileExperiment(cyclingExperiment)).toBe(true);
    if (cyclingExperiment.request.schema_version === 2) {
      expect(cyclingExperiment.request.staking).toEqual({ schema_version: 1, capability: "q80-first-prize-cycling/v1" });
      expect(cyclingExperiment.request.staking).not.toHaveProperty("per_number_stake");
    }
    expect(cyclingExperiment.runs[0].result?.schema_version).toBe(2);
    expect(cyclingExperiment.runs[0].result).not.toHaveProperty("kind");
    expect(isProfileReplay(cyclingReplay)).toBe(true);
    expect(cyclingReplay).toHaveProperty("schema_version", 2);
    expect(cyclingReplay.items[0]).not.toHaveProperty("per_number");
  });
  it("types schema-3 Audaz requests, results, comparison and replay without a fixed stake", () => {
    const audaz: ProfileExperimentSummary = { ...profileExperiment,
      request: { ...profileExperiment.request, schema_version: 3, staking: { schema_version: 1, capability: "profile-audaz/v1" } },
      display: { ...profileExperiment.display, staking_label: "Audaz · apuesta dinámica por sorteo" },
      runs: [{ ...profileExperiment.runs[0], result: { ...profileExperiment.runs[0].result!, schema_version: 3 } }],
    };
    const replay: ReplayPage = { result_kind: "profile", schema_version: 3, total: 1, offset: 0, limit: 20,
      items: [{ label: "2025-01-01 05:10", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] };
    expect(audaz.request.schema_version).toBe(3);
    expect(audaz.request.staking).not.toHaveProperty("per_number_stake");
    expect(audaz.runs[0].result?.schema_version).toBe(3);
    expect(isProfileReplay(replay)).toBe(true);
  });
  it.each(["cycle", "stop"] as const)("types schema-4 recovery request, result, comparison and replay with %s mode", (end_mode) => {
    const recovery: ProfileExperimentSummary = { ...profileExperiment, request: { ...profileExperiment.request,
      schema_version: 4, staking: { schema_version: 1, target_margin: 250, rounds: 4, end_mode } },
      display: { ...profileExperiment.display, staking_label: "Escalera de recuperación · parámetros explícitos por perfil" },
      runs: [{ ...profileExperiment.runs[0], result: { ...profileExperiment.runs[0].result!, schema_version: 4 } }],
    };
    const replay: ReplayPage = { result_kind: "profile", schema_version: 4, total: 1, offset: 0, limit: 20,
      items: [{ label: "2025-01-01 05:10", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] };
    expect(recovery.request.schema_version).toBe(4);
    expect(recovery.request.staking).toEqual({ schema_version: 1, target_margin: 250, rounds: 4, end_mode });
    expect(recovery.runs[0].result?.schema_version).toBe(4);
    expect(isProfileReplay(replay)).toBe(true);
    expect(replay.schema_version).toBe(4);
  });
  it("keeps historical settings fixture fields and adds exact admission components", () => {
    expect(settingsView).toMatchObject(settingsFixture);
    expect(settingsView.quota.effective_bytes).toBe("5368709120");
    expect(settingsView.storage.logical_used_bytes_exact).toBe("1024");
    expect(settingsView.storage.profile_artifact_bytes_exact).toBe("256");
    expect(settingsView.storage.dataset_artifact_bytes_exact).toBe("0");
    expect(BigInt(settingsView.storage.logical_used_bytes_exact) +
      BigInt(settingsView.storage.profile_artifact_bytes_exact)).toBe(
      BigInt(settingsView.storage.admission_logical_bytes_exact));
    expect(settingsView).not.toHaveProperty("adjustment_persistence");
  });
  it("matches the parsed fixture fields and values (not raw JSON formatting)", () => {
    expect(experimentDetailFixture).toEqual(experimentDetail);
    expect(replayFixture.items).toEqual(replayBets);
  });

  it("matches the projected experiment detail run result: bets_count/wagered/paid/final_balance/delta, no bets_placed", () => {
    const run = experimentDetail.runs[0];
    expect(run.result).toMatchObject({
      outcome: "goal",
      bets_count: 1,
      wagered: 1,
      paid: 80,
      final_balance: 179,
      delta: 79,
    });
    expect(run.result && "bets" in run.result).toBe(false);
  });

  it("types metadata-only dataset discovery without implying execution support", () => {
    expect(datasetPage.items[0].execution_supported).toBe(false);
    expect(datasetPage.items[0].clock).toEqual({ mode: "naive_legacy", zone: null });
    expect(datasetPage.items[0]).not.toHaveProperty("raw_bytes");
    expect(datasetPage.items[0]).not.toHaveProperty("canonical_json");
  });

  it("types the exact legacy snapshot and keeps older captured fixtures compatible", () => {
    expect(currentExperiment.profile.multipliers[0]).toEqual({ numerator: 80, denominator: 1 });
    expect(experimentDetailFixture).not.toHaveProperty("profile");
    expect(profileCatalog.items[0].execution_supported).toBe(true);
    expect(profileCatalog.templates[0].known_fields.universe_size).toBe(100);
    expect(profileCatalog.templates[0].missing_fields).toContain("maximum_stake");
    expect(profileCatalog.templates.every((item) => item.execution_supported === false)).toBe(true);
  });

  it("matches the real replay bet shape: label/per_number/wagered/results, not drawn_at/amount_per_number/total_spent/drawn_numbers/payout", () => {
    expect(replayBets[0]).toMatchObject({
      label: "2025-01-01 05:10",
      per_number: 1,
      wagered: 1,
      results: [7, 8, 9, 10, 11],
      paid: 80,
      balance: 179,
    });
  });
});
