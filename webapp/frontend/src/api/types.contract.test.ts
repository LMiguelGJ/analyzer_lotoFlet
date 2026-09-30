import { describe, expect, it } from "vitest";
import experimentDetailFixture from "./__fixtures__/experiment-detail.json";
import replayFixture from "./__fixtures__/replay.json";
import settingsFixture from "./__fixtures__/settings.json";
import type { Bet, ExperimentSummary, SettingsView } from "./types";

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
// The exact quota bytes stay strings; limit_bytes is compatibility-only numeric data.
const settingsView = {
  storage: {
    limit_bytes: 5368709120, logical_used_bytes: 1024, logical_used_bytes_exact: "1024",
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
  it("aligns settings fixture keys with actual GET/PUT settings response, preserving decimal strings", () => {
    expect(settingsFixture).toEqual(settingsView);
    expect(settingsView.quota.effective_bytes).toBe("5368709120");
    expect(settingsView.storage.logical_used_bytes_exact).toBe("1024");
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
