import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
// Contract coverage: F-LIST-064–F-LIST-080 — capacity-first display, honest errors, exact ASCII int64 quota input/save, read-only environment mode, aggregate capacity math, dirty navigation, explicit secret retrieval/copy/clearing/unmount safety, and axe. Additional game-rules editor tests are retained as stricter legacy coverage (contract gap recorded).
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { GameSettings, SettingsView } from "../../api/types";
import fixture from "../../api/__fixtures__/settings.json";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getSettings: vi.fn(), updateSettings: vi.fn(), getAgentCredential: vi.fn(), getGameSettings: vi.fn(), saveGameSettings: vi.fn() } };
});
const agentApi = apiClient as typeof apiClient & {
  getAgentCredential: () => Promise<{ token: string }>;
};
let originalClipboard: PropertyDescriptor | undefined;
const base: SettingsView = {
  ...fixture,
  storage: {
    ...fixture.storage,
    profile_artifact_bytes: 512,
    profile_artifact_bytes_exact: "512",
    dataset_artifact_bytes_exact: "0",
    admission_logical_bytes_exact: "1536",
  },
  quota: { ...fixture.quota, source: "default" },
};
const storedGame: GameSettings = {
  name: "Quiniela 80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1],
  allows_repeats: true, minimum_stake: 1, source: "default",
};
function setup(_options: { stayOnRules?: boolean } = {}) {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/ajustes"] });
  const user = userEvent.setup();
  const rendered = render(<RouterProvider router={router} />);
  return { user, router, ...rendered };
}
async function openQuota(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("heading", { name: "Reglas del sorteo" });
  await waitFor(() => expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("heading", { name: "Presupuesto y cuota" });
}
async function openAgentAccess(user: ReturnType<typeof userEvent.setup>) {
  await openQuota(user);
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(screen.getByText("Acceso para agentes"));
}
beforeEach(() => {
  vi.mocked(apiClient.getSettings).mockReset().mockResolvedValue(base);
  vi.mocked(apiClient.updateSettings).mockReset().mockResolvedValue(base);
  vi.mocked(agentApi.getAgentCredential).mockReset();
  vi.mocked(apiClient.getGameSettings).mockReset().mockResolvedValue(storedGame);
  vi.mocked(apiClient.saveGameSettings).mockReset().mockResolvedValue({ ...storedGame, source: "stored" });
  originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
});
afterEach(() => {
  if (originalClipboard) Object.defineProperty(navigator, "clipboard", originalClipboard);
  else Reflect.deleteProperty(navigator, "clipboard");
});

it("keeps quota and advanced settings reachable when game rules fail to load", async () => {
  vi.mocked(apiClient.getGameSettings).mockRejectedValueOnce(new Error("temporary failure"));
  const { user } = setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudieron cargar las reglas del juego/);
  expect(screen.getByRole("button", { name: "Reintentar reglas" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Presupuesto y cuota" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Detalles avanzados" })).toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("loads the actual view, distinguishing logical quota, physical files and free disk", async () => {
  let resolve!: (view: SettingsView) => void;
  vi.mocked(apiClient.getSettings).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const { user } = setup({ stayOnRules: true });
  expect(screen.getByRole("status")).toHaveTextContent(/Cargando ajustes/);
  resolve(base);
  await screen.findByRole("heading", { name: "Reglas del sorteo" });
  await waitFor(() => expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled());
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Presupuesto y cuota" })).toBeInTheDocument();
  expect(screen.getAllByText("5 GiB")).toHaveLength(2);
  expect(screen.getByText("1.5 KiB")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "0");
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  const diagnostics = screen.getByText("Detalles técnicos").closest("details")!;
  // Advanced diagnostics follow the capacity step and remain collapsed.
  expect(screen.getByRole("heading", { name: "Detalles avanzados" }).compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(document.querySelectorAll(".btn-primary")).toHaveLength(1);
  expect(diagnostics).not.toHaveAttribute("open");
  expect(within(diagnostics).getByText("Experimentos y ejecuciones históricos")).not.toBeVisible();
  await userEvent.setup().click(within(diagnostics).getByText("Detalles técnicos"));
  expect(screen.getByText("Experimentos y ejecuciones históricos")).toBeInTheDocument();
  expect(screen.getByText("Artefactos de perfiles (copias JSON)")).toBeInTheDocument();
  expect(screen.getByText("Artefactos de datasets")).toBeInTheDocument();
  expect(screen.getByText("5,368,709,120 bytes")).toBeInTheDocument();
  expect(screen.getByText("1,536 bytes")).toBeInTheDocument();
  expect(screen.getByText("512 bytes")).toBeInTheDocument();
  expect(within(screen.getByText("Artefactos de datasets").parentElement!).getByText("0 bytes")).toBeInTheDocument();
  expect(screen.getByText(/SQLite y archivos locales \(total informado\)/)).toBeInTheDocument();
  expect(screen.getByText("Espacio en disco libre")).toBeInTheDocument();
  expect(screen.getByText(/El límite de almacenamiento no es el espacio libre en disco/)).toBeInTheDocument();
  expect(screen.getByText("iniciar-laboratorio.bat")).toBeInTheDocument();
  expect(screen.getByText(/Ctrl\+C en su consola/)).toBeInTheDocument();
  expect(screen.queryByText(/LW16/)).not.toBeInTheDocument();
  expect(screen.getByText("chance_express_history.json")).toBeInTheDocument();
  expect(screen.getByText("127.0.0.1:8765")).toBeInTheDocument();
  expect(within(diagnostics).getByText("Por defecto")).toBeInTheDocument();
});

it("offers a quota edit path from review and keeps the save outcome visible", async () => {
  const { user } = setup();
  await openQuota(user);
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("heading", { name: "Detalles avanzados" });
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Revisá tus ajustes" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Editar cuota" }));
  expect(await screen.findByRole("heading", { name: "Presupuesto y cuota" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByRole("heading", { name: "Revisá tus ajustes" });
  await user.click(screen.getByRole("button", { name: "Guardar ajustes" }));
  expect(await screen.findByRole("status")).toHaveTextContent(/Ajustes guardados/);
  expect(screen.getByRole("link", { name: "Crear una simulación" })).toHaveAttribute("href", "/experimentos/nuevo");
});

it("distinguishes disconnected from generic errors and retries", async () => {
  vi.mocked(apiClient.getSettings).mockRejectedValueOnce(new NetworkError()).mockRejectedValueOnce(new ApiError(500, "oops")).mockResolvedValueOnce(base);
  const { user } = setup();
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent(/No se pudo contactar al servidor/);
  expect(banner).toHaveTextContent(/Comprobá que el laboratorio siga abierto y reintentá/);
  expect(banner).not.toHaveTextContent(/Tu información se conserva/);
  await user.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudieron cargar los ajustes/);
  await user.click(screen.getByRole("button", { name: "Reintentar" }));
  await openQuota(user);
  expect(await screen.findByRole("heading", { name: "Presupuesto y cuota" })).toBeInTheDocument();
});

it.each(["", "0", "01", " 5", "+5", "-1", "1.5", "1e3", "９", "9223372036854775808"])("rejects invalid byte input %j with focus and no PUT", async (value) => {
  const { user } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input);
  if (value) await user.type(input, value);
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText(/Ingresá un entero en bytes/, { selector: "#quota-error" })).toBeInTheDocument();
  expect(input).toHaveAccessibleDescription(/Entero positivo.*Mínimo.*Ingresá un entero en bytes/s);
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("sends max int64 exactly as a string, disables duplicate saving, then trusts the full PUT response", async () => {
  let resolve!: (view: SettingsView) => void;
  vi.mocked(apiClient.updateSettings).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const { user } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input);
  expect(input).toHaveAccessibleDescription(/Entero positivo.*Mínimo 1.5 KiB \(1,536 bytes\)/i);
  await user.type(input, "9223372036854775807");
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(apiClient.updateSettings).toHaveBeenCalledWith("9223372036854775807");
  expect(screen.getByRole("button", { name: /Guardando/ })).toBeDisabled();
  expect(input).toBeDisabled();
  expect(apiClient.updateSettings).toHaveBeenCalledTimes(1);
  resolve({ ...base, quota: { effective_bytes: "8000000000000000000", persisted_bytes: "8000000000000000000", source: "persisted", writable: true }, storage: { ...base.storage, limit_bytes: 8000000000000000000 } });
  expect((await screen.findAllByText(/8,000,000,000,000,000,000 bytes/)).length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText(/Guardado/)).toBeInTheDocument();
  expect(input).toHaveValue("8000000000000000000");
});

it("keeps the draft after 422, 409 below usage, and network failure; 422 focuses the field", async () => {
  vi.mocked(apiClient.updateSettings)
    .mockRejectedValueOnce(new ApiError(422, "invalid", [{ loc: ["body", "quota_bytes"], type: "value_error", msg: "server rejected" }]))
    .mockRejectedValueOnce(new ApiError(409, "quota cannot be below current logical usage"))
    .mockRejectedValueOnce(new NetworkError());
  const { user } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input); await user.type(input, "2000");
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(await screen.findByText(/El servidor rechazó el límite/)).toBeInTheDocument();
  expect(input).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/El límite no puede ser menor que el uso actual/);
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/Puede que se haya guardado/);
  expect(input).toHaveValue("2000");
});

it("shows an environment quota as read-only, with persisted preference distinct", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({ ...base, quota: { effective_bytes: "9007199254740993", persisted_bytes: "2147483648", source: "environment", writable: false } });
  const { user } = setup();
  await openQuota(user);
  expect(await screen.findByText(/El límite lo fija el servidor/)).toBeInTheDocument();
  expect(screen.getByText("1.5 KiB")).toBeInTheDocument();
  expect(screen.getByText(/2,147,483,648 bytes/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Guardar límite" })).not.toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /Nuevo límite de almacenamiento/ })).not.toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("presents max int64 and aggregate usage exactly with es-DO grouping while keeping raw ASCII input", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({
    ...base,
    quota: { effective_bytes: "9223372036854775807", persisted_bytes: null, source: "default", writable: true },
    storage: { ...base.storage, logical_used_bytes_exact: "9007199254740993", profile_artifact_bytes_exact: "7", admission_logical_bytes_exact: "9007199254741000" },
  });
  const { user } = setup();
  await openQuota(user);
  const capacity = (await screen.findByRole("heading", { name: "Presupuesto y cuota" })).closest("section")!;
  expect(within(capacity).getByText("8,388,608 TiB")).toBeInTheDocument();
  expect(within(capacity).getByText("8,192 TiB")).toBeInTheDocument();
  expect(capacity.textContent).not.toMatch(/bytes|SHA-256|JSON/);
  const details = screen.getByText("Detalles técnicos").closest("details")!;
  await user.click(within(details).getByText("Detalles técnicos"));
  expect(screen.getByText("9,223,372,036,854,775,807 bytes")).toBeInTheDocument();
  expect(screen.getByText("9,007,199,254,741,000 bytes")).toBeInTheDocument();
  expect(screen.getByText("9,214,364,837,600,034,807 bytes")).toBeInTheDocument();
  expect(screen.getByText("9,007,199,254,740,993 bytes")).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: /Nuevo límite de almacenamiento/ })).toHaveValue("9223372036854775807");
});

it("rejects a quota above historical bytes but below aggregate admission usage, then allows equality", async () => {
  const { user } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input); await user.type(input, "1500");
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText(/Mínimo 1.5 KiB \(1,536 bytes\)/)).toBeInTheDocument();
  expect(screen.getByText(/no puede ser menor que el uso actual.*1,536 bytes/, { selector: "#quota-error" })).toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
  await user.clear(input); await user.type(input, "1536");
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(apiClient.updateSettings).toHaveBeenCalledWith("1536");
  expect(screen.queryByText(/no puede ser menor/, { selector: "#quota-error" })).not.toBeInTheDocument();
});

it("shows exact remaining capacity and bounded progress from aggregate usage", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "2560", persisted_bytes: "2560", source: "persisted", writable: true },
  });
  const { user } = setup();
  await openQuota(user);
  expect(await screen.findByText("1 KiB", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "60");
});

it("clamps remaining and progress when aggregate usage exceeds the effective limit", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "1200", persisted_bytes: "1200", source: "persisted", writable: true },
  });
  const { user } = setup();
  await openQuota(user);
  expect(await screen.findByText("0 bytes", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByText(/Uso superior al límite por 336 bytes/)).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "100");
});

it("marks historical-only responses as incomplete instead of claiming an aggregate", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(fixture as SettingsView);
  const { user } = setup();
  await openQuota(user);
  expect(await screen.findByText(/Uso incompleto: este servidor no informa el total/)).toBeInTheDocument();
  expect(screen.queryByRole("progressbar", { name: "Cuota lógica utilizada" })).not.toBeInTheDocument();
  expect(screen.queryByText("Artefactos de perfiles (copias JSON)")).not.toBeInTheDocument();
  const input = screen.getByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input); await user.type(input, "1023");
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
});

it("warns on the server's quota warning without confusing it with disk reclamation", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({ ...base, storage: { ...base.storage, warning: true, admission_logical_bytes_exact: "9007199254740993" } });
  const { user } = setup();
  await openQuota(user);
  expect(await screen.findByRole("alert")).toHaveTextContent(/límite o falta de disco/);
  expect(screen.getAllByText(/9,007,199,254,740,993 bytes/).length).toBeGreaterThanOrEqual(1);
});

it("guards dirty navigation and unload while a refresh keeps the draft across server changes", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(base).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "6000000000", persisted_bytes: "6000000000", source: "persisted", writable: true },
  });
  const add = vi.spyOn(window, "addEventListener");
  const { user, router } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input); await user.type(input, "7000000000");
  expect(add.mock.calls.some(([name]) => name === "beforeunload")).toBe(true);
  await user.click(screen.getByRole("button", { name: "Actualizar estado" }));
  await waitFor(() => expect(apiClient.getSettings).toHaveBeenCalledTimes(2));
  expect((await screen.findAllByText(/6,000,000,000 bytes/)).length).toBeGreaterThanOrEqual(2);
  expect(input).toHaveValue("7000000000");
  await user.click(screen.getByRole("link", { name: "Simulaciones" }));
  expect(router.state.location.pathname).toBe("/ajustes");
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Seguir editando" }));
  expect(input).toHaveValue("7000000000");
  await user.click(screen.getByRole("link", { name: "Simulaciones" }));
  await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Salir sin guardar" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  add.mockRestore();
});

it("preserves an unsaved draft when a refresh changes quota to environment read-only", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(base).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "6000000000", persisted_bytes: null, source: "environment", writable: false },
  });
  const { user, router } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(input); await user.type(input, "7000000000");
  await user.click(screen.getByRole("button", { name: "Actualizar estado" }));
  expect(await screen.findByText(/Borrador no guardado:/)).toHaveTextContent("7000000000");
  expect(screen.queryByRole("button", { name: "Guardar límite" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Simulaciones" }));
  expect(router.state.location.pathname).toBe("/ajustes");
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
});

it("does not block clean navigation and explains 403 and a raced read-only 409 without losing the draft", async () => {
  const { user, router } = setup();
  await openQuota(user);
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.click(screen.getByRole("link", { name: "Simulaciones" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Ajustes" }));
  await openQuota(user);
  const edited = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.clear(edited); await user.type(edited, "7000000000");
  vi.mocked(apiClient.updateSettings).mockRejectedValueOnce(new ApiError(403, "forbidden")).mockRejectedValueOnce(new ApiError(409, "environment quota is read-only"));
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/El servidor rechazó el origen/);
  await user.click(screen.getByRole("button", { name: "Guardar límite" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/El entorno fija el límite y no se puede cambiar desde la web/);
  expect(edited).toHaveValue("7000000000");
  expect(input).not.toBeInTheDocument();
});

it("keeps agent access closed, secret-free, and retrieves a credential only after explicit request", async () => {
  const { user } = setup();
  expect(await screen.findByRole("heading", { name: "Ajustes" })).toBeInTheDocument();
  expect(agentApi.getAgentCredential).not.toHaveBeenCalled();
  await openQuota(user);
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  const access = screen.getByText("Acceso para agentes").closest("details")!;
  expect(access).not.toHaveAttribute("open");
  expect(screen.queryByLabelText("Credencial de agente")).not.toBeInTheDocument();
  const warning = within(access).getByText("No compartas esta credencial de acceso a la API.");
  expect(warning).not.toBeVisible();
  await user.click(within(access).getByText("Acceso para agentes"));
  expect(warning).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Consultar credencial de agente" }));
  expect(agentApi.getAgentCredential).toHaveBeenCalledTimes(1);
});

it("keeps a retrieved token masked until revealed and copies only on explicit action", async () => {
  const token = "test-only-agent-token";
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.mocked(agentApi.getAgentCredential).mockResolvedValueOnce({ token });
  const { user } = setup();
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  await openAgentAccess(user);
  await user.click(await screen.findByRole("button", { name: "Consultar credencial de agente" }));
  const input = await screen.findByLabelText("Credencial de agente");
  expect(input).toHaveValue(token);
  expect(input).toHaveAttribute("type", "password");
  expect(writeText).not.toHaveBeenCalled();
  expect(localStorage.getItem("agent-token")).toBeNull();
  expect(sessionStorage.getItem("agent-token")).toBeNull();

  await user.click(screen.getByRole("button", { name: "Mostrar credencial" }));
  expect(input).toHaveAttribute("type", "text");
  await user.click(screen.getByRole("button", { name: "Ocultar credencial" }));
  expect(input).toHaveAttribute("type", "password");
  expect(navigator.clipboard.writeText).toBe(writeText);
  const copyButton = screen.getByRole("button", { name: "Copiar credencial" });
  expect(copyButton).not.toBeDisabled();
  await user.click(copyButton);
  await waitFor(() => expect(writeText).toHaveBeenCalledWith(token));
  expect(await screen.findByRole("status")).toHaveTextContent("Credencial copiada al portapapeles");
  expect(screen.getByRole("status").textContent).not.toContain(token);
  await user.click(screen.getByRole("button", { name: "Ocultar y borrar credencial" }));
  expect(screen.queryByLabelText("Credencial de agente")).not.toBeInTheDocument();
});

it("explains clipboard denial and reveals/selects the token for manual copy", async () => {
  const token = "manual-copy-agent-token";
  const writeText = vi.fn().mockRejectedValue(new Error("permission denied"));
  vi.mocked(agentApi.getAgentCredential).mockResolvedValueOnce({ token });
  const { user } = setup();
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
  await openAgentAccess(user);
  await user.click(await screen.findByRole("button", { name: "Consultar credencial de agente" }));
  await user.click(screen.getByRole("button", { name: "Copiar credencial" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/seleccioná y copiá el texto mostrado manualmente/i);
  const input = screen.getByLabelText("Credencial de agente");
  await waitFor(() => {
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveFocus();
    expect(input).toHaveProperty("selectionStart", 0);
    expect(input).toHaveProperty("selectionEnd", token.length);
  });
});

it("ignores credential responses dismissed while pending", async () => {
  let resolve!: (value: { token: string }) => void;
  vi.mocked(agentApi.getAgentCredential).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const { user } = setup();
  await openAgentAccess(user);
  await user.click(await screen.findByRole("button", { name: "Consultar credencial de agente" }));
  expect(screen.getByRole("button", { name: "Consultando credencial…" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Cancelar" }));
  resolve({ token: "late-agent-token" });
  const trigger = await screen.findByRole("button", { name: "Consultar credencial de agente" });
  await waitFor(() => expect(trigger).toHaveFocus());
  expect(screen.queryByDisplayValue("late-agent-token")).not.toBeInTheDocument();
  expect(document.body.textContent).not.toContain("late-agent-token");
  expect(agentApi.getAgentCredential).toHaveBeenCalledTimes(1);
});

it("restores focus to credential consultation after clearing the manual-copy fallback", async () => {
  const token = "manual-copy-focus-token";
  vi.mocked(agentApi.getAgentCredential).mockResolvedValueOnce({ token });
  const { user } = setup();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockRejectedValue(new Error("permission denied")) },
  });
  await openAgentAccess(user);
  await user.click(await screen.findByRole("button", { name: "Consultar credencial de agente" }));
  await user.click(screen.getByRole("button", { name: "Copiar credencial" }));
  const input = screen.getByLabelText("Credencial de agente");
  await waitFor(() => expect(input).toHaveFocus());
  expect(input).toHaveProperty("selectionEnd", token.length);
  await user.click(screen.getByRole("button", { name: "Ocultar y borrar credencial" }));
  const trigger = await screen.findByRole("button", { name: "Consultar credencial de agente" });
  await waitFor(() => expect(trigger).toHaveFocus());
  expect(screen.queryByLabelText("Credencial de agente")).not.toBeInTheDocument();
});

it("ignores a credential response after the settings screen unmounts", async () => {
  let resolve!: (value: { token: string }) => void;
  vi.mocked(agentApi.getAgentCredential).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  const { user, unmount } = setup();
  await openAgentAccess(user);
  await user.click(await screen.findByRole("button", { name: "Consultar credencial de agente" }));
  unmount();
  resolve({ token: "unmounted-agent-token" });
  await Promise.resolve();
  expect(document.body.textContent).not.toContain("unmounted-agent-token");
});

it("has no axe violations in loaded settings", async () => {
  const { container } = setup();
  await screen.findByRole("heading", { name: "Ajustes" });
  expect(await axe(container)).toHaveNoViolations();
});

// Contract coverage: F-LIST-064–F-LIST-080 remains above; these assertions cover
// the guided setup additions without weakening the established behavior checks.
it("guides settings through rules, quota, advanced details, and a review before saving", async () => {
  const { user } = setup({ stayOnRules: true });
  expect(await screen.findByRole("heading", { name: "Reglas del sorteo" })).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: /paso 1 de 4/i })).toBeInTheDocument();
  expect(screen.getByLabelText("Números posibles")).toHaveValue("100");
  expect(screen.getByLabelText("Números posibles").parentElement).toHaveTextContent(/números distintos puede elegir el sorteo/i);
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Presupuesto y cuota" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Detalles avanzados" })).toBeInTheDocument();
  expect(agentApi.getAgentCredential).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Siguiente" }));
  expect(await screen.findByRole("heading", { name: "Revisá tus ajustes" })).toBeInTheDocument();
  const review = screen.getByRole("region", { name: "Revisá tus ajustes" });
  expect(within(review).getByText(/100/)).toBeInTheDocument();
  expect(within(review).getByText(/5,368,709,120 bytes/)).toBeInTheDocument();
  expect(apiClient.updateSettings).not.toHaveBeenCalled();
  expect(apiClient.saveGameSettings).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Guardar ajustes" }));
  await waitFor(() => expect(apiClient.saveGameSettings).toHaveBeenCalledWith({
    name: "Quiniela 80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 1,
  }));
  expect(apiClient.updateSettings).toHaveBeenCalledWith(base.quota.effective_bytes);
});

it("keeps the rules step when values are invalid and prevents advancing", async () => {
  const { user } = setup({ stayOnRules: true });
  await screen.findByRole("heading", { name: "Reglas del sorteo" });
  await user.clear(screen.getByLabelText("Números posibles"));
  await user.type(screen.getByLabelText("Números posibles"), "1");
  expect(screen.getByText("Tiene que haber al menos 2 números posibles.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  expect(screen.getByRole("heading", { name: "Reglas del sorteo" })).toBeInTheDocument();
});

async function openRules(_user?: ReturnType<typeof userEvent.setup>) {
  return screen.findByRole("heading", { name: "Reglas del sorteo" });
}

it("renders the game rules form with stored values inside the Avanzado disclosure", async () => {
  vi.mocked(apiClient.getGameSettings).mockResolvedValue({
    name: "Tres", numbers: 50, positions: 3, prizes: [30, 6, 2], allows_repeats: false, minimum_stake: 5000, source: "stored",
  });
  setup({ stayOnRules: true });
  await openRules();
  expect(screen.getByRole("heading", { name: "Reglas del sorteo" })).toBeInTheDocument();
  expect(screen.getByLabelText("Nombre")).toHaveValue("Tres");
  expect(screen.getByLabelText("Números posibles")).toHaveValue("50");
  expect(screen.getByLabelText("Posiciones por sorteo")).toHaveValue("3");
  expect(screen.getByLabelText("Posición 1")).toHaveValue("30");
  expect(screen.getByLabelText("Posición 3")).toHaveValue("2");
  expect(screen.queryByLabelText("Posición 4")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Repeticiones permitidas")).not.toBeChecked();
  expect(screen.getByLabelText("Apuesta mínima por número")).toHaveValue("5000");
  expect(screen.getByText("Mínimo actual: RD$5.000.")).toBeInTheDocument();
  expect(screen.getByText("Cambiar las reglas del juego afecta las simulaciones futuras; las guardadas conservan las suyas.")).toBeInTheDocument();
  expect(document.querySelectorAll(".btn-primary")).toHaveLength(1);
  // Configuration source remains in the collapsed technical step.
  expect(screen.queryByText(/LABORATORIO_GAME/)).not.toBeInTheDocument();
  expect(screen.getByText("Guardadas desde la web")).toBeInTheDocument();
});

it("adds and removes prize inputs as positions change", async () => {
  const { user } = setup({ stayOnRules: true });
  await openRules();
  const positions = screen.getByLabelText("Posiciones por sorteo");
  await user.clear(positions); await user.type(positions, "7");
  expect(screen.getByLabelText("Posición 7")).toHaveValue("1");
  await user.clear(positions); await user.type(positions, "2");
  expect(screen.queryByLabelText("Posición 3")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Posición 2")).toHaveValue("8");
});

it("validates the rules live with inline errors and blocks saving", async () => {
  const { user } = setup({ stayOnRules: true });
  await openRules();
  const save = screen.getByRole("button", { name: "Guardar reglas" });
  const numbers = screen.getByLabelText("Números posibles");
  await user.clear(numbers); await user.type(numbers, "1");
  expect(screen.getByText("Tiene que haber al menos 2 números posibles.")).toBeInTheDocument();
  expect(save).toBeDisabled();
  await user.clear(numbers); await user.type(numbers, "3");
  await user.click(screen.getByLabelText("Repeticiones permitidas"));
  expect(screen.getByText(/Sin repeticiones, las posiciones no pueden superar/)).toBeInTheDocument();
  await user.click(screen.getByLabelText("Repeticiones permitidas"));
  expect(screen.queryByText(/Sin repeticiones/)).not.toBeInTheDocument();
  const prize = screen.getByLabelText("Posición 2");
  await user.clear(prize); await user.type(prize, "0");
  expect(screen.getByText("Mínimo 1.")).toBeInTheDocument();
  await user.clear(prize); await user.type(prize, "8");
  const stake = screen.getByLabelText("Apuesta mínima por número");
  await user.clear(stake); await user.type(stake, "0");
  expect(screen.getByText("La apuesta mínima es de al menos RD$1.")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Nombre"));
  expect(screen.getByText("Escribí un nombre de hasta 80 caracteres.")).toBeInTheDocument();
  expect(apiClient.saveGameSettings).not.toHaveBeenCalled();
});

it("saves valid rules and confirms", async () => {
  const { user } = setup({ stayOnRules: true });
  await openRules();
  const stake = screen.getByLabelText("Apuesta mínima por número");
  await user.clear(stake); await user.type(stake, "10");
  await user.click(screen.getByRole("button", { name: "Guardar reglas" }));
  await waitFor(() => expect(apiClient.saveGameSettings).toHaveBeenCalledWith({
    name: "Quiniela 80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 10,
  }));
  expect(await screen.findByText(/Reglas guardadas/)).toBeInTheDocument();
});

it("shows the server reason when the rules are rejected with 422", async () => {
  vi.mocked(apiClient.saveGameSettings).mockRejectedValue(new ApiError(422, "every prize must be at least 1"));
  const { user } = setup({ stayOnRules: true });
  await openRules();
  await user.click(screen.getByRole("button", { name: "Guardar reglas" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("every prize must be at least 1");
  expect(screen.getByLabelText("Nombre")).toHaveValue("Quiniela 80");
});
