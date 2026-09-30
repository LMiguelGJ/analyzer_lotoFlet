import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, ExperimentSummary, Page } from "../../api/types";

vi.mock("../../api/client", async (original) => {
  const actual = await original<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getExperiment: vi.fn(), getReplay: vi.fn(), createExperiment: vi.fn() } };
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
function setup(path = "/experimentos/exp") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  return { router, user: userEvent.setup(), ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  vi.mocked(apiClient.getExperiment).mockReset();
  vi.mocked(apiClient.getReplay).mockReset();
  vi.mocked(apiClient.getExperiment).mockResolvedValue(snapshot);
  vi.mocked(apiClient.getReplay).mockResolvedValue(page);
});

describe("LW11 detail", () => {
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
    expect(screen.getByText("Delta").parentElement).toHaveTextContent(displayed);
    expect(screen.getByText("Delta").parentElement).not.toHaveTextContent("No disponible");
  });

  it("does not invent a delta for an incomplete run in a partially completed experiment", async () => {
    const { user } = setup();
    await screen.findByText("Prueba");
    await user.click(screen.getByRole("button", { name: /Segunda/ }));
    const run = screen.getByRole("region", { name: "Ejecución 2" });
    expect(within(run).getByText(/no tiene un resultado completo guardado/i)).toBeInTheDocument();
    expect(within(run).queryByText("Delta")).not.toBeInTheDocument();
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
