import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, ExperimentSummary, Page, ProfileBatchExperimentSummary, ProfileExperimentSummary, ReplayPage } from "../../api/types";

vi.mock("../../api/client", async (original) => {
  const actual = await original<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getExperiment: vi.fn(), getReplay: vi.fn(), getTrajectory: vi.fn(), createExperiment: vi.fn() } };
});

const bet: Bet = { label: "2026-01-02T10:05:00", numbers: [0, 7], per_number: 10, wagered: 20, results: [0, 3, 7, 8, 9], paid: 60, balance: 140 };
const snapshot: ExperimentSummary = {
  id: "exp", status: "running", created_at: "2026-01-02T09:00:00Z",
  request: { name: "Prueba", conditions: { start_draw: bet.label, capital: 100, goal: 200, settlement: "all", max_bets: 12, seed: 5 }, strategies: [
    { name: "Primera", selector: "system", system: "cold", coverage: 2, staking: "flat" },
    { name: "Segunda", selector: "random", coverage: 2, staking: "bold" },
  ] },
  sources: { history_id: "history.json", history_sha256: "abc", rankings_id: "rank.npz", rankings_sha256: "def", code_version: "1" },
  runs: [
    { ordinal: 0, configuration_id: null, status: "completed", bets_count: 1, result: { outcome: "goal", bets_count: 1, wagered: 20, paid: 60, final_balance: 140, delta: 40 } },
    { ordinal: 1, configuration_id: null, status: "running", bets_count: 0, result: null },
  ],
};
const page: Page<Bet> = { total: 1, offset: 0, limit: 20, items: [bet] };
const profileSnapshot: ProfileExperimentSummary = {
  request_kind: "profile", id: "exp", status: "completed", created_at: null,
  request: { kind: "profile", schema_version: 1, name: "Perfil USD", dataset_sha256: "a".repeat(64), profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
    conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 3, max_bet_draws: 2, end_minute: null, duration_minutes: null },
    selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2, numbers: [7, 8], seed: null, algorithm_version: null },
    staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 125 } },
  profile: { schema_version: 1, profile_id: "test", revision: 1, universe_size: 100, positions: 3, allows_repeats: true, multipliers: [80, 8, 4].map((numerator) => ({ numerator, denominator: 1 })), currency: "USD", scale: 2, stake_increment: 1, minimum_stake: 1, maximum_stake: 100000, max_coverage: 10, max_exposure: 100000, best_rule: "maximum-payout/v1" },
  display: { name: "Perfil USD", currency: "USD", scale: 2, capital: 10000, goal: 20000, selector_label: "static-numbers/v1", staking_label: "flat-per-number/v1" },
  sources: { history_id: "a", history_sha256: "a", rankings_id: "", rankings_sha256: "", code_version: "profile-v1" },
  runs: [{ ordinal: 0, configuration_id: null, status: "completed", result_kind: "profile", bets_count: 1,
    result: { schema_version: 1, profile_id: "test", profile_revision: 1, outcome: "limit", collisions: ["max_elapsed_draws"], elapsed_draws: 3, bet_draws: 1, wagered: 250, paid: 0, final_balance: 9750, delta: -250 } }],
};
const profilePage: ReplayPage = { result_kind: "profile", total: 1, offset: 0, limit: 20, items: [{ label: "2025-01-01 05:10", stakes: [[7, 125], [8, 125]], results: [7, 8, 9], wagered: 250, paid: 0, balance: 9750 }] };
const cyclingSnapshot: ProfileExperimentSummary = {
  ...profileSnapshot, status: "completed",
  request: { ...profileSnapshot.request, schema_version: 2, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } },
  display: { ...profileSnapshot.display, staking_label: "Escalera cíclica Q80 · apuesta dinámica por sorteo" },
  runs: [{ ...profileSnapshot.runs[0], status: "completed", result: { ...profileSnapshot.runs[0].result!, schema_version: 2 } }],
};
const cyclingPage: ReplayPage = { result_kind: "profile", schema_version: 2, total: 1, offset: 0, limit: 20,
  items: [{ label: "2025-01-01 05:10", stakes: [[7, 125], [8, 125]], results: [7, 8, 9], wagered: 250, paid: 0, balance: 9750 }] };
const audazSnapshot: ProfileExperimentSummary = { ...cyclingSnapshot,
  request: { ...cyclingSnapshot.request, schema_version: 3, staking: { schema_version: 1, capability: "profile-audaz/v1" } },
  display: { ...cyclingSnapshot.display, staking_label: "Audaz · apuesta dinámica por sorteo" },
  runs: [{ ...cyclingSnapshot.runs[0], result: { ...cyclingSnapshot.runs[0].result!, schema_version: 3 } }],
};
const batchV5Snapshot: ProfileBatchExperimentSummary = {
  request_kind: "profile", request_schema_version: 5, id: "exp", status: "completed", created_at: null,
  request: { schema_version: 5, kind: "profile_batch", profile_id: "test", profile_revision: 1,
    profile_sha256: "b".repeat(64), dataset_sha256: "a".repeat(64),
    conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 3, max_bet_draws: 2, end_minute: null, duration_minutes: null },
    strategies: [{ definition_version: 1, name: "Snapshot cold", selector: "static-numbers/v1", coverage: 2, staking: "flat-per-number/v1", selector_parameters: { numbers: [7, 8] }, staking_parameters: {}, closing_defaults: {} }], max_draws: 3, source_version: "canonical-history/v1" },
  profile: profileSnapshot.profile,
  display: { ...profileSnapshot.display, name: "Lote guardado · Snapshot cold" },
  sources: profileSnapshot.sources,
  batch_admission: {
    strategy_refs: [{ id: "strategy-old", revision: 2, definition_sha256: "c".repeat(64) }],
    source_identity: { dataset_sha256: "a".repeat(64), source_sha256: "d".repeat(64), canonical_sha256: "e".repeat(64), row_count: 8, profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null },
    requested_constraints: { max_draws: 3 }, effective_constraints: { max_draws: 3 }, policy_revision: 1, policy: {},
  },
  runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "completed", bets_count: 1, complete: true, completion: "complete", stop_category: "configured_limit", stop_reason: "max_bet_draws", stop_code: "configured_limit", error: null,
    result_schema_version: 5, strategy: { id: "strategy-old", revision: 2, definition_sha256: "c".repeat(64), name: "Snapshot cold" },
    result: { schema_version: 5, profile_id: "test", profile_revision: 1, outcome: "limit", collisions: ["max_bet_draws"], elapsed_draws: 1, bet_draws: 1, wagered: 250, paid: 0, final_balance: 9750, delta: -250, net: -250, return_per_wagered: 0, roi: -1, max_drawdown: 250, metric_scope: "saved_individual_run", ratio_rounding: "decimal-half-up-6", definition_name: "Snapshot cold", start_draw_index: 5, prior_cutoff: "2024-12-31 05:10", dataset_sha256: "a".repeat(64), source_count: 8, requested_conditions: { max_draws: 3 }, effective_conditions: { max_draws: 3 }, stop_category: "configured_limit", stop_reason: "max_bet_draws", complete: true } }],
};
function setup(path = "/experimentos/exp") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return { router, user: userEvent.setup(), ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  vi.mocked(apiClient.getExperiment).mockReset();
  vi.mocked(apiClient.getTrajectory).mockReset().mockImplementation(async (_id, ordinal) => {
    const latest = vi.mocked(apiClient.getExperiment).mock.results.at(-1);
    const saved = await latest?.value;
    const run = saved?.runs.find((r: { ordinal: number }) => r.ordinal === ordinal);
    const total = run?.result?.bet_draws ?? run?.result?.bets_count ?? 0;
    const capital = saved?.request.conditions.capital ?? 100;
    const end = run?.result?.final_balance ?? capital;
    const v5 = saved?.request_schema_version === 5;
    return { result_kind: v5 ? "profile" as const : undefined, schema_version: v5 ? 5 as const : undefined,
      initial_capital: capital, total, max_points: 500, reduction_method: "none" as const,
      minimum: { balance: Math.min(capital, end), source_index: null }, maximum: { balance: Math.max(capital, end), source_index: null },
      points: Array.from({ length: Math.min(total, 500) }, (_, i) => ({ source_index: v5 ? (run?.result?.start_draw_index ?? 0) + i : i, ...(v5 ? { bet_index: i } : {}), label: `2025-01-01 10:${String(i % 60).padStart(2, "0")}`, balance: end, replay: `replay?offset=${i}&limit=1` })) };
  });
  vi.mocked(apiClient.getReplay).mockReset();
  vi.mocked(apiClient.getExperiment).mockResolvedValue(snapshot);
  vi.mocked(apiClient.getReplay).mockResolvedValue(page);
});

describe("profile detail READ", () => {
  it.each(["pending", "running", "held", "failed"] as const)("shows Q80 %s without a fabricated result or replay", async (status) => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...cyclingSnapshot, status,
      runs: [{ ...cyclingSnapshot.runs[0], status: status === "held" ? "pending" : status, result: null, bets_count: 0 }] });
    const { user, unmount } = setup();
    const run = await screen.findByRole("region", { name: "Ejecución 1" });
    expect(within(run).getByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
    await user.click(within(run).getByRole("tab", { name: "Parámetros y datos" }));
    expect(within(run).getByText("Escalera cíclica Q80 · apuesta dinámica por sorteo")).toBeInTheDocument();
    expect(apiClient.getReplay).not.toHaveBeenCalled();
    unmount();
  });
  it("reads completed cycling stake as dynamic, not a fabricated flat amount", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(cyclingSnapshot);
    vi.mocked(apiClient.getReplay).mockResolvedValue(cyclingPage);
    const { user } = setup();
    await screen.findByText("-USD 2.50");
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(screen.getByText("Escalera cíclica Q80 · apuesta dinámica por sorteo")).toBeInTheDocument();
    expect(screen.queryByText(/undefined por número/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    expect(await screen.findByText("7: USD 1.25, 8: USD 1.25")).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it.each([["pending", "pending"], ["held", "pending"], ["running", "running"], ["failed", "failed"]] as const)(
    "shows schema-3 Audaz %s without an invented result", async (status, runStatus) => {
      vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...audazSnapshot, status,
        runs: [{ ...audazSnapshot.runs[0], status: runStatus, result: null, bets_count: 0 }] });
      const { unmount } = setup();
      const run = await screen.findByRole("region", { name: "Ejecución 1" });
      expect(within(run).getByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
      expect(within(run).getByText(status === "held" ? "Pendiente" : status === "pending" ? "Pendiente" : status === "running" ? "En curso" : "Con error")).toBeInTheDocument();
      expect(apiClient.getReplay).not.toHaveBeenCalled();
      unmount();
    });
  it("renders schema-3 Audaz as dynamic across parameters and completed replay", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(audazSnapshot);
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 3, total: 1, offset: 0, limit: 20,
      items: [{ label: "2025-01-01 05:10", stakes: [[7, 125], [8, 125]], results: [7, 8, 9], wagered: 250, paid: 0, balance: 9750 }] });
    const { user } = setup();
    await screen.findByText("-USD 2.50");
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(screen.getByText("Audaz · apuesta dinámica por sorteo")).toBeInTheDocument();
    expect(screen.queryByText(/por número/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    expect(await screen.findByText("7: USD 1.25, 8: USD 1.25")).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
  });
  it.each([["cycle", "Reiniciar la escalera"], ["stop", "Detener la sesión"]] as const)("shows schema-4 recovery request, saved result version, and %s details", async (end_mode, ending) => {
    const recovery: ProfileExperimentSummary = { ...profileSnapshot,
      request: { ...profileSnapshot.request, schema_version: 4, staking: { schema_version: 1, target_margin: 1250, rounds: 3, end_mode } },
      profile: { ...profileSnapshot.profile, profile_id: "rational-recovery", multipliers: [{ numerator: 5, denominator: 2 }, { numerator: 3, denominator: 2 }] },
      display: { ...profileSnapshot.display, staking_label: "Escalera de recuperación · parámetros explícitos por perfil" },
      runs: [{ ...profileSnapshot.runs[0], result: { ...profileSnapshot.runs[0].result!, schema_version: 4, collisions: ["recovery_round_limit"] } }],
    };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(recovery);
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 4, total: 1, offset: 0, limit: 20,
      items: [{ label: "2025-01-01 05:10", stakes: [[7, 125]], results: [7, 8, 9], wagered: 125, paid: 0, balance: 9875 }] });
    const { user } = setup();
    expect(await screen.findByText("Cambio respecto del inicio")).toBeInTheDocument();
    expect(screen.queryByText("Versión del resultado")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    await user.click(screen.getByText("Detalles técnicos"));
    expect(screen.getAllByText("Perfil v4")).toHaveLength(2);
    expect(screen.getByText("Escalera de recuperación · parámetros explícitos por perfil")).toBeInTheDocument();
    expect(screen.getByText("USD 12.50")).toBeInTheDocument();
    expect(screen.getByText("Rondas de recuperación").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByText(ending)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    expect(await screen.findByText("7: USD 1.25")).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
  });
  it("does not claim historical provenance for a profile dataset without source kind", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(profileSnapshot);
    const { user } = setup();
    const run = await screen.findByRole("region", { name: "Ejecución 1" });
    expect(within(run).getByText("Simulación con datos del conjunto seleccionado: no predice resultados futuros ni garantiza rentabilidad.")).toBeInTheDocument();
    expect(within(run).queryByText(/Simulación con datos históricos/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(within(run).getByText("Resultados sobre datos del conjunto seleccionado: no constituyen una validación independiente de rentabilidad ni una probabilidad de éxito.")).toBeInTheDocument();
    expect(within(run).queryByText(/Resultados históricos/)).not.toBeInTheDocument();
  });

  it("shows server delta, elapsed/bet counts, 3 positions and per-number stakes in USD cents", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(profileSnapshot);
    vi.mocked(apiClient.getReplay).mockResolvedValue(profilePage);
    const { user } = setup();
    await screen.findByText("-USD 2.50");
    expect(screen.getByText("Cambio respecto del inicio").nextElementSibling).toHaveTextContent("-USD 2.50");
    expect(screen.getByText("Sorteos transcurridos").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByText("Sorteos apostados").nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText(/Límite de sesión \(límite de sorteos transcurridos\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    const table = await screen.findByRole("table", { name: "Apuestas del experimento" });
    expect(within(table).getAllByRole("columnheader", { name: /Resultado/ })).toHaveLength(3);
    expect(within(table).getByText("7: USD 1.25, 8: USD 1.25")).toBeInTheDocument();
    await user.click(within(table).getByRole("button", { name: "Detalle" }));
    expect(screen.getByText("Resultados (3 posiciones)").nextElementSibling).toHaveTextContent("7, 8, 9");
    expect(screen.getByText("Saldo resultante").nextElementSibling).toHaveTextContent("USD 97.50");
    expect(screen.queryByText(/posiciones 1 a 5/)).not.toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("shows one position without fixed-five columns, and preserves held/failed null results", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValueOnce({ ...profileSnapshot, profile: { ...profileSnapshot.profile, positions: 1 } });
    const onePosition: ReplayPage = { result_kind: "profile", total: 1, offset: 0, limit: 20, items: [{ label: "2025-01-01 05:10", stakes: [[7, 125]], results: [7], wagered: 125, paid: 0, balance: 9875 }] };
    vi.mocked(apiClient.getReplay).mockResolvedValueOnce(onePosition);
    const first = setup();
    await first.user.click(await screen.findByRole("tab", { name: "Apuestas" }));
    expect(within(screen.getByRole("table", { name: "Apuestas del experimento" })).getAllByRole("columnheader", { name: /Resultado/ })).toHaveLength(1);
    first.unmount();
    for (const status of ["held", "failed"] as const) {
      vi.mocked(apiClient.getExperiment).mockResolvedValueOnce({ ...profileSnapshot, status, runs: [{ ...profileSnapshot.runs[0], status: status === "held" ? "pending" : "failed", result: null, bets_count: 0 }] });
      const view = setup();
      expect(await screen.findByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
      expect(apiClient.getReplay).toHaveBeenCalledTimes(1);
      view.unmount();
    }
  });
});

describe("profile batch v5 detail", () => {
  it("uses saved identity, frozen references, backend metrics, stop scope, and canonical replay indexes", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(batchV5Snapshot);
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 5, total: 1, offset: 0, limit: 20, items: [
      { label: "2025-01-01 05:10", stakes: [[7, 125], [8, 125]], results: [7, 8, 9], wagered: 250, paid: 0, balance: 9750, source_index: 5, bet_index: 0 },
    ] });
    const { user } = setup();
    const run = await screen.findByRole("region", { name: "Ejecución 1" });
    expect(screen.getByRole("heading", { name: "Lote guardado · Snapshot cold" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Snapshot cold" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver comparación" })).toHaveAttribute("href", "/experimentos/exp/comparacion");
    expect(screen.getByText("Neto").nextElementSibling).toHaveTextContent("-USD 2.50");
    expect(screen.getByText("Clasificación de parada").nextElementSibling).toHaveTextContent("Límite configurado");
    const stopDetails = Array.from(run.querySelectorAll("details")).find((details) => details.textContent?.includes("Categoría de parada (código)"));
    expect(stopDetails).toBeDefined();
    await user.click(within(stopDetails!).getByText("Detalles técnicos"));
    expect(screen.getByText("Categoría de parada (código)").nextElementSibling).toHaveTextContent("configured_limit");
    expect(screen.getByText("Motivo informado").nextElementSibling).toHaveTextContent("max_bet_draws");
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(screen.getByText("Estrategia").nextElementSibling).toHaveTextContent("Snapshot cold · revisión 2");
    const parameters = screen.getByRole("region", { name: "Ejecución 1" });
    const identityDetails = Array.from(parameters.querySelectorAll("details")).find((details) => details.textContent?.includes("ID de estrategia"));
    expect(identityDetails).toBeDefined();
    await user.click(within(identityDetails!).getByText("Detalles técnicos"));
    expect(within(identityDetails!).getByText("ID de estrategia").nextElementSibling).toHaveTextContent("strategy-old");
    expect(within(identityDetails!).getByText("SHA-256 de definición").nextElementSibling).toHaveTextContent("c".repeat(64));
    expect(within(identityDetails!).getByText("Fuente canónica SHA-256").nextElementSibling).toHaveTextContent("e".repeat(64));
    expect(screen.getByText("Filas de la fuente").nextElementSibling).toHaveTextContent("8");
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    const table = await screen.findByRole("table", { name: "Apuestas del experimento" });
    expect(within(table).getByText("5")).toBeInTheDocument();
    expect(within(table).getByText("1")).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
  });
  it.each([
    ["pending", "pending", "unknown", "pending"],
    ["held", "pending", "unknown", "pending"],
    ["cancelled", "cancelled", "interrupted", "cancelled"],
    ["failed", "failed", "unknown", "failed"],
  ] as const)("shows v5 %s without claiming metrics or replay", async (status, runStatus, stopCategory, reason) => {
    const run = batchV5Snapshot.runs[0];
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...batchV5Snapshot, status, runs: [{ ...run,
      status: runStatus, result_schema_version: null, result: null, bets_count: 0, complete: false,
      completion: "unavailable" as const, stop_category: stopCategory, stop_reason: reason, stop_code: stopCategory,
      error: status === "failed" ? "strategy failed" : null,
    }] });
    const { unmount } = setup();
    const view = await screen.findByRole("region", { name: "Ejecución 1" });
    expect(within(view).getByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
    expect(within(view).queryByRole("region", { name: "Métricas financieras" })).not.toBeInTheDocument();
    expect(apiClient.getReplay).not.toHaveBeenCalled();
    unmount();
  });
  it("keeps mixed strategy failures ordinal-local without financial zeros", async () => {
    const failed = { ...batchV5Snapshot.runs[0], ordinal: 1, status: "failed" as const, result_schema_version: null,
      strategy: { id: "strategy-new", revision: 1, definition_sha256: "f".repeat(64), name: null }, result: null,
      bets_count: 0, complete: false, completion: "unavailable" as const, stop_category: "unknown" as const,
      stop_reason: "failed", stop_code: "unknown", error: "strategy failed" };
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...batchV5Snapshot, status: "failed", runs: [
      { ...batchV5Snapshot.runs[0], status: "completed" },
      failed,
    ] });
    const { user } = setup();
    await screen.findByRole("region", { name: "Ejecución 1" });
    await user.click(screen.getByRole("button", { name: /2\. Estrategia 2/ }));
    const run = screen.getByRole("region", { name: "Ejecución 2" });
    expect(within(run).getByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
    await user.click(within(run).getByText("Detalles técnicos"));
    expect(within(run).getByText("Categoría de parada (código)").nextElementSibling).toHaveTextContent("unknown");
    expect(within(run).getByText("Motivo informado").nextElementSibling).toHaveTextContent("failed");
    expect(within(run).getByText("Error").nextElementSibling).toHaveTextContent("strategy failed");
    expect(within(run).queryByRole("region", { name: "Métricas financieras" })).not.toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledExactlyOnceWith("exp", 0, 0, 20);
  });
  it("labels history_exhausted as an incomplete operational window when the backend category says so", async () => {
    const savedRun = batchV5Snapshot.runs[0];
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...batchV5Snapshot, batch_admission: { ...batchV5Snapshot.batch_admission, source_identity: { ...batchV5Snapshot.batch_admission.source_identity, row_count: 10 } }, runs: [{ ...savedRun,
      complete: false, completion: "incomplete" as const, stop_category: "operational_window" as const, stop_reason: "bounded draw window ended before source end",
      result: { ...savedRun.result!, outcome: "history_exhausted", collisions: [], elapsed_draws: 3, source_count: 10, complete: false, stop_category: "operational_window" as const, stop_reason: "bounded draw window ended before source end" },
    }] });
    const { user } = setup();
    const run = await screen.findByRole("region", { name: "Ejecución 1" });
    expect(screen.getByText("Motivo de cierre").nextElementSibling).toHaveTextContent("Ventana operativa; fuente incompleta");
    expect(screen.getByText("Clasificación de parada").nextElementSibling).toHaveTextContent("Ventana operativa; fuente incompleta");
    const stopDetails = Array.from(run.querySelectorAll("details")).find((details) => details.textContent?.includes("Categoría de parada (código)"));
    expect(stopDetails).toBeDefined();
    await user.click(within(stopDetails!).getByText("Detalles técnicos"));
    expect(screen.getByText("Categoría de parada (código)").nextElementSibling).toHaveTextContent("operational_window");
    expect(screen.getByText("Motivo informado").nextElementSibling).toHaveTextContent("bounded draw window ended before source end");
    expect(screen.queryByText("Historial agotado")).not.toBeInTheDocument();
    expect(screen.queryByText("Fin de la fuente guardada")).not.toBeInTheDocument();
  });
  it("keeps Historial agotado when v5 reports the actual full-source end", async () => {
    const savedRun = batchV5Snapshot.runs[0];
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...batchV5Snapshot, runs: [{ ...savedRun, complete: true, completion: "complete" as const,
      stop_category: "source_end" as const, stop_reason: "full saved source ended",
      result: { ...savedRun.result!, outcome: "history_exhausted", collisions: [], elapsed_draws: 3, complete: true, stop_category: "source_end" as const, stop_reason: "full saved source ended" },
    }] });
    const { user } = setup();
    await screen.findByText("Historial agotado");
    expect(screen.getByText("Clasificación de parada").nextElementSibling).toHaveTextContent("Fin de la fuente guardada");
    expect(screen.queryByText("Ventana operativa; fuente incompleta")).not.toBeInTheDocument();
    const run = screen.getByRole("region", { name: "Ejecución 1" });
    const stopDetails = Array.from(run.querySelectorAll("details")).find((details) => details.textContent?.includes("Categoría de parada (código)"));
    expect(stopDetails).toBeDefined();
    await user.click(within(stopDetails!).getByText("Detalles técnicos"));
    expect(within(stopDetails!).getByText("Categoría de parada (código)").nextElementSibling).toHaveTextContent("source_end");
    expect(within(stopDetails!).getByText("Motivo informado").nextElementSibling).toHaveTextContent("full saved source ended");
  });
});

describe("LW11 detail", () => {
  it("jumps directly to an exact source bet beyond page 20 from a comparison link", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...snapshot, status: "completed", runs: [{ ...snapshot.runs[0], bets_count: 1001, result: { ...snapshot.runs[0].result!, bets_count: 1001 } }] });
    vi.mocked(apiClient.getReplay).mockResolvedValue({ total: 1001, offset: 600, limit: 20, items: [bet] });
    setup("/experimentos/exp?run=0&bet=600&from=comparison");
    expect(await screen.findByText(/Apuesta seleccionada 601:/)).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledExactlyOnceWith("exp", 0, 600, 20);
    expect(screen.getByRole("tab", { name: "Apuestas" })).toHaveAttribute("aria-selected", "true");
  });
  it("displays backend metrics with profile money and no browser recomputation", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...profileSnapshot, runs: [{ ...profileSnapshot.runs[0], result: { ...profileSnapshot.runs[0].result!, net: 777, max_drawdown: 123, return_per_wagered: 0.456789, roi: -0.543211 } }] });
    setup();
    await screen.findByRole("region", { name: "Métricas financieras" });
    expect(screen.getByText("Neto").nextElementSibling).toHaveTextContent("USD 7.77");
    expect(screen.getByText("Máximo drawdown absoluto").nextElementSibling).toHaveTextContent("USD 1.23");
    expect(screen.getByText("Retorno por peso apostado").nextElementSibling).toHaveTextContent("0.456789");
  });
  it.each([
    [40, "RD$40"],
    [-15, "-RD$15"],
    [0, "RD$0"],
  ])("shows the API-projected delta %i without subtracting balances in the browser", async (delta, displayed) => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({
      ...snapshot,
      runs: [{ ...snapshot.runs[0], result: { ...snapshot.runs[0].result!, delta } }, snapshot.runs[1]],
    });
    setup();
    await screen.findByText("Prueba");
    expect(screen.getByText("Cambio respecto del inicio").nextElementSibling).toHaveTextContent(displayed);
    expect(screen.getByText("Cambio respecto del inicio").nextElementSibling).not.toHaveTextContent("No disponible");
  });

  it("shows an absent net as N/A without confusing it with the delta or a zero", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...snapshot, status: "completed", runs: [{ ...snapshot.runs[0], result: { ...snapshot.runs[0].result!, delta: 40 } }, snapshot.runs[1]] });
    setup();
    await screen.findByText("Prueba");
    expect(screen.getByText("Neto").nextElementSibling).toHaveTextContent("N/A");
    expect(screen.getByText("Cambio respecto del inicio").nextElementSibling).toHaveTextContent("RD$40");
    expect(screen.getByText("Neto").nextElementSibling).not.toHaveTextContent("RD$");
    expect(screen.getByText("Cambio respecto del inicio").nextElementSibling).not.toHaveTextContent("N/A");
  });

  it("does not invent a delta for an incomplete run in a partially completed experiment", async () => {
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("button", { name: /Segunda/ }));
    const run = screen.getByRole("region", { name: "Ejecución 2" });
    expect(within(run).getByText(/no tiene un resultado guardado/i)).toBeInTheDocument();
    expect(within(run).queryByText("Cambio respecto del inicio")).not.toBeInTheDocument();
  });

  it("shows the delta help text and the historical-simulation caveat next to the result summary", async () => {
    setup();
    await screen.findByText("Prueba");
    expect(screen.getByText("Diferencia entre el saldo final y el capital inicial")).toBeInTheDocument();
    expect(screen.getByText(/Simulación con datos históricos: no predice resultados futuros/)).toBeInTheDocument();
  });

  it("maps saved selector and staking to plain labels in Parámetros, never the raw enum keys", async () => {
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(screen.getByText("Un sistema de selección")).toBeInTheDocument();
    expect(screen.getByText("Plana")).toBeInTheDocument();
    expect(screen.getByText("Sumar los premios")).toBeInTheDocument();
    expect(screen.getByText(/Resultados sobre datos históricos ya investigados: no constituyen una validación independiente/)).toBeInTheDocument();
    expect(screen.queryByText("Todas las posiciones")).not.toBeInTheDocument();
    expect(screen.queryByText("system")).not.toBeInTheDocument();
    expect(screen.queryByText("flat")).not.toBeInTheDocument();
    expect(screen.queryByText("all")).not.toBeInTheDocument();
  });
  it("keeps the stable URL, separates execution from outcome, and never assigns an outcome to a null run", async () => {
    const { router, user } = setup();
    expect(await screen.findByText("Prueba")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/experimentos/exp");
    expect(screen.getByText("Meta alcanzada")).toHaveAttribute("data-status-kind", "outcome");
    await user.click(screen.getByRole("button", { name: /Segunda/ }));
    expect(within(screen.getByRole("region", { name: "Ejecución 2" })).getByText("En curso")).toHaveAttribute("data-status-kind", "execution");
    expect(screen.queryByText("Meta alcanzada")).not.toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
    expect(apiClient.getReplay).not.toHaveBeenCalledWith("exp", 1, 0, 20);
  });

  it("shows persisted bet data with padded numbers and DOP, bounded pagination and expandable detail", async () => {
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 0, 20);
    const table = screen.getByRole("table", { name: "Apuestas del experimento" });
    expect(within(table).getByText("00, 07")).toBeInTheDocument();
    expect(within(table).getByText("RD$10")).toBeInTheDocument();
    await user.click(within(table).getByRole("button", { name: /Detalle/ }));
    expect(screen.getByText("00, 03, 07, 08, 09")).toBeInTheDocument();
  });

  it("does not replace an existing snapshot with a stale response after navigating to another id", async () => {
    let finish!: (value: ExperimentSummary) => void;
    vi.mocked(apiClient.getExperiment).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; })).mockResolvedValueOnce({ ...snapshot, id: "other", request: { ...snapshot.request, name: "Otra" } });
    const { router } = setup();
    await act(async () => { await router.navigate("/experimentos/other"); });
    expect(await screen.findByText("Otra")).toBeInTheDocument();
    await act(async () => { finish(snapshot); });
    await waitFor(() => expect(screen.queryByText("Prueba")).not.toBeInTheDocument());
  });

  it("distinguishes missing record, disconnection and a replay conflict", async () => {
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new ApiError(404, "missing"));
    const first = setup();
    expect(await screen.findByRole("alert")).toHaveTextContent(/no existe/i);
    first.unmount();
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new NetworkError());
    const second = setup();
    expect(await screen.findByRole("alert")).toHaveTextContent(/contactar al servidor/i);
    second.unmount();
    vi.mocked(apiClient.getReplay).mockRejectedValueOnce(new ApiError(409, "no result"));
    setup();
    expect(await screen.findByRole("alert")).toHaveTextContent(/reproducción.*disponible/i);
  });

  it("polls a nonterminal snapshot without changing the URL, then stops after completion", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValueOnce(snapshot).mockResolvedValueOnce({ ...snapshot, status: "completed" });
    vi.useFakeTimers();
    const { router, unmount } = setup();
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText("Prueba")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(2);
    expect(router.state.location.pathname).toBe("/experimentos/exp");
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(2);
    unmount();
    vi.useRealTimers();
  });

  it("requests only the next bounded page and ignores an old replay response after switching runs", async () => {
    let resolveReplay!: (value: Page<Bet>) => void;
    vi.mocked(apiClient.getReplay).mockReturnValueOnce(new Promise((resolve) => { resolveReplay = resolve; }));
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("button", { name: /Segunda/ }));
    await act(async () => { resolveReplay(page); });
    expect(screen.queryByText(/Sorteo mostrado:/)).not.toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledTimes(1);
  });

  it("pages a long replay on demand, without requesting all bets", async () => {
    const many = { ...snapshot, status: "completed" as const, runs: [{ ...snapshot.runs[0], bets_count: 21, result: { ...snapshot.runs[0].result!, bets_count: 21 } }] };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(many);
    vi.mocked(apiClient.getReplay).mockResolvedValueOnce({ total: 21, offset: 0, limit: 20, items: Array.from({ length: 20 }, (_, index) => ({ ...bet, label: `2026-01-02T10:${String(index).padStart(2, "0")}:00` })) }).mockResolvedValueOnce({ total: 21, offset: 20, limit: 20, items: [{ ...bet, label: "2026-01-02T11:00:00" }] });
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("tab", { name: "Apuestas" }));
    await screen.findByRole("table", { name: "Apuestas del experimento" });
    await user.click(screen.getByRole("button", { name: "Página siguiente" }));
    await screen.findByText("2026-01-02 11:00:00");
    await user.click(screen.getByRole("tab", { name: "Resultado" }));
    expect(screen.getByText(/Sorteo mostrado: 21 de 21/)).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenNthCalledWith(2, "exp", 0, 20, 20);
    expect(apiClient.getReplay).toHaveBeenCalledTimes(2);
  });

  it("supports keyboard tabs and play/pause with one visual timer, leaving final metrics unchanged", async () => {
    const two = { ...snapshot, status: "completed" as const, runs: [{ ...snapshot.runs[0], bets_count: 2, result: { ...snapshot.runs[0].result!, bets_count: 2 } }] };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(two);
    vi.mocked(apiClient.getReplay).mockResolvedValue({ total: 2, offset: 0, limit: 20, items: [bet, { ...bet, label: "2026-01-02T10:10:00", balance: 120 }] });
    const { user, unmount } = setup();
    await screen.findByText("Prueba");
    await screen.findByText(/Apuesta 2:/);
    const final = screen.getByText("Saldo final").parentElement?.textContent;
    const resultTab = screen.getByRole("tab", { name: "Resultado" });
    resultTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Apuestas" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(resultTab).toHaveFocus();
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Reproducir" }));
    expect(screen.getByRole("button", { name: "Pausar" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pausar" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getByText(/Sorteo mostrado: 1 de 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reproducir" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText(/Sorteo mostrado: 2 de 2/)).toBeInTheDocument();
    expect(screen.getByText("Saldo final").parentElement?.textContent).toBe(final);
    unmount(); vi.useRealTimers();
  });

  it("has no automated accessibility violations in a completed detail", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...snapshot, status: "completed" });
    const { container } = setup();
    await screen.findByText(/Apuesta 1:/);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("keeps final metrics and sources unchanged while replay cursor moves, without mutations", async () => {
    const { user } = setup();
    await screen.findByText("Prueba");
    const final = screen.getByText(/Saldo final/).parentElement?.textContent;
    await user.click(screen.getByRole("button", { name: "Siguiente sorteo" }));
    expect(screen.getByText(/Sorteo mostrado/)).toBeInTheDocument();
    expect(screen.getByText(/Saldo final/).parentElement?.textContent).toBe(final);
    await user.click(screen.getByRole("tab", { name: "Parámetros y datos" }));
    expect(screen.getByText("history.json")).toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
});
