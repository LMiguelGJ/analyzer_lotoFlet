import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "../../api/client";
import { BacktestCreatePage, BacktestsPage } from "./index";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getCatalog: vi.fn(), getGameSettings: vi.fn(), listBacktests: vi.fn(), createBacktest: vi.fn(), getBacktest: vi.fn() } };
});

const game = { name: "Reglas guardadas", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 1, source: "stored" as const };
const report = { id: "backtest-1", name: "Prueba", created_at: "2026-10-01T00:00:00Z", reached_goal: 10, completed: 20, goal_rate: 50, quiebres: 10, neto_medio: -12.5, incomplete: 1, window: { bets: 100, wagered: 500, paid: 550, sessions: 21, incomplete: 1 }, config: { name: "Prueba", strategy: { name: "Transición", selector: "system", system: "transition", coverage: 1, staking: "flat" }, game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 }, conditions: { capital: 2000, goal: 2800 }, inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) } } };
const catalog = { sources: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) } };
function renderPage(element: React.ReactNode, path = "/simulaciones/nueva-historica") {
  const router = createMemoryRouter([{ path: "*", element }], { initialEntries: [path] });
  return { router, ...render(<RouterProvider router={router} />) };
}

beforeEach(() => {
  vi.mocked(apiClient.getCatalog).mockResolvedValue(catalog as never);
  vi.mocked(apiClient.getGameSettings).mockResolvedValue(game);
  vi.mocked(apiClient.listBacktests).mockResolvedValue({ total: 0, offset: 0, limit: 20, items: [] });
  vi.mocked(apiClient.createBacktest).mockResolvedValue({ id: "backtest-1", status: "completed", report } as never);
  vi.mocked(apiClient.getBacktest).mockResolvedValue(report as never);
});

describe("historical backtest pages", () => {
  it("shows consequences and keeps creation disabled when the goal cannot be reached", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la corrida" });
    expect(screen.getByText("Capital inicial")).toBeInTheDocument();
    expect(screen.getByText("RD$2000")).toBeInTheDocument();
    expect(screen.getByText("Hasta meta o quiebre; sin límite temporal")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Prueba inválida");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    const goal = screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" });
    await user.clear(goal);
    await user.type(goal, "2000");
    expect(screen.getByRole("alert")).toHaveTextContent("La meta debe ser mayor que el capital");
    expect(screen.getByRole("button", { name: "Crear corrida histórica" })).toBeDisabled();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("submits the selected general scenario with game rules and pinned source hashes", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la corrida" });
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Transición a 50");
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de selección" }), "system");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema" }), "transition");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.clear(screen.getByRole("spinbutton", { name: "Números cubiertos" }));
    await user.type(screen.getByRole("spinbutton", { name: "Números cubiertos" }), "50");
    await user.selectOptions(screen.getByRole("combobox", { name: "Forma de apostar" }), "bold");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByText(/Configuración que se enviará/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledWith({
      name: "Transición a 50", strategy: { name: "Transición", selector: "system", system: "transition", coverage: 50, staking: "bold" },
      game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 }, conditions: { capital: 2000, goal: 2800 },
      inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) },
    }));
  });

  it("lists saved runs and provides a separate historical view destination", async () => {
    vi.mocked(apiClient.listBacktests).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [report] } as never);
    renderPage(<BacktestsPage />, "/simulaciones/historicas");
    expect(await screen.findByText("Prueba")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir corrida histórica de Prueba" })).toHaveAttribute("href", "/simulaciones/historicas/backtest-1");
    expect(screen.getByRole("link", { name: "Simulaciones" })).toHaveAttribute("href", "/simulaciones");
    expect(within(screen.getByRole("navigation", { name: "Simulaciones" })).getByRole("link", { name: "Corridas históricas" })).toHaveAttribute("aria-current", "page");
  });
});
