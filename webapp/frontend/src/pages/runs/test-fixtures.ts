import type { RunOptions, RunReport } from "../../api/types";

export const optionsFixture: RunOptions = {
  systems: [
    { id: "transition", label: "Transición" },
    { id: "cold", label: "Fríos" },
    { id: "hot", label: "Calientes" },
  ],
  defaults: {
    name: null,
    rules: { positions: 3, prizes: [60, 10, 5], minimum_stake: 1 },
    strategy: { kind: "mix", components: [{ system: "transition", percent: 60 }, { system: "cold", percent: 40 }], coverage: 10 },
    conditions: { capital: 2000, goal: 2800, max_draws: null },
    window: { start_date: null, end_date: null },
    history_sha256: null,
  },
  limits: { coverage: { min: 1, max: 50 }, positions: { min: 1, max: 5 }, name: 80, detail: { sessions: 50000, bets: 250000, bytes: 33554432 } },
  history: { sha256: "a".repeat(64), origin: "frozen", draws: 105426, ranked_draws: 65235, first_label: "2025-03-05", last_label: "2026-09-25", added_draws: 0, created_at: null, active: true },
};

export const runFixture: RunReport = {
  id: "run-123", name: "Corrida base", created_at: "2026-01-01T12:00:00Z", schema_version: 1,
  config: {
    name: "Corrida base", rules: { positions: 3, prizes: [60, 10, 5], minimum_stake: 1 },
    strategy: { kind: "mix", components: [{ system: "transition", percent: 60 }, { system: "cold", percent: 40 }], coverage: 10 },
    conditions: { capital: 2000, goal: 2800, max_draws: null }, window: { start_date: null, end_date: null },
    history: { sha256: "b".repeat(64), origin: "frozen" },
  },
  summary: {
    totals: { sessions: 1, goal: 0, ruin: 1, limit: 0, incomplete: 0, bets: 1, wagered: 10, paid: 0, net: -10, return_pct: -100, mean_net_closed: -10 },
    window: { draws: 1, ranked_draws: 1, first_label: "2025-09-02", last_label: "2025-09-02" },
    detail: { status: "complete", total_sessions: 1, stored_sessions: 1, total_bets: 1, stored_bets: 1, limits: { sessions: 50000, bets: 250000, bytes: 33554432 } }, engine_version: 1, elapsed_seconds: 0.1,
  },
};
