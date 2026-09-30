import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { SettingsView } from "../../api/types";
import fixture from "../../api/__fixtures__/settings.json";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getSettings: vi.fn(), updateSettings: vi.fn() } };
});
const base = fixture as SettingsView;
function setup() {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/ajustes"] });
  return { user: userEvent.setup(), router, ...render(<RouterProvider router={router} />) };
}
beforeEach(() => {
  vi.mocked(apiClient.getSettings).mockReset().mockResolvedValue(base);
  vi.mocked(apiClient.updateSettings).mockReset().mockResolvedValue(base);
});

it("loads the actual view, distinguishing logical quota, physical files and free disk", async () => {
  let resolve!: (view: SettingsView) => void;
  vi.mocked(apiClient.getSettings).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  setup();
  expect(screen.getByRole("status")).toHaveTextContent(/Cargando ajustes/);
  resolve(base);
  expect(await screen.findByText(/Uso lógico/)).toBeInTheDocument();
  expect(screen.getByText("5 GiB (5.368.709.120 bytes)")).toBeInTheDocument();
  expect(screen.getByText(/SQLite y archivos locales \(total informado\)/)).toBeInTheDocument();
  expect(screen.getByText("Espacio en disco libre")).toBeInTheDocument();
  expect(screen.getByText(/JSON y rankings originales no se incluyen/i)).toBeInTheDocument();
  expect(screen.getByText(/borrar registros no garantiza reducir/i)).toBeInTheDocument();
  expect(screen.getByText(/próxima admisión o escritura/i)).toBeInTheDocument();
  expect(screen.getByText(/lanzador.*LW16/i)).toBeInTheDocument();
  expect(screen.getByText("chance_express_history.json")).toBeInTheDocument();
  expect(screen.getByText("127.0.0.1:8765")).toBeInTheDocument();
  expect(screen.getByText(/Por defecto/)).toBeInTheDocument();
});

it("distinguishes disconnected from generic errors and retries", async () => {
  vi.mocked(apiClient.getSettings).mockRejectedValueOnce(new NetworkError()).mockRejectedValueOnce(new ApiError(500, "oops")).mockResolvedValueOnce(base);
  const { user } = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo contactar al servidor local/);
  await user.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudieron cargar los ajustes/);
  await user.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByText(/Uso lógico/)).toBeInTheDocument();
});

it.each(["", "0", "01", " 5", "+5", "-1", "1.5", "1e3", "９", "9223372036854775808"])("rejects invalid byte input %j with focus and no PUT", async (value) => {
  const { user } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(input);
  if (value) await user.type(input, value);
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText(/Ingresá un entero decimal ASCII/)).toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("sends max int64 exactly as a string, disables duplicate saving, then trusts the full PUT response", async () => {
  let resolve!: (view: SettingsView) => void;
  vi.mocked(apiClient.updateSettings).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const { user } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(input);
  await user.type(input, "9223372036854775807");
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(apiClient.updateSettings).toHaveBeenCalledWith("9223372036854775807");
  expect(screen.getByRole("button", { name: /Guardando/ })).toBeDisabled();
  expect(input).toBeDisabled();
  expect(apiClient.updateSettings).toHaveBeenCalledTimes(1);
  resolve({ ...base, quota: { effective_bytes: "8000000000000000000", persisted_bytes: "8000000000000000000", source: "persisted", writable: true }, storage: { ...base.storage, limit_bytes: 8000000000000000000 } });
  expect((await screen.findAllByText(/8.000.000.000.000.000.000 bytes/)).length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText(/Guardado/)).toBeInTheDocument();
  expect(input).toHaveValue("8000000000000000000");
});

it("keeps the draft after 422, 409 below usage, and network failure; 422 focuses the field", async () => {
  vi.mocked(apiClient.updateSettings)
    .mockRejectedValueOnce(new ApiError(422, "invalid", [{ loc: ["body", "quota_bytes"], type: "value_error", msg: "server rejected" }]))
    .mockRejectedValueOnce(new ApiError(409, "quota cannot be below current logical usage"))
    .mockRejectedValueOnce(new NetworkError());
  const { user } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(input); await user.type(input, "500");
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(await screen.findByText(/El servidor rechazó el presupuesto/)).toBeInTheDocument();
  expect(input).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/menor que el uso lógico actual/);
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/podría haber llegado/);
  expect(input).toHaveValue("500");
});

it("shows an environment quota as read-only, with persisted preference distinct", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({ ...base, quota: { effective_bytes: "9007199254740993", persisted_bytes: "2147483648", source: "environment", writable: false } });
  setup();
  expect(await screen.findByText(/Variable de entorno/)).toBeInTheDocument();
  expect(screen.getByText(/2.147.483.648 bytes/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Guardar presupuesto" })).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /Presupuesto en bytes/ })).not.toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("warns on the server's quota warning without confusing it with disk reclamation", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({ ...base, storage: { ...base.storage, warning: true, logical_used_bytes_exact: "9007199254740993" } });
  setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(/límite o falta de disco/);
  expect(screen.getByText(/9.007.199.254.740.993 bytes/)).toBeInTheDocument();
});

it("guards dirty navigation and unload while a refresh keeps the draft across server changes", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(base).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "6000000000", persisted_bytes: "6000000000", source: "persisted", writable: true },
  });
  const add = vi.spyOn(window, "addEventListener");
  const { user, router } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(input); await user.type(input, "7000000000");
  expect(add.mock.calls.some(([name]) => name === "beforeunload")).toBe(true);
  await user.click(screen.getByRole("button", { name: "Actualizar estado" }));
  await waitFor(() => expect(apiClient.getSettings).toHaveBeenCalledTimes(2));
  expect((await screen.findAllByText(/6.000.000.000 bytes/)).length).toBeGreaterThanOrEqual(2);
  expect(input).toHaveValue("7000000000");
  await user.click(screen.getByRole("link", { name: "Experimentos" }));
  expect(router.state.location.pathname).toBe("/ajustes");
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Seguir editando" }));
  expect(input).toHaveValue("7000000000");
  await user.click(screen.getByRole("link", { name: "Experimentos" }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  add.mockRestore();
});

it("preserves an unsaved draft when a refresh changes quota to environment read-only", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(base).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "6000000000", persisted_bytes: null, source: "environment", writable: false },
  });
  const { user, router } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(input); await user.type(input, "7000000000");
  await user.click(screen.getByRole("button", { name: "Actualizar estado" }));
  expect(await screen.findByText(/Borrador no guardado:/)).toHaveTextContent("7000000000");
  expect(screen.queryByRole("button", { name: "Guardar presupuesto" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Experimentos" }));
  expect(router.state.location.pathname).toBe("/ajustes");
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

it("does not block clean navigation and explains 403 and a raced read-only 409 without losing the draft", async () => {
  const { user, router } = setup();
  const input = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.click(screen.getByRole("link", { name: "Experimentos" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Ajustes" }));
  const edited = await screen.findByRole("textbox", { name: /Presupuesto en bytes/ });
  await user.clear(edited); await user.type(edited, "7000000000");
  vi.mocked(apiClient.updateSettings).mockRejectedValueOnce(new ApiError(403, "forbidden")).mockRejectedValueOnce(new ApiError(409, "environment quota is read-only"));
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/origen de la solicitud/);
  await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/variable de entorno tiene prioridad/);
  expect(edited).toHaveValue("7000000000");
  expect(input).not.toBeInTheDocument();
});

it("has no axe violations in loaded settings", async () => {
  const { container } = setup();
  await screen.findByText(/Uso lógico/);
  expect(await axe(container)).toHaveNoViolations();
});
