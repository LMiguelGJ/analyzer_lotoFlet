import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import experimentsPage from "../../api/__fixtures__/experiments-page.json";
import type { Page } from "../../api/types";
import type { ExperimentSummary } from "../../api/types";

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

const fixture = experimentsPage as Page<ExperimentSummary>;

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

    expect(screen.getByRole("status", { name: "" }) || screen.getByText(/Cargando experimentos/)).toBeTruthy();
    resolvePage(fixture);
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
  });

  it("shows first-run guidance when there are zero experiments", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(emptyPage());
    setup();

    expect(await screen.findByText(/Todavía no hay experimentos/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Creá el primero" })).toHaveAttribute("href", "/experimentos/nuevo");
  });

  it("shows a disconnected state with NetworkError wording, never claiming the server stopped, and retries", async () => {
    vi.mocked(apiClient.listExperiments)
      .mockRejectedValueOnce(new NetworkError())
      .mockResolvedValueOnce(fixture);
    const { user } = setup();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/No se pudo contactar al servidor local/);
    expect(alert.textContent ?? "").not.toMatch(/detuvo|detenido|se detuvo/i);

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

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Fríos K1")).toBeInTheDocument();
  });

  it("shows a no-matches state from the server, distinct from the empty state", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture).mockResolvedValueOnce(emptyPage());
    const { user } = setup();
    await screen.findByText("Fríos K1");

    await user.type(screen.getByLabelText("Buscar por nombre"), "no-existe-esto");
    expect(await screen.findByText(/Sin coincidencias/)).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay experimentos/)).not.toBeInTheDocument();
  });
});

describe("LW10 experiments list · data and navigation", () => {
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

    expect(screen.getByRole("columnheader", { name: "Estrategias" })).toHaveClass("table-numeric");
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
    expect(screen.getByRole("region", { name: "Experimentos" })).toHaveClass("overflow-x-auto");
  });

  it("uses StatusLabel for execution status, never the session outcome vocabulary", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();

    await screen.findByText("Fríos K1");
    const table = screen.getByRole("table");
    const completedStatus = within(table).getByText("Ejecución completada");
    expect(completedStatus.closest("span")).toHaveAttribute("data-status-kind", "execution");
    expect(within(table).getByText("En curso")).toBeInTheDocument();
    // The outcome vocabulary ("Meta alcanzada") must not appear as if it were the execution status.
    expect(screen.queryByText("Meta alcanzada")).not.toBeInTheDocument();
  });

  it("links the primary action to the wizard and each row name to its stable detail URL", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    setup();

    expect(screen.getByRole("link", { name: "Nuevo experimento" })).toHaveAttribute(
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
    await user.selectOptions(screen.getByLabelText("Estado de ejecución"), "completed");
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
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar experimento" }));
    await waitFor(() => expect(router.state.location.search).not.toContain("page=2"));
    expect(apiClient.listExperiments).toHaveBeenCalledWith({ offset: 0, limit: 20, sort: "created_at", order: "desc" });
  });

  it("has no axe violations in the ready state", async () => {
    vi.mocked(apiClient.listExperiments).mockResolvedValueOnce(fixture);
    const { container } = setup();

    await screen.findByText("Fríos K1");
    expect(await axe(container)).toHaveNoViolations();
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
    expect(dialog).toHaveAccessibleName("¿Eliminar el experimento «Fríos K1»?");
    expect(dialog).toHaveTextContent(/forma permanente/);
    await user.click(within(dialog).getByRole("button", { name: "Eliminar experimento" }));

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
    await user.click(within(dialog).getByRole("button", { name: "Eliminar experimento" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/activo o en cola/);
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
    await user.click(within(dialog).getByRole("button", { name: "Eliminar experimento" }));

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
