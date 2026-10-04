import { readFileSync } from "node:fs";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getCatalog: vi.fn(), listConfigurations: vi.fn(), getConfiguration: vi.fn(), createConfiguration: vi.fn(), updateConfiguration: vi.fn(), deleteConfiguration: vi.fn() } };
});
const strategy = { name: "Fríos", selector: "system" as const, system: "cold", coverage: 1, staking: "flat" as const };
const item = { id: "cfg-1", name: "Mi plantilla", strategy };
const catalog = { systems: { cold: "Fríos", transition: "Transición" }, selectors: ["system", "blend", "random", "parity"], coverages: [1, 5, 50], parity_coverage: 50 };
function setup() {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/configuraciones"] });
  return { user: userEvent.setup(), router, ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  vi.mocked(apiClient.getCatalog).mockReset().mockResolvedValue(catalog as never);
  vi.mocked(apiClient.listConfigurations).mockReset().mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [item] });
  vi.mocked(apiClient.getConfiguration).mockReset().mockResolvedValue(item);
  vi.mocked(apiClient.createConfiguration).mockReset().mockResolvedValue(item);
  vi.mocked(apiClient.updateConfiguration).mockReset().mockResolvedValue(item);
  vi.mocked(apiClient.deleteConfiguration).mockReset().mockResolvedValue();
});
it("frames saved strategies as an optional reusable library", async () => {
  const { user } = setup();
  expect(await screen.findByRole("heading", { name: "Estrategias" })).toBeInTheDocument();
  expect(screen.getByText("Guardá un método para reutilizarlo.")).toBeInTheDocument();
  const use = screen.getByRole("link", { name: /Usar/ });
  expect(use).toHaveClass("btn-secondary");
  expect(screen.getByRole("button", { name: /Editar/ })).toHaveClass("btn-tertiary");
  expect(screen.getByRole("button", { name: /Eliminar/ })).toHaveClass("btn-tertiary");
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

it("shows empty, disconnected and retry states honestly", async () => {
  vi.mocked(apiClient.listConfigurations).mockRejectedValueOnce(new NetworkError()).mockResolvedValueOnce({ total: 0, offset: 0, limit: 20, items: [] });
  const { user } = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(/contactar al servidor/);
  await user.click(screen.getByRole("button", { name: "Volver a cargar las estrategias guardadas" }));
  expect(await screen.findByText("La biblioteca es opcional; guardá un método para reutilizarlo.")).toBeInTheDocument();
});
it("distinguishes recovery for the catalog and saved strategies", async () => {
  vi.mocked(apiClient.getCatalog).mockRejectedValueOnce(new NetworkError());
  vi.mocked(apiClient.listConfigurations).mockRejectedValueOnce(new NetworkError());
  const { user } = setup();
  expect(await screen.findByText(/necesitan este catálogo/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Volver a cargar el catálogo" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Volver a cargar el catálogo" }));
  await waitFor(() => expect(apiClient.getCatalog).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("button", { name: "Volver a cargar el catálogo" })).not.toBeInTheDocument();
});
it("keeps page-local search distinct from an empty library", async () => {
  const { user } = setup();
  await screen.findByText("Mi plantilla");
  const search = screen.getByRole("textbox", { name: "Buscar estrategia guardada" });
  await user.type(search, "sin coincidencia");
  expect(screen.getByRole("status")).toHaveTextContent(/No hay estrategias con ese nombre/);
  expect(screen.queryByText(/Todavía no hay estrategias guardadas/)).not.toBeInTheDocument();
  expect(apiClient.listConfigurations).toHaveBeenCalledWith(0, 20);
  expect(apiClient.listConfigurations).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("button", { name: "Mostrar todas las estrategias de esta página" }));
  expect(search).toHaveValue("");
  expect(screen.getByText("Mi plantilla")).toBeInTheDocument();
});
it("hides search and pagination while the library is empty", async () => {
  vi.mocked(apiClient.listConfigurations).mockResolvedValueOnce({ total: 0, offset: 0, limit: 20, items: [] });
  setup();
  expect(await screen.findByText("La biblioteca es opcional; guardá un método para reutilizarlo.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Crear estrategia guardada" })).toBeVisible();
  expect(screen.queryByRole("textbox", { name: "Buscar estrategia guardada" })).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Páginas de estrategias guardadas" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Crear estrategia guardada" })).toBeInTheDocument();
});

it("does not discard a dirty edit on cancel or navigation without confirmation", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  const { user, router } = setup();
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: /Editar/ }));
  await user.type(screen.getByRole("textbox", { name: "Nombre guardado" }), " editada");
  await user.click(screen.getByRole("button", { name: "Cancelar edición" }));
  expect(screen.getByRole("textbox", { name: "Nombre guardado" })).toHaveValue("Mi plantilla editada");
  await user.click(screen.getByRole("link", { name: "Ajustes" }));
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/configuraciones");
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Seguir editando" }));
  expect(screen.getByRole("textbox", { name: "Nombre guardado" })).toHaveValue("Mi plantilla editada");
  confirm.mockRestore();
});
it("keeps saved data and actions in DOM order with a full-width data row and wrapping actions", async () => {
  setup();
  const template = await screen.findByText("Mi plantilla");
  const row = template.closest("li")!;
  expect(row).toHaveClass("saved-strategy-row");
  expect(within(row).getAllByRole("link")).toHaveLength(1);
  expect(within(row).getAllByRole("button").map((button) => button.textContent)).toEqual(["Editar Mi plantilla", "Eliminar Mi plantilla"]);
  expect(within(row).getAllByRole("button").every((button) => button.classList.contains("btn-tertiary"))).toBe(true);
  const css = readFileSync("src/styles/index.css", "utf8");
  expect(css).toMatch(/\.saved-strategy-row\s*\{[^}]*grid-template-columns:\s*minmax\(0, 1fr\);/s);
  expect(css).toMatch(/\.saved-strategy-row \.btn\s*\{[^}]*max-width:\s*100%;/s);
});

it("lists a bounded page, offers use and edit, and preserves distinct library and strategy names", async () => {
  const { user } = setup();
  expect(await screen.findByText("Mi plantilla")).toBeInTheDocument();
  expect(apiClient.listConfigurations).toHaveBeenCalledWith(0, 20);
  expect(screen.getByRole("link", { name: /Usar/ })).toHaveAttribute("href", "/experimentos/nuevo?configuration=cfg-1");
  expect(screen.getByText("Un sistema de selección")).toBeInTheDocument();
  expect(document.querySelectorAll(".btn-primary")).toHaveLength(1);
  expect(screen.getByText("Plana")).toBeInTheDocument();
  expect(screen.getByText("Fríos", { selector: "dd" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Editar/ }));
  const templateName = screen.getByRole("textbox", { name: "Nombre guardado" });
  expect(templateName).toHaveValue("Mi plantilla");
  expect(templateName).toHaveAccessibleName("Nombre guardado");
  expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Fríos");
  await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
  await waitFor(() => expect(apiClient.updateConfiguration).toHaveBeenCalledWith("cfg-1", "Mi plantilla", strategy));
});
it("rejects invalid drafts locally and maps server 422 fields without losing the draft", async () => {
  const { user } = setup();
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: "Nueva estrategia guardada" }));
  await user.click(screen.getByRole("button", { name: "Guardar estrategia" }));
  expect(apiClient.createConfiguration).not.toHaveBeenCalled();
  await user.type(screen.getByRole("textbox", { name: "Nombre guardado" }), "Nueva biblioteca");
  await user.type(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" }), "Otra");
  await user.selectOptions(screen.getByRole("combobox", { name: "Sistema de ranking" }), "cold");
  vi.mocked(apiClient.createConfiguration).mockRejectedValueOnce(new ApiError(422, "invalid", [{ loc: ["body", "strategy", "name"], msg: "server detail", type: "value_error" }]));
  await user.click(screen.getByRole("button", { name: "Guardar estrategia" }));
  expect(await screen.findByText("server detail")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveValue("Otra");
  expect(screen.getByRole("textbox", { name: "Nombre de la estrategia 1" })).toHaveAttribute("aria-invalid", "true");
});
it("prevents a second save and changes during an in-flight request", async () => {
  let resolveSave!: (value: typeof item) => void;
  vi.mocked(apiClient.updateConfiguration).mockReturnValueOnce(new Promise((resolve) => { resolveSave = resolve; }));
  const { user } = setup();
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: /Editar/ }));
  await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
  expect(screen.getByRole("button", { name: "Guardar cambios" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Nombre guardado" })).toBeDisabled();
  expect(apiClient.updateConfiguration).toHaveBeenCalledTimes(1);
  resolveSave(item);
  expect(await screen.findByRole("status")).toHaveTextContent(/actualizada/);
});
it("deletes only after confirmation with exact ID; missing row refreshes, and network failure stays visible", async () => {
  const { user } = setup();
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveAccessibleName("¿Eliminar la estrategia guardada «Mi plantilla»?");
  expect(dialog).toHaveTextContent(/resultados de experimentos anteriores se conservan/);
  await user.keyboard("{Escape}");
  expect(apiClient.deleteConfiguration).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: /Eliminar Mi plantilla/ })).toHaveFocus();
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  vi.mocked(apiClient.deleteConfiguration).mockRejectedValueOnce(new NetworkError());
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar estrategia guardada" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Sin respuesta del servidor/);
  expect(screen.queryByText(/Estrategia guardada eliminada/)).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  vi.mocked(apiClient.deleteConfiguration).mockRejectedValueOnce(new ApiError(404, "missing"));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar estrategia guardada" }));
  await waitFor(() => expect(apiClient.deleteConfiguration).toHaveBeenLastCalledWith("cfg-1", "cfg-1"));
  expect(screen.queryByText(/Estrategia guardada eliminada/)).not.toBeInTheDocument();
});
it("keeps focus on the success status after the deleted row is removed asynchronously", async () => {
  let resolveReload!: (value: { total: number; offset: number; limit: number; items: typeof item[] }) => void;
  vi.mocked(apiClient.listConfigurations).mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [item] })
    .mockImplementationOnce(() => new Promise((resolve) => { resolveReload = resolve; }));
  const { user } = setup();
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar estrategia guardada" }));
  const status = await screen.findByText("Estrategia eliminada. Los resultados se conservan.");
  expect(status).toHaveAttribute("role", "status");
  expect(status).toHaveFocus();
  await waitFor(() => expect(apiClient.listConfigurations).toHaveBeenCalledTimes(2));
  resolveReload({ total: 0, offset: 0, limit: 20, items: [] });
  expect(await screen.findByText("La biblioteca es opcional; guardá un método para reutilizarlo.")).toBeInTheDocument();
  expect(screen.queryByText("Mi plantilla")).not.toBeInTheDocument();
  expect(status).toHaveFocus();
  expect(document.activeElement).not.toBe(document.body);
});
it("keeps success focus through asynchronous last-page recovery after deletion", async () => {
  let resolveEmpty!: (value: { total: number; offset: number; limit: number; items: typeof item[] }) => void;
  let resolvePrevious!: (value: { total: number; offset: number; limit: number; items: typeof item[] }) => void;
  const survivor = { ...item, id: "cfg-survivor", name: "Plantilla anterior" };
  vi.mocked(apiClient.listConfigurations).mockResolvedValueOnce({ total: 21, offset: 0, limit: 20, items: [survivor] })
    .mockResolvedValueOnce({ total: 21, offset: 20, limit: 20, items: [item] })
    .mockImplementationOnce(() => new Promise((resolve) => { resolveEmpty = resolve; }))
    .mockImplementationOnce(() => new Promise((resolve) => { resolvePrevious = resolve; }));
  const { user } = setup();
  await screen.findByText("Plantilla anterior");
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByText("Mi plantilla");
  await user.click(screen.getByRole("button", { name: /Eliminar/ }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar estrategia guardada" }));
  const status = await screen.findByText("Estrategia eliminada. Los resultados se conservan.");
  expect(status).toHaveFocus();
  await waitFor(() => expect(apiClient.listConfigurations).toHaveBeenCalledWith(20, 20));
  resolveEmpty({ total: 20, offset: 20, limit: 20, items: [] });
  await waitFor(() => expect(apiClient.listConfigurations).toHaveBeenCalledWith(0, 20));
  resolvePrevious({ total: 20, offset: 0, limit: 20, items: [survivor] });
  expect(await screen.findByText("Plantilla anterior")).toBeInTheDocument();
  expect(screen.getByText("Página 1 · 20 en total")).toBeInTheDocument();
  expect(status).toHaveFocus();
  expect(document.activeElement).not.toBe(document.body);
});
