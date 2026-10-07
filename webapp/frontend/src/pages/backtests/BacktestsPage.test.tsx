import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient } from "../../api/client";
import { BacktestCreatePage, BacktestDetailPage, BacktestsPage } from "./index";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getCatalog: vi.fn(), getGameSettings: vi.fn(), listConfigurations: vi.fn(), getConfiguration: vi.fn(), getBacktest: vi.fn(), listBacktests: vi.fn(), createBacktest: vi.fn() } };
});

const game = { name: "Reglas guardadas", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 1, source: "stored" as const };
const report = { id: "backtest-1", name: "Prueba", created_at: "2026-10-01T00:00:00Z", reached_goal: 10, completed: 20, goal_rate: 50, quiebres: 10, neto_medio: -12.5, incomplete: 1, window: { bets: 100, wagered: 500, paid: 550, sessions: 21, incomplete: 1 }, config: { name: "Prueba", strategy: { name: "Transición", selector: "system", system: "transition", coverage: 1, staking: "flat" }, game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 }, conditions: { capital: 2000, goal: 2800 }, inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) } } };
const catalog = { sources: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) }, selectors: ["system", "blend", "random", "parity"], systems: { transition: "Transición", cold: "Fríos", select_interpretable: "Selector automático", mix: "Mezclas", ensemble: "Ensemble", other: "Otro" }, coverages: [1, 17, 50], parity_coverage: 50 };
function renderPage(element: React.ReactNode, path = "/simulaciones/nueva-historica") {
  const router = createMemoryRouter([{ path: "*", element }], { initialEntries: [path] });
  return { router, ...render(<RouterProvider router={router} />) };
}

beforeEach(() => {
  vi.mocked(apiClient.getCatalog).mockResolvedValue(catalog as never);
  vi.mocked(apiClient.getGameSettings).mockResolvedValue(game);
  vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 0, offset: 0, limit: 100, items: [] } as never);
  vi.mocked(apiClient.getConfiguration).mockResolvedValue({ id: "saved-1", name: "Guardada", strategy: { name: "Método de biblioteca", selector: "system", system: "cold", coverage: 17, staking: "ladder" } } as never);
  vi.mocked(apiClient.listBacktests).mockResolvedValue({ total: 0, offset: 0, limit: 20, items: [] });
  vi.mocked(apiClient.createBacktest).mockResolvedValue({ id: "backtest-1", status: "completed", report } as never);
  vi.mocked(apiClient.getBacktest).mockResolvedValue(report as never);
});

describe("historical backtest pages", () => {
  it("shows Strategy errors immediately without asking for the future corrida name", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    const name = await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    expect(screen.queryByRole("textbox", { name: "Nombre de la corrida" })).not.toBeInTheDocument();
    await user.clear(name);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByRole("alert")).toHaveTextContent("Ingresá un nombre para la estrategia.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("reconocer la corrida");
    await user.type(name, "Paridad nativa");
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "parity");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });
  it("shows consequences and keeps creation disabled when the goal cannot be reached", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    expect(screen.getByText("Capital inicial")).toBeInTheDocument();
    expect(screen.getByText("RD$2000")).toBeInTheDocument();
    expect(screen.getByText("Hasta meta o quiebre; sin límite temporal")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Prueba inválida");
    const goal = screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" });
    await user.clear(goal);
    await user.type(goal, "2000");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("alert")).toHaveTextContent("La meta debe ser mayor que el capital");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4");
    expect(screen.queryByRole("button", { name: "Crear corrida histórica" })).not.toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("submits the selected general scenario with game rules and pinned source hashes", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "system");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.clear(screen.getByRole("spinbutton", { name: "Números cubiertos" }));
    await user.type(screen.getByRole("spinbutton", { name: "Números cubiertos" }), "50");
    await user.selectOptions(screen.getByRole("combobox", { name: "Forma de apostar" }), "bold");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Transición a 50");
    expect(screen.getByText(/Configuración que se enviará/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
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

  it("loads a saved classic configuration into StrategyEditor and submits its exact strategy fields", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [{ id: "saved-1", name: "Biblioteca" }] } as never);
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Estrategia guardada (opcional)" }), "saved-1");
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Método de biblioteca"));
    expect(apiClient.getConfiguration).toHaveBeenCalledWith("saved-1");
    expect(screen.getByRole("spinbutton", { name: "Números cubiertos" })).toHaveValue(17);
    expect(screen.getByRole("combobox", { name: "Forma de apostar" })).toHaveValue("ladder");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Run desde biblioteca");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledWith(expect.objectContaining({
      name: "Run desde biblioteca", strategy: { name: "Método de biblioteca", selector: "system", system: "cold", coverage: 17, staking: "ladder" },
    })));
  });

  it("renders catalog-only systems disabled and distinguishes blend from supported mix", async () => {
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    expect(screen.getByRole("option", { name: "Mezclas" })).toHaveValue("mix");
    expect(screen.getByRole("checkbox", { name: "Otro" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Combinación de estrategias (blend)" })).toBeDisabled();
  });

  it("allows clearing and retyping a strategy name but blocks submission while blank", async () => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    const strategyName = await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.clear(strategyName);
    expect(strategyName).toHaveValue("");
    await user.type(strategyName, "Etiqueta manual");
    await user.clear(strategyName);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.queryByRole("button", { name: "Crear corrida histórica" })).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/nombre.*estrategia/i);
    expect(screen.getByRole("button", { name: "Atrás" })).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Etiqueta reescrita");
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Etiqueta reescrita");
  });

  it("does not let a stale saved-configuration response overwrite manual edits", async () => {
    const user = userEvent.setup();
    let resolveConfiguration!: (value: never) => void;
    vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [{ id: "slow", name: "Lenta" }] } as never);
    vi.mocked(apiClient.getConfiguration).mockImplementationOnce(() => new Promise((resolve) => { resolveConfiguration = resolve; }) as never);
    renderPage(<BacktestCreatePage />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Estrategia guardada (opcional)" }), "slow");
    expect(screen.getByRole("status")).toHaveTextContent(/cargando la estrategia guardada/i);
    const strategyName = screen.getByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.clear(strategyName);
    await user.type(strategyName, "Edición manual");
    expect(screen.getByRole("combobox", { name: "Estrategia guardada (opcional)" })).toHaveValue("");
    expect(screen.queryByText(/cargando la estrategia guardada/i)).not.toBeInTheDocument();
    resolveConfiguration({ id: "slow", name: "Lenta", strategy: { name: "Sobrescritura tardía", selector: "system", system: "cold", coverage: 17, staking: "bold" } } as never);
    await waitFor(() => expect(apiClient.getConfiguration).toHaveBeenCalledWith("slow"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(strategyName).toHaveValue("Edición manual");
  });

  it("blocks missing or incompatible saved configuration references with recovery guidance", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [{ id: "gone", name: "Ya no existe" }] } as never);
    vi.mocked(apiClient.getConfiguration).mockRejectedValueOnce(new ApiError(404, "missing"));
    renderPage(<BacktestCreatePage />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Estrategia guardada (opcional)" }), "gone");
    expect(await screen.findByText(/La estrategia guardada ya no existe/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("rejects an incompatible saved blend instead of converting it to a system", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [{ id: "blend", name: "Mezcla" }] } as never);
    vi.mocked(apiClient.getConfiguration).mockResolvedValue({ id: "blend", name: "Mezcla", strategy: { name: "Blend original", selector: "blend", components: [{ system: "cold", weight: 100 }], coverage: 17, staking: "flat" } } as never);
    renderPage(<BacktestCreatePage />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Estrategia guardada (opcional)" }), "blend");
    expect(await screen.findByText(/selección no disponible.*no se convierte/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it.each(["pointer", "Enter", "Space"] as const)("advancing to final review by %s requires a separate create activation", async (activation) => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Activación segura");
    const next = screen.getByRole("button", { name: "Siguiente" });
    if (activation === "pointer") await user.click(next);
    else {
      next.focus();
      await user.keyboard(activation === "Enter" ? "{Enter}" : " ");
    }
    expect(await screen.findByRole("heading", { name: "Revisá la corrida histórica" })).toBeInTheDocument();
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
    const create = screen.getByRole("button", { name: "Crear corrida histórica" });
    expect(create).not.toBe(next);
    expect(screen.getByRole("heading", { name: "5 · Revisá y creá" })).toHaveFocus();
    await user.click(create);
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledTimes(1));
  });

  it("repeats saved parity coverage 17 with every native field and pinned original hashes", async () => {
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
    expect(await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Tu par/impar");
    expect(apiClient.getBacktest).toHaveBeenCalledWith("backtest-1");
    expect(screen.getByRole("combobox", { name: "Método de la estrategia 1" })).toHaveValue("parity");
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
    expect(screen.getByText("c".repeat(64))).toBeInTheDocument();
    expect(screen.getByText("d".repeat(64))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("textbox", { name: "Nombre de la corrida" })).toHaveValue("Apuesta guardada");
    expect(screen.getByRole("spinbutton", { name: "Capital inicial (RD$)" })).toHaveValue(3400);
    expect(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" })).toHaveValue(9100);
    await user.clear(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" }));
    await user.type(screen.getByRole("spinbutton", { name: "Meta de saldo (RD$)" }), "9200");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledWith({
      name: "Apuesta guardada", strategy: { name: "Tu par/impar", selector: "parity", system: null, coverage: 17, staking: "ladder" },
      game: { numbers: 77, positions: 3, prizes: [91, 13, 5], min_stake: 7 }, conditions: { capital: 3400, goal: 9200 },
      inputs: { history_sha256: "c".repeat(64), rankings_sha256: "d".repeat(64) },
    }));
  });

  it.each([1, 17, 49, 50])("edits historical parity coverage %s and retains it across selector changes", async (coverage) => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    const selector = await screen.findByRole("combobox", { name: "Método de la estrategia 1" });
    const covered = screen.getByRole("spinbutton", { name: "Números cubiertos" });
    await user.clear(covered);
    await user.type(covered, String(coverage));
    await user.selectOptions(selector, "parity");
    expect(covered).toHaveValue(coverage);
    expect(covered).toBeEnabled();
    expect(covered).toHaveAttribute("max", "50");
    expect(screen.queryByText(/utiliza siempre 50/)).not.toBeInTheDocument();
    await user.clear(covered);
    await user.type(covered, String(coverage));
    expect(covered).toHaveValue(coverage);
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "system");
    expect(covered).toHaveValue(coverage);
    expect(screen.getByRole("combobox", { name: "Cobertura de la estrategia 1" })).toHaveValue(String(coverage));
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "parity");
    expect(covered).toHaveValue(coverage);
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it.each([0, 51])("blocks invalid parity coverage %s at the native strategy step", async (coverage) => {
    const user = userEvent.setup();
    renderPage(<BacktestCreatePage />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Método de la estrategia 1" }), "parity");
    const covered = screen.getByRole("spinbutton", { name: "Números cubiertos" });
    await user.clear(covered);
    await user.type(covered, String(coverage));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByRole("alert")).toHaveTextContent(coverage === 0 ? "La cobertura debe ser un número entero desde 1." : "Paridad puede cubrir hasta 50 números");
    expect(covered).toHaveValue(coverage);
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
  });

  it("selects compatible library parity coverage 17 without catalog coercion and submits it", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.listConfigurations).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [{ id: "saved-1", name: "Paridad de biblioteca" }] } as never);
    vi.mocked(apiClient.getConfiguration).mockResolvedValue({ id: "saved-1", name: "Biblioteca", strategy: { name: " Paridad original ", selector: "parity", system: null, coverage: 17, staking: "bold" } } as never);
    vi.mocked(apiClient.getCatalog).mockResolvedValue({ ...catalog, coverages: [1, 50], parity_coverage: 50 } as never);
    renderPage(<BacktestCreatePage />);
    await user.selectOptions(await screen.findByRole("combobox", { name: "Estrategia guardada (opcional)" }), "saved-1");
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue(" Paridad original "));
    expect(screen.getByRole("spinbutton", { name: "Números cubiertos" })).toHaveValue(17);
    expect(screen.getByRole("combobox", { name: "Forma de apostar" })).toHaveValue("bold");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la corrida" }), "Run de biblioteca");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(apiClient.createBacktest).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    await waitFor(() => expect(apiClient.createBacktest).toHaveBeenCalledWith({
      ...report.config, name: "Run de biblioteca",
      strategy: { name: " Paridad original ", selector: "parity", system: null, coverage: 17, staking: "bold" },
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
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Crear corrida histórica" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/fuentes|huellas/i);
    expect(apiClient.createBacktest).toHaveBeenCalledTimes(1);
    expect(apiClient.createBacktest).toHaveBeenCalledWith(expect.objectContaining({ inputs: stale.config.inputs }));
  });

  it("ignores settings and saved-report responses from an obsolete repeat request", async () => {
    const user = userEvent.setup();
    let resolveOldCatalog!: (value: typeof catalog) => void;
    let resolveOldGame!: (value: typeof game) => void;
    vi.mocked(apiClient.getCatalog).mockImplementationOnce(() => new Promise((resolve) => { resolveOldCatalog = resolve; }) as never);
    vi.mocked(apiClient.getGameSettings).mockImplementationOnce(() => new Promise((resolve) => { resolveOldGame = resolve; }) as never);
    vi.mocked(apiClient.getBacktest).mockImplementation(async (id) => ({ ...report, id, name: id, config: { ...report.config, name: id } }) as never);
    const { router } = renderPage(<BacktestCreatePage />, "/simulaciones/nueva-historica?base=old");
    await waitFor(() => expect(apiClient.getBacktest).toHaveBeenCalledWith("old"));
    await router.navigate("/simulaciones/nueva-historica?base=backtest-1");
    await screen.findByRole("textbox", { name: "Nombre de la estrategia 1" });
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("textbox", { name: "Nombre de la corrida" })).toHaveValue("backtest-1");
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
