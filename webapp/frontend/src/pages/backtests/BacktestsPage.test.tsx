import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "../../api/client";
import { BacktestCreatePage, BacktestDetailPage, BacktestsPage } from "./index";

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

  it("lists saved runs with result and repeat actions", async () => {
    vi.mocked(apiClient.listBacktests).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [report] } as never);
    renderPage(<BacktestsPage />, "/simulaciones/historicas");
    expect(await screen.findByText("Prueba")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir corrida histórica de Prueba" })).toHaveAttribute("href", "/simulaciones/historicas/backtest-1");
    expect(screen.getByRole("link", { name: "Repetir con cambios: Prueba" })).toHaveAttribute("href", "/simulaciones/nueva-historica?base=backtest-1");
    expect(screen.getByRole("link", { name: "Simulaciones" })).toHaveAttribute("href", "/simulaciones");
    expect(within(screen.getByRole("navigation", { name: "Simulaciones" })).getByRole("link", { name: "Corridas históricas" })).toHaveAttribute("aria-current", "page");
  });

  it.each(["pointer", "Enter", "Space"] as const)("advancing from game rules by %s requires a separate create activation", async (activation) => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await user.type(await screen.findByRole("textbox", { name: "Nombre de la corrida" }), "Activación segura");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    const next = screen.getByRole("button", { name: "Siguiente" });
    if (activation === "pointer") await user.click(next);
    else {
      next.focus();
      await user.keyboard(activation === "Enter" ? "{Enter}" : " ");
    }
    expect(await screen.findByRole("heading", { name: "Capital y meta" })).toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
    const create = screen.getByRole("button", { name: "Crear corrida histórica" });
    expect(create).not.toBe(next);
    expect(create).toHaveFocus();
    await user.click(create);
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledTimes(1));
  });

  it("hydrates every saved field and submits an edited new run with pinned original hashes", async () => {
    const user = userEvent.setup();
    const saved = { ...report, name: "Apuesta guardada", config: {
      name: "Apuesta guardada",
      strategy: { name: "Tu par/impar", selector: "parity" as const, system: null, coverage: 17, staking: "ladder" as const },
      game: { numbers: 77, positions: 3, prizes: [91, 13, 5], min_stake: 7 },
      conditions: { capital: 3400, goal: 9100 },
      inputs: { history_sha256: "c".repeat(64), rankings_sha256: "d".repeat(64) },
    } };
    vi.mocked(apiClient.getBacktest).mockResolvedValue(saved as never);
    vi.mocked(apiClient.getCatalog).mockResolvedValue({ ...catalog, sources: { history_sha256: "e".repeat(64), rankings_sha256: "f".repeat(64) } } as never);
    vi.mocked(apiClient.getGameSettings).mockResolvedValue({ ...game, numbers: 90, positions: 2, prizes: [2, 1], minimum_stake: 3 });
    renderPage(<BacktestCreatePage />, "/simulaciones/nueva-historica?base=backtest-1");
    expect(await screen.findByRole("textbox", { name: "Nombre de la corrida" })).toHaveValue("Apuesta guardada");
    expect(apiClient.getBacktest).toHaveBeenCalledWith("backtest-1");
    expect(screen.getByRole("combobox", { name: "Método de selección" })).toHaveValue("parity");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("spinbutton", { name: "Números cubiertos" })).toHaveValue(17);
    expect(screen.getByRole("combobox", { name: "Forma de apostar" })).toHaveValue("ladder");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("spinbutton", { name: "Números posibles" })).toHaveValue(77);
    expect(screen.getByRole("spinbutton", { name: "Posiciones" })).toHaveValue(3);
    expect(screen.getByRole("spinbutton", { name: "Premio de la posición 1" })).toHaveValue(91);
    expect(screen.getByRole("spinbutton", { name: "Premio de la posición 2" })).toHaveValue(13);
    expect(screen.getByRole("spinbutton", { name: "Premio de la posición 3" })).toHaveValue(5);
    expect(screen.getByRole("spinbutton", { name: "Apuesta mínima (RD$)" })).toHaveValue(7);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("spinbutton", { name: "Capital inicial (RD$)" })).toHaveValue(3400);
    expect(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" })).toHaveValue(9100);
    await user.clear(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" }));
    await user.type(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" }), "9200");
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledWith({
      name: "Apuesta guardada", strategy: { name: "Tu par/impar", selector: "parity", system: null, coverage: 17, staking: "ladder" },
      game: { numbers: 77, positions: 3, prizes: [91, 13, 5], min_stake: 7 }, conditions: { capital: 3400, goal: 9200 },
      inputs: { history_sha256: "c".repeat(64), rankings_sha256: "d".repeat(64) },
    }));
  });

  it("opens the saved repeat editor from detail without changing the original", async () => {
    renderPage(<BacktestDetailPage />, "/simulaciones/historicas/backtest-1");
    expect(await screen.findByRole("link", { name: "Repetir con cambios" })).toHaveAttribute("href", "/simulaciones/nueva-historica?base=backtest-1");
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("explains stale source conflicts without rebinding or retrying automatically", async () => {
    const user = userEvent.setup();
    const stale = { ...report, config: { ...report.config, inputs: { history_sha256: "c".repeat(64), rankings_sha256: "d".repeat(64) } } };
    vi.mocked(apiClient.getBacktest).mockResolvedValue(stale as never);
    vi.mocked(apiClient.createBacktest).mockRejectedValue(new ApiError(409, "stale sources"));
    renderPage(<BacktestCreatePage />, "/simulaciones/nueva-historica?base=backtest-1");
    await screen.findByRole("textbox", { name: "Nombre de la corrida" });
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/fuentes|huellas/i);
    expect(apiClient.createBacktest).toHaveBeenCalledTimes(1);
    expect(apiClient.createBacktest).toHaveBeenCalledWith(expect.objectContaining({ inputs: stale.config.inputs }));
  });

  it("ignores settings and saved-report responses from an obsolete repeat request", async () => {
    let resolveOldCatalog!: (value: typeof catalog) => void;
    let resolveOldGame!: (value: typeof game) => void;
    vi.mocked(apiClient.getCatalog).mockImplementationOnce(() => new Promise((resolve) => { resolveOldCatalog = resolve; }) as never);
    vi.mocked(apiClient.getGameSettings).mockImplementationOnce(() => new Promise((resolve) => { resolveOldGame = resolve; }) as never);
    vi.mocked(apiClient.getBacktest).mockImplementation(async (id) => ({ ...report, id, name: id, config: { ...report.config, name: id } }) as never);
    const { router } = renderPage(<BacktestCreatePage />, "/simulaciones/nueva-historica?base=old");
    await waitFor(() => expect(apiClient.getBacktest).toHaveBeenCalledWith("old"));
    await router.navigate("/simulaciones/nueva-historica?base=backtest-1");
    expect(await screen.findByRole("textbox", { name: "Nombre de la corrida" })).toHaveValue("backtest-1");
    resolveOldCatalog({ ...catalog, sources: { history_sha256: "e".repeat(64), rankings_sha256: "f".repeat(64) } });
    resolveOldGame({ ...game, numbers: 90, positions: 2, prizes: [2, 1], minimum_stake: 3 });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByRole("textbox", { name: "Nombre de la corrida" })).toHaveValue("backtest-1");
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("blocks submission when the requested saved run cannot be loaded", async () => {
    vi.mocked(apiClient.getBacktest).mockRejectedValue(new Error("missing"));
    renderPage(<BacktestCreatePage />, "/simulaciones/nueva-historica?base=missing");
    expect(await screen.findByRole("alert")).toHaveTextContent(/cargar.*corrida/i);
    expect(screen.queryByRole("button", { name: "Crear corrida histórica" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar carga" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a corridas históricas" })).toHaveAttribute("href", "/simulaciones/historicas");
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });
});
