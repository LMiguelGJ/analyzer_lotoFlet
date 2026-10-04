import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import experimentsPage from "../../api/__fixtures__/experiments-page.json";
import type { Page } from "../../api/types";
import type { ExperimentSummary, LegacyExperimentSummary, ProfileBatchExperimentSummary, ProfileExperimentSummary } from "../../api/types";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      listExperiments: vi.fn(),
      deleteExperiment: vi.fn(),
      getQueue: vi.fn(),
    },
  };
});

const fixture = experimentsPage as Page<LegacyExperimentSummary>;
const profileItem: ProfileExperimentSummary = {
  id: "profile-held", request_kind: "profile", status: "held", created_at: null,
  request: { kind: "profile", schema_version: 1, name: "Perfil de prueba", dataset_sha256: "a".repeat(64), profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), entry_policy: "all_rows/v1",
    conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: null, max_bet_draws: null, end_minute: null, duration_minutes: null },
    selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 1, numbers: [7], seed: null, algorithm_version: null },
    staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 100 } },
  profile: { schema_version: 1, profile_id: "test", revision: 1, universe_size: 100, positions: 1, allows_repeats: true, multipliers: [{ numerator: 80, denominator: 1 }], currency: "USD", scale: 2, stake_increment: 1, minimum_stake: 1, maximum_stake: 100000, max_coverage: 10, max_exposure: 100000, best_rule: "maximum-payout/v1" },
  display: { name: "Perfil de prueba", currency: "USD", scale: 2, capital: 10000, goal: 20000, selector_label: "static-numbers/v1", staking_label: "flat-per-number/v1" },
  sources: { history_id: "a", history_sha256: "a", rankings_id: "", rankings_sha256: "", code_version: "profile-v1" },
  runs: [{ ordinal: 0, configuration_id: null, status: "pending", result_kind: "profile", result: null, bets_count: 0 }],
};
const profileBatchV5: ProfileBatchExperimentSummary = {
  request_kind: "profile", request_schema_version: 5, id: "batch-v5", status: "completed", created_at: null,
  request: { schema_version: 5, kind: "profile_batch", profile_id: "test", profile_revision: 1,
    profile_sha256: "b".repeat(64), dataset_sha256: "a".repeat(64),
    conditions: { schema_version: 1, start_draw: "2025-01-01 05:10", capital: 10000, goal: 20000, settlement: "all", max_elapsed_draws: 2, max_bet_draws: 1, end_minute: null, duration_minutes: null },
    strategies: [{ definition_version: 1, name: "Frozen strategy", selector: "static-numbers/v1", coverage: 1, staking: "flat-per-number/v1", selector_parameters: { numbers: [7] }, staking_parameters: {}, closing_defaults: {} }],
    max_draws: 2, source_version: "canonical-history/v1" },
  profile: profileItem.profile,
  display: { ...profileItem.display, name: "Lote v5 guardado" },
  sources: profileItem.sources,
  batch_admission: {
    strategy_refs: [{ id: "strategy-id", revision: 3, definition_sha256: "c".repeat(64) }],
    source_identity: { dataset_sha256: "a".repeat(64), source_sha256: "d".repeat(64), canonical_sha256: "e".repeat(64), row_count: 4,
      profile_id: "test", profile_revision: 1, profile_sha256: "b".repeat(64), archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null },
    requested_constraints: {}, effective_constraints: {}, policy_revision: 1, policy: {},
  },
  runs: [{ result_kind: "profile", ordinal: 0, configuration_id: null, status: "completed", result_schema_version: null,
    strategy: { id: "strategy-id", revision: 3, definition_sha256: "c".repeat(64), name: null }, result: null, bets_count: 0,
    complete: false, completion: "unavailable", stop_category: "unknown", stop_reason: "failed", stop_code: "unknown", error: null }],
};

function emptyPage(offset = 0, limit = 20): Page<ExperimentSummary> {
  return { total: 0, offset, limit, items: [] };
}

function setup(initialEntry = "/experimentos") {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: [initialEntry] });
  const view = render(<RouterProvider router={router} />);
  return { user: userEvent.setup(), router, ...view };
}

beforeEach(() => {
  vi.mocked(apiClient.listExperiments).mockReset();
  vi.mocked(apiClient.deleteExperiment).mockReset();
  vi.mocked(apiClient.getQueue).mockReset();
  vi.mocked(apiClient.getQueue).mockResolvedValue({ active_id: null, pending: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, held: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, last_failure: null });
});

describe("LW10 experiments list · states", () => {
  it("shows a loading state before the first response arrives", async () => {
    let resolvePage!: (page: Page<ExperimentSummary>) => void;
    vi.mocked(apiClient.listExperiments).mockReturnValueOnce(
      new Promise((resolve) => { resolvePage = resolve; }),
    );
    setup();

    expect(screen.getByRole("status", { name: "" }) || screen.getByText(/Cargando simulaciones/)).toBeTruthy();
    resolvePage(fixture);
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
  });

  it("shows first-run guidance when there are zero experiments", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(emptyPage());
    setup();

    expect(await screen.findByText(/Las simulaciones muestran cómo se comportan tus estrategias con datos históricos/)).toBeInTheDocument();
    // The empty state owns the single primary action; the header does not repeat it.
    const links = screen.getAllByRole("link", { name: "Nueva simulación" });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/experimentos/nuevo");
    expect(links[0]).toHaveClass("ledger-button-primary");
    expect(screen.queryByRole("group", { name: "Filtros de simulaciones" })).not.toBeInTheDocument();
  });

  it("shows a disconnected state with NetworkError wording, never claiming the server stopped, and retries", async () => {
    vi.mocked(apiClient.listExperiments)
      .mockRejectedValueOnce(new NetworkError())
      .mockResolvedValueOnce(fixture);
    const { user } = setup();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/No se pudo contactar al servidor/);
    expect(alert.textContent ?? "").not.toMatch(/detuvo|detenido|se detuvo/i);
    expect(alert.textContent).toMatch(/Iniciá el laboratorio desde el lanzador y después reintentá/);

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
  });

  it("shows a generic server-error state distinct from disconnection, and retries", async () => {
    vi.mocked(apiClient.listExperiments)
      .mockRejectedValueOnce(new ApiError(500, "boom"))
      .mockResolvedValueOnce(fixture);
    const { user } = setup();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/No se pudo cargar el listado/);
    expect(alert.textContent).toMatch(/Tu información se conserva/);

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
  });

  it("shows a no-matches state from the server, distinct from the empty state", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture).mockResolvedValueOnce(emptyPage());
    const { user } = setup();
    await screen.findByText("Fríos K1");

    await user.type(screen.getByLabelText("Buscar por nombre"), "no-existe-esto");
    expect(await screen.findByText(/Sin coincidencias/)).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay simulaciones/)).not.toBeInTheDocument();
    // Teaches and offers exactly one next step, and the primary action stays the header's.
    const empty = screen.getByText("Sin coincidencias").closest("section")!;
    expect(within(empty).getAllByRole("button")).toHaveLength(1);
    expect(within(empty).queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Nueva simulación" })).toHaveLength(1);
  });

  it("clears the filters from the no-matches state and reloads the full ledger", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(emptyPage()).mockResolvedValueOnce(fixture);
    const { user, router } = setup("/experimentos?name=nada&status=failed");
    await screen.findByText("Sin coincidencias");
    const empty = screen.getByText("Sin coincidencias").closest("section")!;
    await user.click(within(empty).getByRole("button", { name: "Limpiar filtros" }));
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("renders static skeleton rows with a screen-reader status while loading", () => {
    vi.mocked(apiClient.listExperiments).mockReturnValueOnce(new Promise(() => {}));
    setup();
    expect(screen.getByRole("status")).toHaveTextContent("Cargando simulaciones…");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("LW10 experiments list · data and navigation", () => {
  it("lists completed cycling with profile formatting and never offers a flat clone", async () => {
    const cycling: ProfileExperimentSummary = {
      ...profileItem, id: "cycling", status: "completed",
      request: { ...profileItem.request, schema_version: 2, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } },
      display: { ...profileItem.display, name: "Cycling", staking_label: "Escalera cíclica Q80 · apuesta dinámica por sorteo" },
      runs: [{ ...profileItem.runs[0], status: "completed", bets_count: 1,
        result: { schema_version: 2, profile_id: "test", profile_revision: 1, outcome: "limit", collisions: [], elapsed_draws: 1, bet_draws: 1, wagered: 100, paid: 0, final_balance: 9900, delta: -100 } }],
    };
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [cycling] });
    const { user } = setup();
    const link = await screen.findByRole("link", { name: "Cycling" });
    expect(link).toHaveAttribute("href", "/experimentos/cycling");
    expect(screen.getByText(/Perfil test · 1 posiciones/)).toBeInTheDocument();
    expect(screen.getByText(/Capital USD 100.00/)).toBeInTheDocument();
    expect(screen.getByText(/Escalera cíclica Q80/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Acciones de Perfil de prueba" }));
    expect(screen.queryByRole("link", { name: "Usar como base" })).not.toBeInTheDocument();
    expect(screen.getByText(/No disponible como base/)).toBeInTheDocument();
  });
  it("labels a recovery run by its saved profile policy instead of calling it a strategy", async () => {
    const recovery: ProfileExperimentSummary = {
      ...profileItem, id: "recovery", request: { ...profileItem.request, schema_version: 4,
        staking: { schema_version: 1, target_margin: 200, rounds: 3, end_mode: "stop" } },
      display: { ...profileItem.display, name: "Recovery", staking_label: "Escalera de recuperación" },
      runs: [{ ...profileItem.runs[0], result: null }],
    };
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [recovery] });
    setup();
    const row = (await screen.findByRole("link", { name: "Recovery" })).closest("tr");
    expect(row).toHaveTextContent(/Perfil test · 1 posiciones.*Escalera de recuperación/);
    expect(screen.getByRole("columnheader", { name: "Corridas" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Estrategias" })).not.toBeInTheDocument();
  });
  it("requests the bounded default page (offset 0, limit 20) and renders truthful columns only", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();

    await screen.findByText("Fríos K1");
    expect(apiClient.listExperiments).toHaveBeenCalledWith({ offset: 0, limit: 20, sort: "created_at", order: "desc" });
    expect(apiClient.listExperiments).toHaveBeenCalledTimes(1);

    // Configurations count comes from the real strategies array (1 and 2), not an invented metric.
    const table = screen.getByRole("table");
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByText("1")).toBeInTheDocument();
    expect(within(rows[2]).getByText("2")).toBeInTheDocument();

    expect(screen.getByRole("columnheader", { name: "Corridas" })).toHaveClass("table-numeric");
    expect(within(rows[1]).getAllByRole("cell")[1]).toHaveClass("table-numeric");
    expect(screen.getByRole("columnheader", { name: /Creado/ })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: /Creado/ })).toHaveClass("table-date");
    expect(within(rows[1]).getAllByRole("cell")[2]).toHaveClass("table-date");
    expect(screen.getByRole("columnheader", { name: /Estado/ })).toHaveClass("table-status");
    expect(screen.getByRole("columnheader", { name: "Acciones" })).toHaveClass("table-actions");
    expect(within(rows[1]).getByTitle("2026-09-29T12:30:00Z")).not.toHaveTextContent("—");
    expect(within(rows[2]).getByTitle("Fecha no registrada")).toHaveTextContent("—");
  });

  it("keeps a long experiment name intact in a word-wrapping column with local horizontal scroll", async () => {
    const longName = "Experimento con nombre deliberadamente muy largo para probar el límite visual";
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ ...fixture, items: [{ ...fixture.items[0], request: { ...fixture.items[0].request, name: longName } }] });
    setup();
    const link = await screen.findByRole("link", { name: longName });
    expect(link.closest("td")).toHaveClass("table-name");
    expect(link).toHaveAttribute("href", `/experimentos/${fixture.items[0].id}`);
    expect(screen.getByRole("region", { name: "Simulaciones" })).toHaveClass("overflow-x-auto");
  });

  it("shows status chips: a financial outcome only when every run closed with it, execution state otherwise", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();

    await screen.findByText("Fríos K1");
    const table = screen.getByRole("table");
    const goal = within(table).getByText("Meta alcanzada");
    expect(goal).toHaveClass("ledger-chip", "ledger-chip-success");
    expect(goal).toHaveAttribute("data-status-kind", "outcome");
    const running = within(table).getByText("En curso");
    expect(running).toHaveClass("ledger-chip", "ledger-chip-info");
    expect(running).toHaveAttribute("data-status-kind", "execution");
    // Completed without a uniform outcome stays an execution state, never a goal claim.
    expect(within(table).queryByText("Ejecución completada")).not.toBeInTheDocument();
  });

  it.each([
    ["ruin", "Se agotó el capital", "ledger-chip-danger"],
    ["limit", "Ejecución completada", "ledger-chip-neutral"],
  ] as const)("maps a completed %s outcome to the %s chip", async (outcome, label, variant) => {
    const base = fixture.items[0];
    const run = { ...base.runs[0], result: { ...base.runs[0].result!, outcome } };
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ ...fixture, total: 1, items: [{ ...base, runs: [run] }] });
    setup();
    const chip = within(await screen.findByRole("table")).getByText(label);
    expect(chip).toHaveClass("ledger-chip", variant);
  });

  it("shows the net result as a signed money figure with money-semantic color only on the figure", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();
    const rows = within(await screen.findByRole("table")).getAllByRole("row");
    const gain = within(rows[1]).getByText(/^\+.*837/);
    expect(gain).toHaveClass("ledger-figure", "ledger-money-positive");
    expect(gain.closest("td")).toHaveClass("table-numeric");
    // A multi-run comparison has no single net figure.
    expect(within(rows[2]).queryByText(/ledger-money/)).not.toBeInTheDocument();
    expect(within(rows[2]).getAllByRole("cell")[4]).toHaveTextContent("—");
  });

  it("derives the stat band from the fetched page: total, goal reached and running", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();
    await screen.findByText("Fríos K1");
    const band = screen.getByRole("group", { name: "Resumen de simulaciones" });
    const stat = (label: string) => within(band).getByText(label).closest(".ledger-stat") as HTMLElement;
    expect(stat("Simulaciones")).toHaveTextContent("2");
    expect(stat("Con meta alcanzada")).toHaveTextContent("1");
    expect(stat("En curso")).toHaveTextContent("1");
    expect(stat("En curso")).toHaveTextContent("de las 2 mostradas");
  });

  it("offers one open-result row action and keeps comparing/deleting behind a ghost menu", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { user } = setup();
    const row = (await screen.findByText("Fríos K1")).closest("tr")!;
    const open = within(row).getByRole("link", { name: "Abrir resultado de Fríos K1" });
    expect(open).toHaveAttribute("href", "/experimentos/exp-completed-1");
    expect(open).not.toHaveClass("ledger-button-primary");
    const trigger = within(row).getByRole("button", { name: "Acciones de Fríos K1" });
    expect(trigger).toHaveClass("ledger-button-ghost");
    await user.click(trigger);
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toHaveClass("ledger-button-ghost");
  });

  it("keeps compact filters (search, status, clear) visible and the sort controls inside the Filtros disclosure", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValue(fixture);
    const { user, router } = setup("/experimentos?name=Fr");
    await screen.findByText("Fríos K1");
    const group = screen.getByRole("group", { name: "Filtros de simulaciones" });
    const disclosure = group.querySelector("details")!;
    expect(disclosure).not.toHaveAttribute("open");
    expect(within(disclosure).getByLabelText("Ordenar por")).toBeInTheDocument();
    const visible = [...group.querySelectorAll("input, select, button")].filter((node) => !disclosure.contains(node));
    expect(visible.length).toBeLessThanOrEqual(4);
    expect(within(group).getByText("Filtros", { selector: "summary" })).toBeInTheDocument();
    await user.selectOptions(within(disclosure).getByLabelText("Ordenar por"), "name");
    await waitFor(() => expect(router.state.location.search).toContain("sort=name"));
  });

  it("has exactly one primary action on the populated ledger", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { container } = setup();
    await screen.findByText("Fríos K1");
    expect(container.querySelectorAll(".ledger-button-primary")).toHaveLength(1);
  });

  it("links the primary action to the wizard and each row name to its stable detail URL", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();

    expect(screen.getByRole("link", { name: "Nueva simulación" })).toHaveAttribute(
      "href",
      "/experimentos/nuevo",
    );
    await screen.findByText("Fríos K1");
    expect(screen.getByRole("link", { name: "Fríos K1" })).toHaveAttribute(
      "href",
      "/experimentos/exp-completed-1",
    );
  });

  it("paginates forward and back using the real offset/limit/total from the server", async () => {
    const secondPage: Page<ExperimentSummary> = {
      total: 25,
      offset: 20,
      limit: 20,
      items: [{ ...fixture.items[0], id: "exp-page-2", request: { ...fixture.items[0].request, name: "Página dos" } }],
    };
    vi.mocked(apiClient.listExperiments)
      .mockResolvedValueOnce({ ...fixture, total: 25 })
      .mockResolvedValueOnce(secondPage);
    const { user, router } = setup();

    await screen.findByText("Fríos K1");
    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    await screen.findByText("Página dos");
    expect(apiClient.listExperiments).toHaveBeenNthCalledWith(2, { offset: 20, limit: 20, sort: "created_at", order: "desc" });
    expect(router.state.location.search).toContain("page=2");
  });

  it("uses URL-backed filters and sort against the server, retaining controls on no matches and navigation", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValue(fixture);
    const { user, router } = setup("/experimentos?name=Fr%C3%ADos&status=running&sort=name&order=asc&page=2");
    await screen.findByText("Fríos K1");
    expect(apiClient.listExperiments).toHaveBeenCalledWith({ offset: 20, limit: 20, name_contains: "Fríos", status: "running", sort: "name", order: "asc" });
    expect(screen.getByRole("columnheader", { name: /Nombre/ })).toHaveAttribute("aria-sort", "ascending");
    await user.selectOptions(screen.getByLabelText("Estado"), "completed");
    await waitFor(() => expect(router.state.location.search).toContain("status=completed"));
    expect(router.state.location.search).not.toContain("page=2");
  });

  it("sanitizes malformed query values, shows missing timestamp as an em dash and active queue ID as a real link", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce({ active_id: "exp-running-2", pending: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, held: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, last_failure: null });
    setup("/experimentos?sort=count&order=evil&page=-1&status=bogus&name=x");
    await screen.findByText("Fríos K1");
    expect(apiClient.listExperiments).toHaveBeenCalledWith({ offset: 0, limit: 20, name_contains: "x", sort: "created_at", order: "desc" });
    expect(screen.getAllByRole("link", { name: /Comparación mezcla/ })[0]).toHaveAttribute("href", "/experimentos/exp-running-2");
    expect(apiClient.getQueue).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("ignores an older response after a newer URL query succeeds", async () => {
    let resolveOld!: (page: Page<ExperimentSummary>) => void;
    vi.mocked(apiClient.listExperiments).mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; })).mockResolvedValueOnce(fixture);
    const { router } = setup();
    await router.navigate("/experimentos?sort=name");
    await screen.findByText("Fríos K1");
    resolveOld(emptyPage());
    await waitFor(() => expect(screen.getByText("Fríos K1")).toBeInTheDocument());
  });

  it("opens the row menu by keyboard, focuses the first action and restores trigger focus on Escape", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { user } = setup();
    await screen.findByText("Fríos K1");
    const trigger = screen.getByRole("button", { name: "Acciones de Fríos K1" });
    trigger.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("menuitem", { name: "Usar como base" })).toHaveFocus();
    expect(screen.getByRole("menuitem", { name: "Usar como base" })).toHaveAttribute("href", "/experimentos/nuevo?base=exp-completed-1");
    await user.keyboard("{Escape}");
    expect(trigger).toHaveFocus();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("moves to the preceding URL page when deleting the last row of a later page", async () => {
    const later = { ...fixture, total: 21, offset: 20, items: [fixture.items[0]] };
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(later).mockResolvedValueOnce({ ...later, total: 20, items: [] }).mockResolvedValueOnce({ ...fixture, total: 20 });
    vi.mocked(apiClient.deleteExperiment).mockResolvedValueOnce(undefined);
    const { user, router } = setup("/experimentos?page=2");
    await screen.findByText("Fríos K1");
    await user.click(screen.getByRole("button", { name: "Acciones de Fríos K1" }));
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar simulación" }));
    await waitFor(() => expect(router.state.location.search).not.toContain("page=2"));
    await waitFor(() => expect(apiClient.listExperiments).toHaveBeenCalledWith({ offset: 0, limit: 20, sort: "created_at", order: "desc" }));
  });

  it("has no axe violations in the ready state", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { container } = setup();

    await screen.findByText("Fríos K1");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("profile batch v5 experiment list compatibility", () => {
  it("uses the saved display name for queue identity, accessible actions, delete dialog, and success notice", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [profileBatchV5] })
      .mockResolvedValueOnce(emptyPage());
    vi.mocked(apiClient.getQueue).mockResolvedValueOnce({ active_id: "batch-v5", pending: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, held: { total: 0, offset: 0, limit: 20, count: 0, items: [] }, last_failure: null });
    vi.mocked(apiClient.deleteExperiment).mockResolvedValueOnce(undefined);
    const { user } = setup();
    const name = profileBatchV5.display.name;
    const links = await screen.findAllByRole("link", { name });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/experimentos/batch-v5");
    expect(links[1]).toHaveAttribute("href", "/experimentos/batch-v5");
    const trigger = screen.getByRole("button", { name: `Acciones de ${name}` });
    await user.click(trigger);
    expect(screen.getByRole("menu", { name: `Acciones de ${name}` })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    const dialog = screen.getByRole("alertdialog", { name: `¿Eliminar la simulación «${name}»?` });
    expect(dialog).toHaveTextContent("Se elimina de forma permanente.");
    await user.click(within(dialog).getByRole("button", { name: "Eliminar simulación" }));
    expect(apiClient.deleteExperiment).toHaveBeenCalledWith("batch-v5", "batch-v5");
    expect(await screen.findByText(`Se eliminó "${name}".`)).toHaveAttribute("role", "status");
  });
});

describe("profile experiment list", () => {
  it.each(["held", "failed", "completed"] as const)("shows %s profile with one run and no legacy base action", async (status) => {
    const row = { ...profileItem, status, runs: [{ ...profileItem.runs[0], status: status === "held" ? "pending" as const : status }] };
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [row] });
    const { user } = setup();
    await screen.findByRole("link", { name: "Perfil de prueba" });
    const table = screen.getByRole("table", { name: "Simulaciones" });
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("1");
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("Capital USD 100.00 · Meta USD 200.00");
    await user.click(screen.getByRole("button", { name: "Acciones de Perfil de prueba" }));
    expect(screen.queryByRole("menuitem", { name: "Usar como base" })).not.toBeInTheDocument();
    expect(screen.getByText(/No disponible como base/)).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Eliminar" })).toHaveFocus();
  });
});

describe("LW10 deletion", () => {
  it("sends confirm_id tied to the target row and removes it from the list on success, announcing and focusing the result", async () => {
    vi.mocked(apiClient.listExperiments)
      .mockResolvedValueOnce(fixture)
      .mockResolvedValueOnce({ ...fixture, total: 1, items: [fixture.items[1]] });
    vi.mocked(apiClient.deleteExperiment).mockResolvedValueOnce(undefined);
    const { user } = setup();

    await screen.findByText("Fríos K1");
    const row = screen.getByText("Fríos K1").closest("tr")!;
    await user.click(within(row).getByRole("button", { name: /Acciones de/ }));
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveAccessibleName("¿Eliminar la simulación «Fríos K1»?");
    expect(dialog).toHaveTextContent(/forma permanente/);
    await user.click(within(dialog).getByRole("button", { name: "Eliminar simulación" }));

    expect(apiClient.deleteExperiment).toHaveBeenCalledWith("exp-completed-1", "exp-completed-1");
    await waitFor(() => expect(screen.queryByText("Fríos K1")).not.toBeInTheDocument());

    const notice = await screen.findByRole("status", { name: "" });
    await waitFor(() => expect(document.activeElement).toBe(notice));
  });

  it("rejects deleting an active experiment with a 409 without removing it, keeping the dialog usable", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValue(fixture);
    vi.mocked(apiClient.deleteExperiment).mockRejectedValueOnce(new ApiError(409, "experiment is active"));
    const { user } = setup();

    await screen.findByText("Comparación mezcla");
    const row = screen.getByText("Comparación mezcla").closest("tr")!;
    await user.click(within(row).getByRole("button", { name: /Acciones de/ }));
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Eliminar simulación" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/activa o en cola/);
    expect(screen.getByText("Comparación mezcla")).toBeInTheDocument();
  });

  it("treats a 404 on delete as already-deleted, refreshing the list instead of showing a dead confirmation", async () => {
    vi.mocked(apiClient.listExperiments)
      .mockResolvedValueOnce(fixture)
      .mockResolvedValueOnce({ ...fixture, total: 1, items: [fixture.items[1]] });
    vi.mocked(apiClient.deleteExperiment).mockRejectedValueOnce(new ApiError(404, "resource not found"));
    const { user } = setup();

    await screen.findByText("Fríos K1");
    const row = screen.getByText("Fríos K1").closest("tr")!;
    await user.click(within(row).getByRole("button", { name: /Acciones de/ }));
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Eliminar simulación" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/ya no exist/);
    await waitFor(() => expect(screen.queryByText("Fríos K1")).not.toBeInTheDocument());
  });

  it("returns focus to the origin control when the confirmation is cancelled", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { user } = setup();

    await screen.findByText("Fríos K1");
    const row = screen.getByText("Fríos K1").closest("tr")!;
    const trigger = within(row).getByRole("button", { name: /Acciones de/ });
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    await screen.findByRole("alertdialog");

    await user.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
