import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, CompareResult, ExperimentSummary, Page, ProfileBatchExperimentSummary, ProfileBatchRunSummary, ProfileCompareResult, ProfileExperimentSummary, ReplayPage } from "../../api/types";

vi.mock("../../api/client", async (original) => {
  const actual = await original<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getExperiment: vi.fn(), compareExperiment: vi.fn(), getReplay: vi.fn(), getTrajectory: vi.fn(), createExperiment: vi.fn() } };
});
const bet = (label: string, balance: number): Bet => ({ label, balance, numbers: [1], results: [1, 2, 3, 4, 5], per_number: 1, wagered: 1, paid: 0 });
const runs: CompareResult["runs"] = [
  { ordinal: 0, configuration_id: "a", status: "completed", bets_count: 2, result: { outcome: "goal", bets_count: 2, final_balance: 150, delta: 50, paid: 60, wagered: 10 } },
  { ordinal: 1, configuration_id: "b", status: "running", bets_count: 1, result: null },
];
const detail: ExperimentSummary = { id: "exp", status: "running", request: { name: "Ensayo", conditions: { start_draw: "2025-01-01 10:00", capital: 100, goal: 200, seed: 7, settlement: "all" }, strategies: [
  { name: "Primera", selector: "system", system: "cold", coverage: 1, staking: "flat" },
  { name: "Segunda", selector: "random", coverage: 1, staking: "flat" },
] }, sources: { history_id: "hist", history_sha256: "hash-h", rankings_id: "ranks", rankings_sha256: "hash-r", code_version: "v1" }, runs };
const comparison: CompareResult = { id: "exp", status: "running", completed: 1, requested: 2, complete: false, runs };
const profileDetail: ProfileExperimentSummary = {
  id: "exp", status: "completed", request_kind: "profile", created_at: null,
  request: { kind: "profile", schema_version: 1, name: "Perfil EUR", dataset_sha256: "a".repeat(64), profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
    conditions: { schema_version: 1, start_draw: "2025-01-01 10:00", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 3, max_bet_draws: 1, end_minute: null, duration_minutes: null },
    selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1, numbers: [7], seed: null, algorithm_version: null },
    staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 100 } },
  profile: { schema_version: 1, profile_id: "test", revision: 1, universe_size: 100, positions: 3, allows_repeats: true, multipliers: [80, 8, 4].map((numerator) => ({ numerator, denominator: 1 })), currency: "EUR", scale: 2, stake_increment: 1, minimum_stake: 1, maximum_stake: 100000, max_coverage: 10, max_exposure: 100000, best_rule: "maximum-payout/v1" },
  display: { name: "Perfil EUR", currency: "EUR", scale: 2, capital: 10000, goal: 20000, selector_label: "static-numbers/v1", staking_label: "flat-per-number/v1" },
  sources: { history_id: "a", history_sha256: "a", rankings_id: "", rankings_sha256: "", code_version: "profile-v1" },
  runs: [{ ordinal: 0, configuration_id: null, status: "completed", result_kind: "profile", bets_count: 1,
    result: { schema_version: 1, profile_id: "test", profile_revision: 1, outcome: "limit", collisions: ["max_bet_draws"], elapsed_draws: 3, bet_draws: 1, wagered: 100, paid: 0, final_balance: 9900, delta: -100 } }],
};
const profileCompare: ProfileCompareResult = { id: "exp", status: "completed", request_kind: "profile", completed: 1, requested: 1, complete: true, runs: profileDetail.runs };
const profileReplay: ReplayPage = { result_kind: "profile", total: 1, offset: 0, limit: 100, items: [{ label: "2025-01-01 10:00", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] };
const batchNames = ["Frozen A", "Frozen B", "Frozen C"];
const batchStrategies = batchNames.map((name) => ({ definition_version: 1 as const, name, selector: "static-numbers/v1" as const, coverage: 1, staking: "flat-per-number/v1" as const, selector_parameters: { numbers: [7] }, staking_parameters: {}, closing_defaults: {} }));
const batchRefs = batchNames.map((_, ordinal) => ({ id: `frozen-${ordinal}`, revision: ordinal + 4, definition_sha256: String.fromCharCode(97 + ordinal).repeat(64) }));
const batchSuccess: ProfileBatchRunSummary = {
  result_kind: "profile", ordinal: 0, configuration_id: null, status: "completed", result_schema_version: 5,
  strategy: { ...batchRefs[0], name: batchNames[0] }, bets_count: 2, complete: false, completion: "incomplete",
  stop_category: "operational_window", stop_reason: "bounded draw window ended before source end", stop_code: "operational_window", error: null,
  result: { schema_version: 5, profile_id: "test", profile_revision: 1, outcome: "history_exhausted", collisions: [], elapsed_draws: 4, bet_draws: 2, wagered: 500, paid: 1250, final_balance: 10750, delta: 750, net: 750, return_per_wagered: 2.5, roi: 1.5, max_drawdown: 125, metric_scope: "saved_individual_run", ratio_rounding: "decimal-half-up-6", definition_name: batchNames[0], start_draw_index: 5, prior_cutoff: "2024-12-31 05:10", dataset_sha256: "a".repeat(64), source_count: 15, requested_conditions: { max_draws: 4 }, effective_conditions: { max_draws: 4 }, stop_category: "operational_window", stop_reason: "bounded draw window ended before source end", complete: false },
};
const batchFailed: ProfileBatchRunSummary = { result_kind: "profile", ordinal: 2, configuration_id: null, status: "failed", result_schema_version: null, strategy: { ...batchRefs[2], name: null }, result: null, bets_count: 0, complete: false, completion: "unavailable", stop_category: "unknown", stop_reason: "failed", stop_code: "unknown", error: "strategy-local failure" };
const batchCancelled: ProfileBatchRunSummary = { result_kind: "profile", ordinal: 1, configuration_id: null, status: "cancelled", result_schema_version: null, strategy: { ...batchRefs[1], name: null }, result: null, bets_count: 0, complete: false, completion: "unavailable", stop_category: "interrupted", stop_reason: "cancelled", stop_code: "interrupted", error: null };
const batchV5Detail: ProfileBatchExperimentSummary = {
  request_kind: "profile", request_schema_version: 5, id: "exp", status: "failed", created_at: null,
  request: { schema_version: 5, kind: "profile_batch", profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), dataset_sha256: "a".repeat(64), conditions: { schema_version: 1, start_draw: "2025-01-01 10:00", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 4, max_bet_draws: 2, end_minute: null, duration_minutes: null }, strategies: batchStrategies, max_draws: 4, source_version: "canonical-history/v1" },
  profile: profileDetail.profile, display: { ...profileDetail.display, name: "Batch saved identity" }, sources: profileDetail.sources,
  batch_admission: { strategy_refs: batchRefs, source_identity: { dataset_sha256: "a".repeat(64), source_sha256: "d".repeat(64), canonical_sha256: "e".repeat(64), row_count: 15, profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null }, requested_constraints: { max_draws: 4, max_elapsed_draws: 4 }, effective_constraints: { max_draws: 4, max_elapsed_draws: 4 }, policy_revision: 2, policy: { worker_count: 1 } },
  runs: [batchFailed, batchSuccess, batchCancelled],
};
const batchCompare: CompareResult = { id: "exp", status: "failed", request_kind: "profile", completed: 1, requested: 3, complete: false, runs: [batchFailed, batchSuccess, batchCancelled] };
const page = (ordinal: number, offset = 0): Page<Bet> => ({ offset, limit: 100, total: ordinal ? 1 : 101, items: offset ? [bet("2025-01-01 11:00", 150)] : ordinal ? [bet("2025-01-01 10:30", 110)] : Array.from({ length: 100 }, (_, i) => bet(`2025-01-01 10:${String(i % 60).padStart(2, "0")}`, 101 + i)) });
function setup(path = "/experimentos/exp/comparacion") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return { router, user: userEvent.setup(), ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(apiClient.getExperiment).mockReset().mockResolvedValue(detail);
  vi.mocked(apiClient.compareExperiment).mockReset().mockResolvedValue(comparison);
  vi.mocked(apiClient.getTrajectory).mockReset().mockImplementation(async (_id, ordinal) => {
    const latest = vi.mocked(apiClient.getExperiment).mock.results.at(-1);
    const saved = await latest?.value;
    const run = saved?.runs.find((r: { ordinal: number }) => r.ordinal === ordinal);
    const total = run?.result?.bet_draws ?? run?.result?.bets_count ?? 0;
    const capital = saved?.request.conditions.capital ?? 100;
    const end = run?.result?.final_balance ?? capital;
    return { initial_capital: capital, total, max_points: 500, reduction_method: "none",
      minimum: { balance: Math.min(capital, end), source_index: null }, maximum: { balance: Math.max(capital, end), source_index: null },
      points: Array.from({ length: Math.min(total, 500) }, (_, i) => ({ source_index: i, label: `2025-01-01 10:${String(i % 60).padStart(2, "0")}`, balance: end, replay: `replay?offset=${i}&limit=1` })) };
  });
  vi.mocked(apiClient.getReplay).mockReset().mockImplementation(async (_id, ordinal, offset) => page(ordinal, offset));
  vi.mocked(apiClient.createExperiment).mockReset();
});
describe("profile comparison READ", () => {
  it("compares completed cycling from schema-2 summaries and replay without flat-stake assumptions", async () => {
    const cycling: ProfileExperimentSummary = {
      ...profileDetail, status: "completed",
      request: { ...profileDetail.request, schema_version: 2, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } },
      display: { ...profileDetail.display, staking_label: "Escalera cíclica Q80 · apuesta dinámica por sorteo" },
      runs: [{ ...profileDetail.runs[0], status: "completed", result: { ...profileDetail.runs[0].result!, schema_version: 2 } }],
    };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(cycling);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...profileCompare, runs: cycling.runs });
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 2, total: 1, offset: 0, limit: 100, items: [{ label: "2025-01-01 10:00", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] });
    setup();
    const table = await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent(/EUR 99.00.*-EUR 1.00.*1.*3/);
    expect(await screen.findByText(/Perfil EUR: 1 de 1 apuestas/)).toBeInTheDocument();
    expect(screen.getByText("Datos de origen")).toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("compares schema-3 Audaz with dynamic stake and completed replay", async () => {
    const audaz: ProfileExperimentSummary = { ...profileDetail,
      request: { ...profileDetail.request, schema_version: 3, staking: { schema_version: 1, capability: "profile-audaz/v1" } },
      display: { ...profileDetail.display, staking_label: "Audaz · apuesta dinámica por sorteo" },
      runs: [{ ...profileDetail.runs[0], result: { ...profileDetail.runs[0].result!, schema_version: 3 } }],
    };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(audaz);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...profileCompare, runs: audaz.runs });
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 3, total: 1, offset: 0, limit: 100,
      items: [{ label: "2025-01-01 10:00", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] });
    setup();
    const table = await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent(/EUR 99.00.*-EUR 1.00.*Límite de sesión.*1.*3/);
    expect(await screen.findByText(/Perfil EUR: 1 de 1 apuestas/)).toBeInTheDocument();
    expect(apiClient.getTrajectory).toHaveBeenCalledWith("exp", 0, 500);
  });
  it.each([["cycle", "Reiniciar la escalera"], ["stop", "Detener la sesión"]] as const)("compares schema-4 recovery with stored version and %s parameters", async (end_mode, ending) => {
    const recovery: ProfileExperimentSummary = { ...profileDetail,
      request: { ...profileDetail.request, schema_version: 4, staking: { schema_version: 1, target_margin: 500, rounds: 3, end_mode } },
      display: { ...profileDetail.display, staking_label: "Escalera de recuperación · parámetros explícitos por perfil" },
      runs: [{ ...profileDetail.runs[0], result: { ...profileDetail.runs[0].result!, schema_version: 4, collisions: ["recovery_round_limit"] } }],
    };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(recovery);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...profileCompare, runs: recovery.runs });
    vi.mocked(apiClient.getReplay).mockResolvedValue({ result_kind: "profile", schema_version: 4, total: 1, offset: 0, limit: 100,
      items: [{ label: "2025-01-01 10:00", stakes: [[7, 100]], results: [7, 8, 9], wagered: 100, paid: 0, balance: 9900 }] });
    setup();
    await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    await userEvent.setup().click(screen.getByText("Detalles técnicos"));
    expect(screen.getByText("Versión de solicitud").nextElementSibling).toHaveTextContent("Perfil v4");
    expect(screen.getByText("Resultado · Perfil EUR").nextElementSibling).toHaveTextContent("Perfil v4");
    expect(screen.getByText("EUR 5.00")).toBeInTheDocument();
    expect(screen.getByText(ending)).toBeInTheDocument();
    expect(await screen.findByText(/Perfil EUR: 1 de 1 apuestas/)).toBeInTheDocument();
  });
  it("uses neutral dataset language when profile source kind is unavailable", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(profileDetail);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue(profileCompare);
    setup();
    await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(screen.getByText("Simulación con datos del conjunto seleccionado: no predice resultados futuros ni garantiza rentabilidad.")).toBeInTheDocument();
    expect(screen.getByText("Datos de origen")).toBeInTheDocument();
    expect(screen.getByText("SHA-256 de datos de origen")).toBeInTheDocument();
    expect(screen.getByText("Evolución comparada · fechas guardadas")).toBeInTheDocument();
    expect(screen.queryByText(/datos históricos|Resultados históricos|fechas históricas|^Historial$|^SHA-256 historial$/i)).not.toBeInTheDocument();
  });

  it("shows server delta and elapsed versus bet draws with profile currency in table and chart", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(profileDetail);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue(profileCompare);
    vi.mocked(apiClient.getReplay).mockResolvedValue(profileReplay);
    setup();
    const table = await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent(/EUR 99.00.*-EUR 1.00.*Límite de sesión.*1.*3/);
    expect(screen.getByText("Capital").nextElementSibling).toHaveTextContent("EUR 100.00");
    expect(await screen.findByText(/Perfil EUR: 1 de 1 apuestas/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Datos textuales del gráfico" })).toHaveTextContent("EUR 99.00");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it.each(["held", "failed"] as const)("shows %s with no fabricated result or replay", async (status) => {
    const runs = [{ ...profileDetail.runs[0], status: status === "held" ? "pending" as const : "failed" as const, result: null, bets_count: 0 }];
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...profileDetail, status, runs });
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...profileCompare, status, completed: 0, complete: false, runs });
    setup();
    const table = await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[1]).not.toHaveTextContent("EUR 99.00");
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("—");
    expect(apiClient.getReplay).not.toHaveBeenCalled();
  });
});

describe("profile batch v5 comparison", () => {
  it("shows frozen ordered strategies, saved server metrics, incomplete operational windows, and local bet continuity", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(batchV5Detail);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue(batchCompare);
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ result_kind: "profile", schema_version: 5, initial_capital: 10000, total: 2, max_points: 500, reduction_method: "none",
      minimum: { balance: 9750, source_index: 5, bet_index: 0 }, maximum: { balance: 10750, source_index: 8, bet_index: 1 },
      points: [{ source_index: 5, bet_index: 0, label: "2025-01-01 10:10", balance: 9750, replay: "replay?offset=0&limit=1" }, { source_index: 8, bet_index: 1, label: "2025-01-01 10:40", balance: 10750, replay: "replay?offset=1&limit=1" }] });
    const { user } = setup();
    expect(await screen.findByText("Comparación incompleta · 1/3 terminadas")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Batch saved identity" })).toBeInTheDocument();
    const experimentStatus = screen.getByText(/Estado:/).parentElement;
    expect(experimentStatus && within(experimentStatus).getByText("Con error")).toHaveAttribute("data-status-value", "failed");
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent(/Frozen A.*EUR 107.50.*EUR 7.50.*EUR 5.00.*EUR 12.50.*2\.500000.*1\.500000.*EUR 1.25/);
    expect(rows[1]).toHaveTextContent(/Ventana operativa; fuente incompleta.*bounded draw window ended before source end/);
    expect(rows[1]).toHaveTextContent("Ventana operativa; fuente incompleta");
    expect(rows[1]).not.toHaveTextContent("Historial agotado");
    expect(rows[2]).toHaveTextContent(/Frozen B.*Cancelado.*N\/A/);
    expect(rows[3]).toHaveTextContent(/Frozen C.*Con error.*strategy-local failure/);
    expect(screen.queryByText("Fin de la fuente guardada")).not.toBeInTheDocument();
    await user.click(screen.getByText("Condiciones y datos de origen"));
    expect(screen.getByText("Definiciones congeladas").nextElementSibling).toHaveTextContent(`frozen-0 · revisión 4 · SHA-256 ${"a".repeat(64)}`);
    expect(within(rows[1]).getAllByText(/Ventana operativa; fuente incompleta/)).toHaveLength(2);
    expect(screen.getByText(/Límites efectivos guardados/).nextElementSibling).toHaveTextContent(/max_draws.*4/);
    expect(await screen.findByText(/Frozen A: 2 de 2 apuestas/)).toBeInTheDocument();
    const chart = screen.getByRole("figure", { name: /Evolución comparada/ });
    expect(within(chart).getByTestId("series-0").getAttribute("points")?.split(" ")).toHaveLength(3);
    expect(apiClient.getTrajectory).toHaveBeenCalledExactlyOnceWith("exp", 0, 500);
    expect(apiClient.getReplay).not.toHaveBeenCalled();
  });
  it("labels history exhaustion only for a backend-classified full-source end", async () => {
    const exhausted: ProfileBatchRunSummary = { ...batchSuccess, complete: true, completion: "complete", stop_category: "source_end", stop_reason: "full saved source ended", stop_code: "source_end",
      result: { ...batchSuccess.result!, outcome: "history_exhausted", elapsed_draws: 4, source_count: 9, complete: true, stop_category: "source_end", stop_reason: "full saved source ended" } };
    const detail: ProfileBatchExperimentSummary = { ...batchV5Detail, status: "completed", batch_admission: { ...batchV5Detail.batch_admission, source_identity: { ...batchV5Detail.batch_admission.source_identity, row_count: 9 } }, runs: [exhausted] };
    const comparison: CompareResult = { ...batchCompare, status: "completed", completed: 1, requested: 1, complete: true, runs: [exhausted] };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue(comparison);
    setup();
    const row = within(await screen.findByRole("table", { name: "Comparación de ejecuciones" })).getAllByRole("row")[1];
    expect(row).toHaveTextContent("Historial agotado");
    expect(row).toHaveTextContent("Fin de la fuente guardada");
    expect(row).not.toHaveTextContent("Ventana operativa; fuente incompleta");
  });
  it("keeps all nonterminal v5 rows resultless and out of the chart", async () => {
    const pendingRuns: ProfileBatchRunSummary[] = batchV5Detail.runs.map((run) => ({ ...run, status: "pending", result_schema_version: null, result: null, bets_count: 0, complete: false, completion: "unavailable", stop_category: "unknown", stop_reason: "pending", stop_code: "unknown", error: null }));
    const detail: ProfileBatchExperimentSummary = { ...batchV5Detail, status: "running", runs: pendingRuns };
    const progress: CompareResult = { ...batchCompare, status: "running", completed: 0, complete: false, runs: pendingRuns };
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail);
    vi.mocked(apiClient.compareExperiment).mockResolvedValue(progress);
    vi.mocked(apiClient.getTrajectory).mockReset();
    setup();
    expect(await screen.findByText("Comparación incompleta · 0/3 terminadas")).toBeInTheDocument();
    expect(screen.getByText(/Estado:/).parentElement).toHaveTextContent("En curso");
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row").slice(1)).toHaveLength(3);
    expect(within(table).getAllByText("N/A").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Todavía no hay apuestas guardadas cargadas para graficar.")).toHaveAttribute("role", "status");
    expect(apiClient.getTrajectory).not.toHaveBeenCalled();
    expect(apiClient.getReplay).not.toHaveBeenCalled();
  });
});

describe("LW12 comparison", () => {
  it("uses server N/M and delta, shows absent values as dashes, and separates outcome from execution", async () => {
    setup();
    expect(await screen.findByText("Comparación incompleta · 1/2 terminadas")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent(/Primera.*Ejecución completada.*RD\$150.*RD\$50.*Meta alcanzada.*2/);
    expect(rows[2]).toHaveTextContent(/Segunda.*En curso.*—.*—.*—.*—/);
    expect(within(rows[2]).queryByText("Meta alcanzada")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Comparación de ejecuciones" })).toHaveClass("overflow-x-auto");
    expect(screen.getByText("hash-h")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/mejor estrategia|probabilidad de éxito|exportar/i);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    expect(apiClient.getReplay).not.toHaveBeenCalledWith("exp", 1, 0, 100);
  });
  it("labels the delta column and places the historical-simulation caveat near the table", async () => {
    setup();
    const table = await screen.findByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getByRole("columnheader", { name: "Cambio respecto del inicio" })).toBeInTheDocument();
    expect(screen.getByText(/Simulación con datos históricos: no predice resultados futuros ni garantiza rentabilidad/)).toBeInTheDocument();
    expect(screen.queryByText(/Resultados históricos sobre datos ya investigados/)).not.toBeInTheDocument();
    expect(screen.getByText("Historial")).toBeInTheDocument();
    expect(screen.getByText("SHA-256 historial")).toBeInTheDocument();
  });
  it("treats two completed runs as complete, preserving requested order rather than ranking", async () => {
    const second = { ...runs[1], status: "completed" as const, result: { ...runs[0].result!, delta: -10, final_balance: 90, outcome: "limit" as const } };
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...comparison, status: "completed", completed: 2, complete: true, runs: [runs[0], second] });
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...detail, status: "completed", runs: [runs[0], second] });
    setup();
    expect(await screen.findByText("Comparación completa · 2/2 terminadas")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[2]).toHaveTextContent("-RD$10");
    await waitFor(() => expect(apiClient.getTrajectory).toHaveBeenCalledWith("exp", 1, 500));
  });
  it("loads complete bounded trajectories automatically and retries without erasing another", async () => {
    const second = { ...runs[1], status: "completed" as const, result: { ...runs[0].result!, bets_count: 1 } };
    const long = { ...runs[0], bets_count: 1001, result: { ...runs[0].result!, bets_count: 1001 } };
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...comparison, runs: [long, second] });
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...detail, runs: [long, second] });
    const trajectory = { initial_capital: 100, total: 1001, max_points: 500, reduction_method: "minmax-even-v1" as const,
      minimum: { balance: 1, source_index: 700 }, maximum: { balance: 300, source_index: 400 },
      points: [0, 400, 700, 1000].map((i) => ({ source_index: i, label: `2025-01-01 10:00`, balance: i === 700 ? 1 : 300, replay: `replay?offset=${i}&limit=1` })) };
    vi.mocked(apiClient.getTrajectory).mockImplementation(async (_id, ordinal) => { if (ordinal === 1) throw new NetworkError(); return trajectory; });
    const { user } = setup();
    expect(await screen.findByText(/Primera: 4 de 1001 apuestas.*reducción/)).toBeInTheDocument();
    expect(await screen.findByText(/No se pudo cargar la trayectoria de Segunda/)).toBeInTheDocument();
    expect(apiClient.getReplay).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Cargar más/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Apuesta 1001/ })).toHaveAttribute("href", "/experimentos/exp?run=0&bet=1000&from=comparison");
    vi.mocked(apiClient.getTrajectory).mockResolvedValue({ ...trajectory, total: 1, points: trajectory.points.slice(0, 1), reduction_method: "none" });
    await user.click(screen.getByRole("button", { name: /Reintentar trayectoria de Segunda/ }));
    expect(await screen.findByText(/Segunda: 1 de 1 apuestas/)).toBeInTheDocument();
    expect(screen.getByText(/Primera: 4 de 1001 apuestas/)).toBeInTheDocument();
  });
  it("shows 404 and disconnection separately, retries and ignores an old id response", async () => {
    vi.mocked(apiClient.compareExperiment).mockRejectedValueOnce(new ApiError(404, "missing"));
    const first = setup();
    expect(await screen.findByRole("alert")).toHaveTextContent(/no existe/i);
    first.unmount();
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new NetworkError());
    const second = setup();
    expect(await screen.findByRole("alert")).toHaveTextContent(/contactar/i);
    second.unmount();
    let resolve!: (value: CompareResult) => void;
    vi.mocked(apiClient.compareExperiment).mockReturnValueOnce(new Promise((done) => { resolve = done; })).mockResolvedValueOnce({ ...comparison, id: "other" });
    vi.mocked(apiClient.getExperiment).mockResolvedValueOnce(detail).mockResolvedValueOnce({ ...detail, id: "other", request: { ...detail.request, name: "Otra" } });
    const { router } = setup();
    await act(async () => { await router.navigate("/experimentos/other/comparacion"); });
    expect(await screen.findByText("Otra")).toBeInTheDocument();
    await act(async () => { resolve(comparison); });
    expect(screen.queryByText("Ensayo")).not.toBeInTheDocument();
  });
  it("preserves hidden selection and loaded context on targeted detail return; invalid run falls back honestly", async () => {
    const second = { ...runs[1], status: "completed" as const, result: { ...runs[0].result!, bets_count: 1 } };
    const long = { ...runs[0], bets_count: 101, result: { ...runs[0].result!, bets_count: 101 } };
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...comparison, runs: [long, second] });
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...detail, runs: [long, second] });
    const { user, router } = setup();
    await screen.findByText(/Primera: 101 de 101 apuestas/);
    await user.click(screen.getByRole("checkbox", { name: /Mostrar Segunda/ }));
    await screen.findByText(/Primera: 101 de 101 apuestas/);
    await user.click(screen.getByRole("link", { name: /Detalle de Segunda/ }));
    expect(router.state.location.search).toBe("?run=1&from=comparison");
    expect(await screen.findByRole("region", { name: "Ejecución 2" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Volver a comparación/ }));
    expect(await screen.findByText(/Primera: 101 de 101 apuestas/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Mostrar Segunda/ })).not.toBeChecked();
    await act(async () => { await router.navigate("/experimentos/exp?run=999&from=comparison"); });
    expect(await screen.findByText(/Esa ejecución no existe/i)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ejecución 1" })).toBeInTheDocument();
  });
  it("ignores a late trajectory response after leaving and does not issue mutations", async () => {
    let resolve!: (value: Awaited<ReturnType<typeof apiClient.getTrajectory>>) => void;
    vi.mocked(apiClient.getTrajectory).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { router } = setup();
    expect(await screen.findByText(/Cargando trayectoria de Primera/)).toBeInTheDocument();
    await act(async () => { await router.navigate("/experimentos/exp?run=1&from=comparison"); });
    await act(async () => { resolve({ initial_capital: 100, total: 0, max_points: 500, reduction_method: "none", points: [], minimum: { balance: 100, source_index: null }, maximum: { balance: 100, source_index: null } }); });
    expect(screen.queryByText(/Primera: 0 de 0 apuestas/)).not.toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("has no automated accessibility violations in a completed comparison", async () => {
    vi.mocked(apiClient.getReplay).mockResolvedValue({ total: 2, offset: 0, limit: 100, items: [bet("2025-01-01 10:00", 101), bet("2025-01-01 10:10", 120)] });
    const { container } = setup();
    await screen.findByText(/Primera: 2 de 2 apuestas/);
    expect(await axe(container)).toHaveNoViolations();
  });
  it("polls nonterminal only, cleans up on unmount", async () => {
    vi.mocked(apiClient.compareExperiment).mockResolvedValueOnce(comparison).mockResolvedValueOnce({ ...comparison, status: "completed" });
    vi.mocked(apiClient.getExperiment).mockResolvedValueOnce(detail).mockResolvedValueOnce({ ...detail, status: "completed" });
    vi.useFakeTimers();
    try {
      const { unmount } = setup();
      await act(async () => { await Promise.resolve(); await Promise.resolve(); });
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(apiClient.compareExperiment).toHaveBeenCalledTimes(2);
      unmount();
      await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
      expect(apiClient.compareExperiment).toHaveBeenCalledTimes(2);
    } finally { vi.useRealTimers(); }
  });
});
