import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import detail from "../../api/__fixtures__/experiment-detail.json";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getCatalog: vi.fn(), getStartingDraws: vi.fn(), getStartingDrawAvailability: vi.fn(), getExperiment: vi.fn(), createExperiment: vi.fn(), getConfiguration: vi.fn(), listConfigurations: vi.fn(), createConfiguration: vi.fn() } };
});

const catalog = {
  game: { name: "Quiniela 80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true },
  systems: { transition: "Transición", cold: "Fríos", freq_hist: "Frecuencia histórica" },
  selectors: ["system", "blend", "random", "parity"], coverages: [1, 5, 10, 20, 25, 30, 40, 50], parity_coverage: 50,
  starting_draws: ["2025-09-02 05:10"], starting_draws_total: 2, sources: {},
};
function setup(path = "/experimentos/nuevo") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [path] });
  const view = render(<RouterProvider router={router} />);
  return { user: userEvent.setup(), router, ...view };
}
async function conditions(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("option", { name: /2025-09-02 05:10/ });
  await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Prueba Q80");
  await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), "2025-09-02 05:10");
  await user.type(screen.getByRole("textbox", { name: "Capital inicial (RD$)" }), "2000");
  await user.type(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }), "2800");
  await user.type(screen.getByRole("textbox", { name: "Máximo de apuestas" }), "12");
  await user.type(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" }), "42");
  await user.click(screen.getByRole("button", { name: "Continuar" }));
}

beforeEach(() => {
  vi.mocked(apiClient.getCatalog).mockResolvedValue(catalog as never);
  vi.mocked(apiClient.getStartingDraws).mockReset().mockImplementation(async (offset = 0, limit = 100, date) => ({
    total: date === "2025-09-02" ? 2 : date ? 1 : 2, offset, limit,
    items: date === "2025-09-02" ? ["2025-09-02 05:10", "2025-09-02 05:15"]
      : date ? [date === "2025-01-01" ? detail.request.conditions.start_draw : `${date} 05:10`]
        : ["2025-09-02 05:10", "2025-09-02 05:15"],
  }));
  vi.mocked(apiClient.getStartingDrawAvailability).mockReset().mockImplementation(async (date) => ({
    date, history_total: date === "2025-09-02" ? 2 : 1, ranked_total: date === "2025-09-02" ? 2 : 1,
  }));
  vi.mocked(apiClient.createExperiment).mockReset();
  vi.mocked(apiClient.getExperiment).mockReset();
  vi.mocked(apiClient.getConfiguration).mockReset();
  vi.mocked(apiClient.listConfigurations).mockReset().mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [{ id: "cfg-1", name: "Biblioteca", strategy: { name: "Fríos", selector: "system", system: "cold", coverage: 1, staking: "flat" } }] });
  vi.mocked(apiClient.createConfiguration).mockReset();
});

describe("profile creator discovery", () => {
  it("links to the dedicated route without changing the legacy form", async () => {
    const { user, router } = setup();
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Crear sesión con perfil" });
    expect(link).toHaveAttribute("href", "/experimentos/nuevo/perfil");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    // The link is navigation only; existing legacy inputs remain usable.
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Clásico");
    expect(router.state.location.pathname).toBe("/experimentos/nuevo");
  });
});

describe("LW13 library templates", () => {
  const saved = { id: "cfg-1", name: "Biblioteca", strategy: { name: "Fríos", selector: "system" as const, system: "cold", coverage: 1, staking: "flat" as const } };
  it("prefills only one strategy from a configuration; conditions remain fresh and unsubmitted", async () => {
    vi.mocked(apiClient.getConfiguration).mockResolvedValue(saved);
    const { user, router } = setup("/experimentos/nuevo?configuration=cfg-1");
    expect(await screen.findByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: "Capital inicial (RD$)" })).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Condiciones" })).toBeInTheDocument();
    expect(apiClient.getConfiguration).toHaveBeenCalledWith("cfg-1");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    await user.click(screen.getByRole("link", { name: "Volver a experimentos" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  });
  it("appends one selected template without changing conditions or existing strategies, and rejects a normalized duplicate", async () => {
    vi.mocked(apiClient.getConfiguration).mockResolvedValue(saved);
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Original");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Agregar desde biblioteca" }));
    await user.click(screen.getByRole("button", { name: "Añadir Biblioteca" }));
    expect(await screen.findByRole("button", { name: /Estrategia 2.*Fríos/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Atrás" }));
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Prueba Q80");
    expect(screen.getByRole("textbox", { name: "Capital inicial (RD$)" })).toHaveValue("2000");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await user.click(screen.getByRole("button", { name: "Agregar desde biblioteca" }));
    await user.click(screen.getByRole("button", { name: "Añadir Biblioteca" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/nombre.*único/i);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("guards semantic configuration changes and removal, stays or leaves; rejects base/configuration conflict", async () => {
    vi.mocked(apiClient.getConfiguration).mockResolvedValue(saved);
    const { user, router } = setup("/experimentos/nuevo?configuration=cfg-1");
    await screen.findByRole("textbox", { name: "Nombre del experimento" });
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Borrador");
    await act(async () => { await router.navigate("/experimentos/nuevo?configuration=other"); });
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(apiClient.getConfiguration).toHaveBeenCalledTimes(1);
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Seguir editando" }));
    await act(async () => { await router.navigate("/experimentos/nuevo"); });
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue(""));
    await act(async () => { await router.navigate("/experimentos/nuevo?base=exp-1&configuration=cfg-1"); });
    expect(await screen.findByRole("alert")).toHaveTextContent(/dos orígenes/);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("ignores a stale configuration response after a clean query change", async () => {
    let resolveOld!: (value: { id: string; name: string; strategy: { name: string; selector: "system"; system: string; coverage: number; staking: "flat" } }) => void;
    vi.mocked(apiClient.getConfiguration).mockImplementation((id) => id === "other" ? Promise.resolve({ ...saved, id, strategy: { ...saved.strategy, name: "Nueva" } }) : new Promise((resolve) => { resolveOld = resolve; }));
    const { router, user } = setup("/experimentos/nuevo?configuration=cfg-1");
    await waitFor(() => expect(apiClient.getConfiguration).toHaveBeenCalledWith("cfg-1"));
    await act(async () => { await router.navigate("/experimentos/nuevo?configuration=other"); });
    await screen.findByRole("textbox", { name: "Nombre del experimento" });
    await act(async () => { resolveOld(saved); });
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Nueva prueba");
    await screen.findByRole("option", { name: "2025-09-02 05:10" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), "2025-09-02 05:10");
    await user.type(screen.getByRole("textbox", { name: "Capital inicial (RD$)" }), "100");
    await user.type(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }), "200");
    await user.type(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" }), "0");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Nueva");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    expect(apiClient.getConfiguration).toHaveBeenCalledTimes(2);
  });
  it("caps append at five and keeps failed library saves and the wizard draft without an experiment POST", async () => {
    vi.mocked(apiClient.getConfiguration).mockResolvedValue(saved);
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Original");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    for (let i = 2; i <= 5; i++) {
      await user.click(screen.getByRole("button", { name: "Agregar estrategia" }));
      await user.click(screen.getByRole("button", { name: new RegExp(`Estrategia ${i}`) }));
      await user.type(screen.getByRole("textbox", { name: `Nombre de la estrategia ${i}` }), `Otra ${i}`);
      await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "cold");
    }
    expect(screen.getByRole("button", { name: "Agregar desde biblioteca" })).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Nombre para guardar en biblioteca" }), "Guardada");
    vi.mocked(apiClient.createConfiguration).mockRejectedValueOnce(new NetworkError());
    await user.click(screen.getByRole("button", { name: "Guardar estrategia en biblioteca" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/biblioteca.*reintentar/i);
    expect(screen.getByRole("textbox", { name: "Nombre para guardar en biblioteca" })).toHaveValue("Guardada");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("maps library save 422 to its own name and strategy field while preserving the draft", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "cold");
    await user.type(screen.getByRole("textbox", { name: "Nombre para guardar en biblioteca" }), "Mi nombre");
    vi.mocked(apiClient.createConfiguration).mockRejectedValueOnce(new ApiError(422, "invalid", [
      { loc: ["body", "name"], msg: "library rejected", type: "value_error" },
      { loc: ["body", "strategy", "system"], msg: "system rejected", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Guardar estrategia en biblioteca" }));
    expect(await screen.findByText("library rejected")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nombre para guardar en biblioteca" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("combobox", { name: "Sistema de ranking" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Una");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
  it("reports missing, network and catalog-invalid templates without posting", async () => {
    vi.mocked(apiClient.getConfiguration).mockRejectedValueOnce(new ApiError(404, "missing"));
    const first = setup("/experimentos/nuevo?configuration=gone");
    expect(await screen.findByRole("alert")).toHaveTextContent(/ya no existe/);
    first.unmount();
    vi.mocked(apiClient.getConfiguration).mockRejectedValueOnce(new NetworkError());
    const second = setup("/experimentos/nuevo?configuration=offline");
    expect(await screen.findByRole("alert")).toHaveTextContent(/contactar al servidor/);
    second.unmount();
    vi.mocked(apiClient.getConfiguration).mockResolvedValue({ ...saved, strategy: { ...saved.strategy, system: "unknown" } });
    setup("/experimentos/nuevo?configuration=invalid");
    expect(await screen.findByRole("alert")).toHaveTextContent(/Esta estrategia guardada ya no es válida/);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
});

describe("LW10 use as base", () => {
  it("loads a saved request through detail, locates a ranked draw beyond the first catalog page, and leaves it clean until edited", async () => {
    const saved = { ...detail, request: { ...detail.request, name: "Original", conditions: { ...detail.request.conditions, start_draw: "2025-09-03 05:10", seed: 9007199254740991, max_minutes: 90 }, strategies: [
      { name: "Mix", selector: "blend", system: null, components: [{ system: "transition", weight: 60 }, { system: "cold", weight: 40 }], coverage: 10, staking: "bold" },
      { name: "Par", selector: "parity", system: null, components: null, coverage: 50, staking: "flat" },
    ] } };
    let resolveBase!: (value: typeof saved) => void;
    vi.mocked(apiClient.getExperiment).mockReturnValue(new Promise((resolve) => { resolveBase = resolve; }) as never);
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => ({
      total: date ? 101 : 1000, offset, limit,
      items: date ? offset === 0 ? Array.from({ length: 100 }, (_, i) => `${date} ${String(Math.floor(i / 60)).padStart(2, "0")}:${String(i % 60).padStart(2, "0")}`)
        : ["2025-09-03 05:10"] : ["2025-09-02 05:10"],
    }));
    const { user, router } = setup("/experimentos/nuevo?base=exp-1");
    expect(await screen.findByText(/Cargando experimento base/)).toBeInTheDocument();
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledWith("exp-1"));
    await act(async () => { resolveBase(saved); });
    expect(await screen.findByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Original");
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue("2025-09-03 05:10");
    expect(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" })).toHaveValue("9007199254740991");
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(0, 100, "2025-09-03");
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(100, 100, "2025-09-03");
    expect(vi.mocked(apiClient.getStartingDraws).mock.calls.filter(([, , date]) => !date)).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Mix");
    expect(screen.getByRole("combobox", { name: "Método de la estrategia 1" })).toHaveValue("blend");
    expect(screen.getByRole("textbox", { name: "Peso 1 (%)" })).toHaveValue("60");
    expect(screen.getByRole("textbox", { name: "Peso 2 (%)" })).toHaveValue("40");
    await user.click(screen.getByRole("button", { name: /Estrategia 2/ }));
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 2" })).toHaveValue("Par");
    expect(screen.getByText(/50 números/)).toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Revisar" })).toBeInTheDocument();
    expect(screen.getByText(/Combinación de sistemas: Transición 60% \+ Fríos 40%/)).toBeInTheDocument();
    expect(screen.getByText(/Selección por paridad \(par\/impar\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Volver a experimentos" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("keeps the prefilled draft guarded only after a change through the in-app back link", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail as never);
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 1, offset: 0, limit: 100, items: [detail.request.conditions.start_draw] });
    const { user, router } = setup(`/experimentos/nuevo?base=${detail.id}`);
    await screen.findByDisplayValue("Trial");
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), " edited");
    await user.click(screen.getByRole("link", { name: "Volver a experimentos" }));
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/experimentos/nuevo");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("blocks a new base query from replacing an edited prefilled draft", async () => {
    vi.mocked(apiClient.getExperiment).mockImplementation(async (id) => id === "other"
      ? { ...detail, request: { ...detail.request, name: "Next base" } } as never : detail as never);
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 1, offset: 0, limit: 100, items: [detail.request.conditions.start_draw] });
    const { user, router } = setup(`/experimentos/nuevo?base=${detail.id}`);
    await screen.findByDisplayValue("Trial");
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), " edited");
    await act(async () => { await router.navigate("/experimentos/nuevo?base=other"); });
    const dialog = await screen.findByRole("alertdialog");
    expect(router.state.location.search).toBe(`?base=${detail.id}`);
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Trial edited");
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(1);
    await user.click(within(dialog).getByRole("button", { name: "Seguir editando" }));
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Trial edited");
    await act(async () => { await router.navigate("/experimentos/nuevo?base=other"); });
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Next base"));
    expect(router.state.location.search).toBe("?base=other");
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(2);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("guards base removal for an edited prefill, then clears the draft on leave", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail as never);
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 1, offset: 0, limit: 100, items: [detail.request.conditions.start_draw] });
    const { user, router } = setup(`/experimentos/nuevo?base=${detail.id}`);
    await screen.findByDisplayValue("Trial");
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), " edited");
    await act(async () => { await router.navigate("/experimentos/nuevo"); });
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(router.state.location.search).toBe(`?base=${detail.id}`);
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Trial edited");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("loads another base without a prompt while clean and resets on clean base removal", async () => {
    vi.mocked(apiClient.getExperiment).mockImplementation(async (id) => id === "other"
      ? { ...detail, request: { ...detail.request, name: "Next base" } } as never : detail as never);
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 1, offset: 0, limit: 100, items: [detail.request.conditions.start_draw] });
    const { router } = setup(`/experimentos/nuevo?base=${detail.id}`);
    await screen.findByDisplayValue("Trial");
    await act(async () => { await router.navigate("/experimentos/nuevo?base=other"); });
    expect(await screen.findByDisplayValue("Next base")).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await act(async () => { await router.navigate("/experimentos/nuevo"); });
    await waitFor(() => expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue(""));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("guards a dirty blank draft when adding a base, but allows unrelated query changes", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(detail as never);
    const { user, router } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Borrador");
    await act(async () => { await router.navigate("/experimentos/nuevo?view=compact"); });
    expect(router.state.location.search).toBe("?view=compact");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await act(async () => { await router.navigate(`/experimentos/nuevo?base=${detail.id}`); });
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Borrador");
    expect(apiClient.getExperiment).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Seguir editando" }));
    expect(router.state.location.search).toBe("?view=compact");
  });

  it("ignores a delayed previous base response after navigating to a new base", async () => {
    let resolveOld!: (value: typeof detail) => void;
    vi.mocked(apiClient.getExperiment).mockImplementation((id) => id === "other"
      ? Promise.resolve({ ...detail, request: { ...detail.request, name: "Next base" } } as never)
      : new Promise<typeof detail>((resolve) => { resolveOld = resolve; }) as never);
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 1, offset: 0, limit: 100, items: [detail.request.conditions.start_draw] });
    const { router } = setup(`/experimentos/nuevo?base=${detail.id}`);
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledWith(detail.id));
    await act(async () => { await router.navigate("/experimentos/nuevo?base=other"); });
    expect(await screen.findByDisplayValue("Next base")).toBeInTheDocument();
    await act(async () => { resolveOld(detail); });
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Next base");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("distinguishes a missing base from a network error without posting", async () => {
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new ApiError(404, "not found"));
    const first = setup("/experimentos/nuevo?base=gone");
    expect(await screen.findByRole("alert")).toHaveTextContent(/ya no existe/);
    first.unmount();
    vi.mocked(apiClient.getExperiment).mockRejectedValueOnce(new NetworkError());
    setup("/experimentos/nuevo?base=offline");
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo contactar al servidor/);
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
});

describe("ODD03b dated starting draws", () => {
  it("labels the date filter, keeps a same-day selection and clears it without choosing a different day", async () => {
    const { user, router } = setup();
    await screen.findByRole("option", { name: "2025-09-02 05:10" });
    const date = screen.getByLabelText("Filtrar sorteos por fecha");
    expect(date).toHaveAttribute("type", "date");
    expect(date).toHaveAccessibleDescription(/Vacío: todas las fechas/);
    await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), "2025-09-02 05:15");
    fireEvent.change(date, { target: { value: "2025-09-02" } });
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue("2025-09-02 05:15"));
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(0, 100, "2025-09-02");
    expect(apiClient.getStartingDrawAvailability).toHaveBeenCalledWith("2025-09-02");
    fireEvent.change(date, { target: { value: "2025-09-03" } });
    await screen.findByRole("option", { name: "2025-09-03 05:10" });
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue("");
    expect(screen.queryByRole("option", { name: "2025-09-02 05:15" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Volver a experimentos" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/experimentos/nuevo");
  });

  it("distinguishes dates without history from dates with only unranked history", async () => {
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => ({
      total: date ? 0 : 2, offset, limit, items: date ? [] : ["2025-09-02 05:10"],
    }));
    vi.mocked(apiClient.getStartingDrawAvailability).mockImplementation(async (date) => ({
      date, history_total: date === "2025-09-03" ? 0 : 4, ranked_total: 0,
    }));
    setup();
    const date = await screen.findByLabelText("Filtrar sorteos por fecha");
    fireEvent.change(date, { target: { value: "2025-09-03" } });
    expect(await screen.findByText(/No hay sorteos en esta fecha/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
    fireEvent.change(date, { target: { value: "2025-09-04" } });
    await waitFor(() => expect(apiClient.getStartingDrawAvailability).toHaveBeenCalledWith("2025-09-04"));
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(0, 100, "2025-09-04");
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toBeDisabled();
  });

  it("ignores older filter and pagination responses after a newer date is selected", async () => {
    let resolveOld!: (page: { total: number; offset: number; limit: number; items: string[] }) => void;
    let resolveMore!: (page: { total: number; offset: number; limit: number; items: string[] }) => void;
    vi.mocked(apiClient.getStartingDraws).mockImplementation((offset = 0, limit = 100, date) => {
      if (date === "2025-09-03") return new Promise((resolve) => { resolveOld = resolve; });
      if (!date && offset > 0) return new Promise((resolve) => { resolveMore = resolve; });
      return Promise.resolve({ total: date ? 1 : 150, offset, limit,
        items: [date ? `${date} 05:10` : "2025-09-02 05:10"] });
    });
    const { user } = setup();
    await screen.findByRole("option", { name: "2025-09-02 05:10" });
    await user.click(screen.getByRole("button", { name: "Cargar más sorteos" }));
    const date = screen.getByLabelText("Filtrar sorteos por fecha");
    fireEvent.change(date, { target: { value: "2025-09-03" } });
    await waitFor(() => expect(apiClient.getStartingDraws).toHaveBeenCalledWith(0, 100, "2025-09-03"));
    fireEvent.change(date, { target: { value: "2025-09-04" } });
    await screen.findByRole("option", { name: "2025-09-04 05:10" });
    await act(async () => {
      resolveOld({ total: 2, offset: 0, limit: 100, items: ["2025-09-03 05:10"] });
      resolveMore({ total: 150, offset: 1, limit: 100, items: ["2025-09-02 05:15"] });
    });
    expect(screen.queryByRole("option", { name: "2025-09-03 05:10" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "2025-09-02 05:15" })).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Cargar más sorteos" })).not.toBeInTheDocument();
  });

  it("does not accept a selected draw after its same-day reload reports no ranking", async () => {
    let datedLoads = 0;
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => {
      if (date === "2025-09-02") {
        datedLoads += 1;
        return { total: datedLoads === 1 ? 1 : 0, offset, limit,
          items: datedLoads === 1 ? ["2025-09-02 05:10"] : [] };
      }
      return { total: 1, offset, limit, items: ["2025-09-02 05:10"] };
    });
    vi.mocked(apiClient.getStartingDrawAvailability).mockImplementation(async (date) => ({
      date, history_total: 1, ranked_total: datedLoads === 1 ? 1 : 0,
    }));
    const { user } = setup();
    const date = screen.getByLabelText("Filtrar sorteos por fecha");
    fireEvent.change(date, { target: { value: "2025-09-02" } });
    await screen.findByRole("option", { name: "2025-09-02 05:10" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), "2025-09-02 05:10");
    fireEvent.change(date, { target: { value: "" } });
    await screen.findByRole("option", { name: "2025-09-02 05:10" });
    fireEvent.change(date, { target: { value: "2025-09-02" } });
    expect(await screen.findByText(/Ese sorteo ya no está disponible/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue("2025-09-02 05:10");
    expect(screen.getByRole("option", { name: /2025-09-02 05:10/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("rechecks a selected off-page draw within its day and keeps it valid after reloading", async () => {
    const late = "2025-09-03 05:10";
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => ({
      total: date ? 101 : 1000, offset, limit,
      items: date ? offset === 0
        ? Array.from({ length: 100 }, (_, i) => `${date} ${String(Math.floor(i / 60)).padStart(2, "0")}:${String(i % 60).padStart(2, "0")}`)
        : [late] : ["2025-09-02 05:10"],
    }));
    vi.mocked(apiClient.getStartingDrawAvailability).mockImplementation(async (date) => ({ date, history_total: 101, ranked_total: 101 }));
    const { user } = setup();
    const date = screen.getByLabelText("Filtrar sorteos por fecha");
    fireEvent.change(date, { target: { value: "2025-09-03" } });
    await screen.findByRole("option", { name: "2025-09-03 00:00" });
    await user.click(screen.getByRole("button", { name: "Cargar más sorteos" }));
    await screen.findByRole("option", { name: late });
    await user.selectOptions(screen.getByRole("combobox", { name: "Sorteo inicial" }), late);
    fireEvent.change(date, { target: { value: "" } });
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue(late));
    fireEvent.change(date, { target: { value: "2025-09-03" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Continuar" })).toBeEnabled());
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toHaveValue(late);
    expect(screen.getByRole("option", { name: late })).toBeEnabled();
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(100, 100, "2025-09-03");
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Prueba");
    await user.type(screen.getByRole("textbox", { name: "Capital inicial (RD$)" }), "100");
    await user.type(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }), "200");
    await user.type(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" }), "0");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
  });

  it("paginates only the selected day and retries a failed dated request", async () => {
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => {
      if (date === "2025-09-03" && offset === 0) throw new NetworkError();
      return { total: date ? 101 : 2, offset, limit, items: [date ? `${date} ${offset ? "05:15" : "05:10"}` : "2025-09-02 05:10"] };
    });
    const { user } = setup();
    fireEvent.change(await screen.findByLabelText("Filtrar sorteos por fecha"), { target: { value: "2025-09-03" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(/Reintentá/);
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
    vi.mocked(apiClient.getStartingDraws).mockImplementation(async (offset = 0, limit = 100, date) => ({
      total: date ? 101 : 2, offset, limit, items: [date ? `${date} ${offset ? "05:15" : "05:10"}` : "2025-09-02 05:10"],
    }));
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByRole("option", { name: "2025-09-03 05:10" });
    await user.click(screen.getByRole("button", { name: "Cargar más sorteos" }));
    expect(await screen.findByRole("option", { name: "2025-09-03 05:15" })).toBeInTheDocument();
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(1, 100, "2025-09-03");
  });
});

describe("LW09 wizard", () => {
  it("shows empty and disconnected catalog states without inventing a default draw, then retries", async () => {
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 0, offset: 0, limit: 100, items: [] });
    const { user, unmount: unmountFirst } = setup();
    expect(await screen.findByText(/No hay sorteos iniciales/)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Sorteo inicial" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled();
    // A fresh visit after a disconnection retains no fake draw.
    unmountFirst();
    vi.mocked(apiClient.getCatalog).mockRejectedValueOnce(new NetworkError());
    const second = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/experimentos/nuevo"] });
    const { unmount } = render(<RouterProvider router={second} />);
    expect(await screen.findByText(/No se pudo contactar al servidor/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("option", { name: /2025-09-02 05:10/ })).toBeInTheDocument();
    unmount();
  });

  it("loads further ranked draws on demand without requesting all history", async () => {
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 150, offset: 0, limit: 100, items: ["2025-09-02 05:10"] });
    vi.mocked(apiClient.getStartingDraws).mockResolvedValueOnce({ total: 150, offset: 1, limit: 100, items: ["2025-09-02 05:15"] });
    const { user } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.click(screen.getByRole("button", { name: "Cargar más sorteos" }));
    expect(await screen.findByRole("option", { name: /2025-09-02 05:15/ })).toBeInTheDocument();
    expect(apiClient.getStartingDraws).toHaveBeenNthCalledWith(2, 1, 100);
  });

  it("keeps the original field order for keyboard navigation across stop limits and seed", async () => {
    setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    const fields = screen.getByRole("region", { name: "Condiciones comunes" }).querySelectorAll("input, select");
    expect(Array.from(fields, (field) => field.id)).toEqual([
      "name", "draw_date", "start_draw", "capital", "goal", "settlement", "max_bets", "max_minutes", "seed",
    ]);
  });

  it("announces the seed help together with validation errors, without losing either reference", async () => {
    const { user } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    const seed = screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" });
    const help = screen.getByText(/El mismo código permite repetir la selección aleatoria/);
    expect(seed).toHaveAttribute("aria-describedby", "seed-help");
    expect(seed).toHaveAccessibleDescription(help.textContent!);
    expect(help).toHaveTextContent("0 a 9.007.199.254.740.991");
    expect(help).toHaveTextContent("por sorteo entre todas las estrategias");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(seed).toHaveAttribute("aria-invalid", "true");
    expect(seed).toHaveAttribute("aria-describedby", "seed-help seed-error");
    expect(seed).toHaveAccessibleDescription(`${help.textContent} Ingresá un entero entre 0 y 9.007.199.254.740.991.`);
    for (const id of seed.getAttribute("aria-describedby")!.split(" ")) expect(document.getElementById(id)).toBeInTheDocument();
    const draw = screen.getByRole("combobox", { name: "Sorteo inicial" });
    expect(draw).toHaveAttribute("aria-describedby", "start_draw-help start_draw-error");
    expect(draw).toHaveAccessibleDescription(/Elegí un sorteo con ranking disponible/);
  });

  it("loads ranked starting draws via paginated endpoint; three steps preserve conditions and summary", async () => {
    const { user } = setup();
    await conditions(user);
    expect(apiClient.getStartingDraws).toHaveBeenCalledWith(0, 100);
    expect(screen.getByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
    const summary = within(screen.getByRole("complementary", { name: "Resumen del experimento" }));
    expect(summary.getAllByText(/2,000/).length).toBeGreaterThan(0);
    expect(summary.getAllByText("Estrategias").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Atrás" }));
    expect(screen.getByRole("textbox", { name: "Capital inicial (RD$)" })).toHaveValue("2000");
    expect(screen.getByRole("combobox", { name: "Cómo contar los premios" })).toHaveValue("all");
    expect(screen.getByRole("option", { name: "Sumar los premios" })).toHaveValue("all");
    expect(screen.getByRole("option", { name: "Contar solo el mayor premio por número" })).toHaveValue("best");
    expect(screen.getByText(/El mismo código permite repetir la selección aleatoria/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuar" })).toHaveClass("btn-primary");
    expect(screen.getByRole("button", { name: "Salir" })).toHaveClass("btn-secondary");
    expect(screen.getByText("1 Condiciones")).toHaveAttribute("aria-current", "step");
  });

  it("rejects invalid money, goal, start, limits and seed without rounding", async () => {
    const { user } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.type(screen.getByRole("textbox", { name: "Capital inicial (RD$)" }), "2.5");
    await user.type(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }), "1");
    await user.type(screen.getByRole("textbox", { name: "Máximo de apuestas" }), "10000001");
    await user.type(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" }), "9007199254740992");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Condiciones" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/errores/i);
    expect(screen.getByRole("textbox", { name: "Capital inicial (RD$)" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Código para repetir el azar (semilla)" })).toHaveValue("9007199254740992");
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });

  it("builds accepted 60/40 mix K10 max12 and posts exact body once, then stable detail path", async () => {
    let resolve!: (value: { id: string; status: string }) => void;
    vi.mocked(apiClient.createExperiment).mockReturnValue(new Promise((r) => { resolve = r; }));
    const { user, router } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Mi mezcla");
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "blend");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema 1" }), "transition");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema 2" }), "cold");
    await user.clear(screen.getByRole("textbox", { name: "Peso 1 (%)" }));
    await user.type(screen.getByRole("textbox", { name: "Peso 1 (%)" }), "60");
    await user.clear(screen.getByRole("textbox", { name: "Peso 2 (%)" }));
    await user.type(screen.getByRole("textbox", { name: "Peso 2 (%)" }), "40");
    await user.selectOptions(screen.getByRole("combobox", { name: "Cobertura de la estrategia 1" }), "10");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Revisar" })).toBeInTheDocument();
    expect(screen.getByText(/Combinación de sistemas: Transición 60% \+ Fríos 40%/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(screen.getByRole("button", { name: "Agregando…" })).toBeDisabled();
    expect(apiClient.createExperiment).toHaveBeenCalledTimes(1);
    expect(apiClient.createExperiment).toHaveBeenCalledWith({ request: {
      name: "Prueba Q80", conditions: { start_draw: "2025-09-02 05:10", capital: 2000, goal: 2800, settlement: "all", max_bets: 12, max_minutes: null, seed: 42 },
      strategies: [{ name: "Mi mezcla", selector: "blend", components: [{ system: "transition", weight: 60 }, { system: "cold", weight: 40 }], coverage: 10, staking: "flat" }],
    } });
    resolve({ id: "exp-1", status: "pending" });
    await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos/exp-1"));
  });

  it("parity forces coverage 50; invalid mix sum and duplicate strategy names block review", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Par");
    await user.selectOptions(screen.getByRole("combobox", { name: "Cobertura de la estrategia 1" }), "10");
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "parity");
    expect(screen.getByText(/50 números/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Agregar estrategia" }));
    await user.click(screen.getByRole("button", { name: /Estrategia 2/ }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 2" }), " pAR ");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
    expect(screen.getByText(/El nombre debe ser único/i)).toBeInTheDocument();
  });

  it("maps a field-located duplicate-name 422 to the offending strategy's name field and step", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [
      { loc: ["body", "request", "strategies", 0, "name"], msg: "Value error", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(await screen.findByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveAttribute("aria-invalid", "true");
  });

  it("maps 422 field errors to correct step; 507 and network failures preserve entered values", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [{ loc: ["body", "request", "conditions", "goal"], msg: "Value error", type: "value_error" }]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    await screen.findByRole("textbox", { name: "Meta de saldo final (RD$)" });
    expect(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" })).toHaveAttribute("aria-invalid", "true");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(507, "quota exceeded"));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/No hay espacio para crear el experimento/);
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new NetworkError());
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Sin respuesta del servidor\. Puede que el experimento se haya creado/);
    expect(screen.getByText("Una")).toBeInTheDocument();
  });

  it("blocks browser back while dirty, then proceeds when confirmed", async () => {
    const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/ajustes", "/experimentos/nuevo"] });
    const user = userEvent.setup();
    render(<RouterProvider router={router} />);
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Borrador");
    await act(async () => { await router.navigate(-1); });
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/experimentos/nuevo");
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/ajustes"));
  });

  it("requests native refresh confirmation only while dirty and cleans listener on leave", async () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { user } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    const before = add.mock.calls.filter(([name]) => name === "beforeunload").length;
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Borrador");
    expect(add.mock.calls.filter(([name]) => name === "beforeunload").length).toBeGreaterThan(before);
    await user.click(screen.getByRole("link", { name: "Ajustes" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(remove.mock.calls.some(([name]) => name === "beforeunload")).toBe(true));
    add.mockRestore(); remove.mockRestore();
  });

  it("does not block a clean wizard navigation", async () => {
    const { user, router } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.click(screen.getByRole("link", { name: "Ajustes" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/ajustes"));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("focuses and clears a bare mix component error when its subfield changes while retaining unrelated errors", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Mix");
    await user.selectOptions(screen.getByRole("combobox", { name: "Método de la estrategia 1" }), "blend");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema 1" }), "transition");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema 2" }), "cold");
    await user.type(screen.getByRole("textbox", { name: "Peso 1 (%)" }), "60");
    await user.type(screen.getByRole("textbox", { name: "Peso 2 (%)" }), "40");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "invalid", [
      { loc: ["body", "request", "strategies", 0, "components", 1], msg: "component rejected", type: "value_error" },
      { loc: ["body", "request", "strategies", 0, "staking"], msg: "staking rejected", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    const system = await screen.findByRole("combobox", { name: "Sistema 2" });
    expect(system).toHaveFocus();
    expect(screen.getByText(/component rejected/)).toBeInTheDocument();
    await user.selectOptions(system, "transition");
    expect(screen.queryByText(/component rejected/)).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Forma de ajustar la apuesta" })).toHaveAttribute("aria-invalid", "true");
  });

  it("maps a strategy-level 422 without a field to that strategy's block, expands it and keeps the server detail", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Agregar estrategia" }));
    await user.click(screen.getByRole("button", { name: /Estrategia 2/ }));
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 2" }), "Otra");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "cold");
    await user.click(screen.getByRole("button", { name: /Estrategia 1/ }));
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [
      { loc: ["body", "request", "strategies", 1], msg: "blend weights must add up to 100", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(await screen.findByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Estrategia 2/, expanded: true })).toBeInTheDocument();
    expect(screen.getByText(/Estrategia rechazada/i)).toBeInTheDocument();
    expect(screen.getByText(/blend weights must add up to 100/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 2" })).not.toHaveAttribute("aria-invalid", "true");
  });

  it("maps a conditions-level 422 without a field to the conditions section, not silently onto goal", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [
      { loc: ["body", "request", "conditions"], msg: "goal is the final balance and must exceed capital", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    expect(await screen.findByRole("heading", { name: "Condiciones" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" })).not.toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/goal is the final balance and must exceed capital/)).toBeInTheDocument();
  });

  it("clears the server notice and the matching field error on edit, keeping an unrelated field's error", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [
      { loc: ["body", "request", "conditions", "goal"], msg: "Value error", type: "value_error" },
      { loc: ["body", "request", "conditions", "max_bets"], msg: "Value error", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    await screen.findByRole("heading", { name: "Condiciones" });
    expect(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Máximo de apuestas" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(/Revisá los campos señalados/);
    await user.clear(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }));
    await user.type(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" }), "3000");
    // The specific server notice cleared because the field just fixed had a server
    // error, but the unrelated conditions.max_bets error (not addressed yet) must
    // survive the edit.
    expect(screen.getByRole("textbox", { name: "Meta de saldo final (RD$)" })).not.toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("textbox", { name: "Máximo de apuestas" })).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Revisá los errores señalados junto a los campos antes de continuar.");
  });

  it("moves focus to the first offending field after a server error, not just the alert", async () => {
    const { user } = setup();
    await conditions(user);
    await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Una");
    await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "transition");
    await user.click(screen.getByRole("button", { name: "Continuar" }));
    vi.mocked(apiClient.createExperiment).mockRejectedValueOnce(new ApiError(422, "inválido", [
      { loc: ["body", "request", "strategies", 0, "name"], msg: "Value error", type: "value_error" },
    ]));
    await user.click(screen.getByRole("button", { name: "Agregar a la cola" }));
    await screen.findByRole("heading", { name: "Estrategias" });
    expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveFocus();
  });

  it("guards dirty navigation with accessible stay/leave, without canceling backend work", async () => {
    const { user, router } = setup();
    await screen.findByRole("option", { name: /2025-09-02 05:10/ });
    await user.type(screen.getByRole("textbox", { name: "Nombre del experimento" }), "Borrador");
    await user.click(screen.getByRole("link", { name: "Ajustes" }));
    const dialog = screen.getByRole("alertdialog");
    expect(router.state.location.pathname).toBe("/experimentos/nuevo");
    await user.click(within(dialog).getByRole("button", { name: "Seguir editando" }));
    expect(screen.getByRole("textbox", { name: "Nombre del experimento" })).toHaveValue("Borrador");
    await user.click(screen.getByRole("link", { name: "Ajustes" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/ajustes"));
    expect(apiClient.createExperiment).not.toHaveBeenCalled();
  });
});
