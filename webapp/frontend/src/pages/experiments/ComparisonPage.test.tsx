import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, CompareResult, ExperimentSummary, Page } from "../../api/types";

vi.mock("../../api/client", async (original) => {
  const actual = await original<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getExperiment: vi.fn(), compareExperiment: vi.fn(), getReplay: vi.fn(), createExperiment: vi.fn() } };
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
const page = (ordinal: number, offset = 0): Page<Bet> => ({ offset, limit: 100, total: ordinal ? 1 : 101, items: offset ? [bet("2025-01-01 11:00", 150)] : ordinal ? [bet("2025-01-01 10:30", 110)] : Array.from({ length: 100 }, (_, i) => bet(`2025-01-01 10:${String(i % 60).padStart(2, "0")}`, 101 + i)) });
function setup(path = "/experimentos/exp/comparacion") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return { router, user: userEvent.setup(), ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(apiClient.getExperiment).mockReset().mockResolvedValue(detail);
  vi.mocked(apiClient.compareExperiment).mockReset().mockResolvedValue(comparison);
  vi.mocked(apiClient.getReplay).mockReset().mockImplementation(async (_id, ordinal, offset) => page(ordinal, offset));
  vi.mocked(apiClient.createExperiment).mockReset();
});
describe("LW12 comparison", () => {
  it("uses server N/M and delta, shows absent values as dashes, and separates outcome from execution", async () => {
    setup();
    expect(await screen.findByText("Comparación incompleta · 1/2 terminadas")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent(/Primera.*Completado.*RD\$150.*RD\$50.*2.*Meta alcanzada/);
    expect(rows[2]).toHaveTextContent(/Segunda.*En curso.*—.*—.*—.*—/);
    expect(within(rows[2]).queryByText("Meta alcanzada")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Comparación de ejecuciones" })).toHaveClass("overflow-x-auto");
    expect(screen.getByText("hash-h")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/mejor estrategia|probabilidad de éxito|exportar/i);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    expect(apiClient.getReplay).not.toHaveBeenCalledWith("exp", 1, 0, 100);
  });
  it("treats two completed runs as complete, preserving requested order rather than ranking", async () => {
    const second = { ...runs[1], status: "completed" as const, result: { ...runs[0].result!, delta: -10, final_balance: 90, outcome: "limit" as const } };
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...comparison, status: "completed", completed: 2, complete: true, runs: [runs[0], second] });
    vi.mocked(apiClient.getExperiment).mockResolvedValue({ ...detail, status: "completed", runs: [runs[0], second] });
    setup();
    expect(await screen.findByText("Comparación completa · 2/2 terminadas")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Comparación de ejecuciones" });
    expect(within(table).getAllByRole("row")[2]).toHaveTextContent("-RD$10");
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 1, 0, 100);
  });
  it("loads only bounded replay pages on demand and retries a failed series without erasing another", async () => {
    const second = { ...runs[1], status: "completed" as const, result: { ...runs[0].result!, bets_count: 1 } };
    const long = { ...runs[0], bets_count: 101, result: { ...runs[0].result!, bets_count: 101 } };
    vi.mocked(apiClient.compareExperiment).mockResolvedValue({ ...comparison, runs: [long, second] });
    vi.mocked(apiClient.getReplay).mockImplementation(async (_id, ordinal, offset) => { if (ordinal === 1 && offset === 0) throw new NetworkError(); return page(ordinal, offset); });
    const { user } = setup();
    expect(await screen.findByText(/Primera: 100\/101 cargadas/)).toBeInTheDocument();
    expect(await screen.findByRole("alert", { name: /Segunda/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Cargar más de Primera/ }));
    expect(await screen.findByText(/Primera: 101\/101 cargadas/)).toBeInTheDocument();
    expect(apiClient.getReplay).toHaveBeenCalledWith("exp", 0, 100, 100);
    vi.mocked(apiClient.getReplay).mockImplementation(async (_id, ordinal, offset) => page(ordinal, offset));
    await user.click(screen.getByRole("button", { name: /Reintentar Segunda/ }));
    expect(await screen.findByText(/Segunda: 1\/1 cargadas/)).toBeInTheDocument();
    expect(screen.getByText(/Primera: 101\/101 cargadas/)).toBeInTheDocument();
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
    await screen.findByText(/Primera: 100\/101 cargadas/);
    await user.click(screen.getByRole("checkbox", { name: /Mostrar Segunda/ }));
    await user.click(screen.getByRole("button", { name: /Cargar más de Primera/ }));
    await screen.findByText(/Primera: 101\/101 cargadas/);
    await user.click(screen.getByRole("link", { name: /Detalle de Segunda/ }));
    expect(router.state.location.search).toBe("?run=1&from=comparison");
    expect(await screen.findByRole("region", { name: "Ejecución 2" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Volver a comparación/ }));
    expect(await screen.findByText(/Primera: 101\/101 cargadas/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Mostrar Segunda/ })).not.toBeChecked();
    await act(async () => { await router.navigate("/experimentos/exp?run=999&from=comparison"); });
    expect(await screen.findByText(/ejecución solicitada no existe/i)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ejecución 1" })).toBeInTheDocument();
  });
  it("ignores a late replay response after leaving and does not issue mutations", async () => {
    let resolve!: (value: Page<Bet>) => void;
    vi.mocked(apiClient.getReplay).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    const { router } = setup();
    expect(await screen.findByText(/Primera: 0\/2 cargadas/)).toBeInTheDocument();
    await act(async () => { await router.navigate("/experimentos/exp?run=1&from=comparison"); });
    await act(async () => { resolve({ total: 2, offset: 0, limit: 100, items: [bet("2025-01-01 10:00", 101)] }); });
    expect(screen.queryByText(/Primera: 1\/2 cargadas/)).not.toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("has no automated accessibility violations in a completed comparison", async () => {
    vi.mocked(apiClient.getReplay).mockResolvedValue({ total: 2, offset: 0, limit: 100, items: [bet("2025-01-01 10:00", 101), bet("2025-01-01 10:10", 120)] });
    const { container } = setup();
    await screen.findByText(/Primera: 2\/2 cargadas/);
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
