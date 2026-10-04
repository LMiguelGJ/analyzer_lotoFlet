import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "../../App";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { SettingsView } from "../../api/types";
import fixture from "../../api/__fixtures__/settings.json";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getSettings: vi.fn(), updateSettings: vi.fn(), getAgentCredential: vi.fn() } };
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
function setup() {
  const router = createMemoryRouter([{ path: "*", element: <App /> }], { initialEntries: ["/ajustes"] });
  return { user: userEvent.setup(), router, ...render(<RouterProvider router={router} />) };
}
async function openAgentAccess(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole("heading", { name: "Capacidad" });
  await user.click(screen.getByText("Acceso para agentes"));
}
beforeEach(() => {
  vi.mocked(apiClient.getSettings).mockReset().mockResolvedValue(base);
  vi.mocked(apiClient.updateSettings).mockReset().mockResolvedValue(base);
  vi.mocked(agentApi.getAgentCredential).mockReset();
  originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
});
afterEach(() => {
  if (originalClipboard) Object.defineProperty(navigator, "clipboard", originalClipboard);
  else Reflect.deleteProperty(navigator, "clipboard");
});

it("loads the actual view, distinguishing logical quota, physical files and free disk", async () => {
  let resolve!: (view: SettingsView) => void;
  vi.mocked(apiClient.getSettings).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  setup();
  expect(screen.getByRole("status")).toHaveTextContent(/Cargando capacidad y límites/);
  resolve(base);
  expect(await screen.findByRole("heading", { name: "Capacidad" })).toBeInTheDocument();
  expect(screen.getAllByText("5 GiB")).toHaveLength(2);
  expect(screen.getByText("1.5 KiB")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "0");
  const diagnostics = screen.getByText("Detalles técnicos").closest("details")!;
  // Capacity leads; diagnostics come after it; one primary action on the page.
  expect(screen.getByRole("heading", { name: "Capacidad" }).compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
  expect(screen.getByText(/Por defecto/)).toBeInTheDocument();
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
  expect(await screen.findByRole("heading", { name: "Capacidad" })).toBeInTheDocument();
});

it.each(["", "0", "01", " 5", "+5", "-1", "1.5", "1e3", "９", "9223372036854775808"])("rejects invalid byte input %j with focus and no PUT", async (value) => {
  const { user } = setup();
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
  setup();
  expect(await screen.findByText(/Variable de entorno/)).toBeInTheDocument();
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
  const capacity = (await screen.findByRole("heading", { name: "Capacidad" })).closest("section")!;
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
  setup();
  expect(await screen.findByText("1 KiB", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "60");
});

it("clamps remaining and progress when aggregate usage exceeds the effective limit", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "1200", persisted_bytes: "1200", source: "persisted", writable: true },
  });
  setup();
  expect(await screen.findByText("0 bytes", { selector: "span" })).toBeInTheDocument();
  expect(screen.getByText(/Uso superior al límite por 336 bytes/)).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "Cuota lógica utilizada" })).toHaveAttribute("value", "100");
});

it("marks historical-only responses as incomplete instead of claiming an aggregate", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(fixture as SettingsView);
  const { user } = setup();
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
  setup();
  expect(await screen.findByRole("alert")).toHaveTextContent(/límite o falta de disco/);
  expect(screen.getAllByText(/9,007,199,254,740,993 bytes/).length).toBeGreaterThanOrEqual(1);
});

it("guards dirty navigation and unload while a refresh keeps the draft across server changes", async () => {
  vi.mocked(apiClient.getSettings).mockResolvedValueOnce(base).mockResolvedValueOnce({
    ...base, quota: { effective_bytes: "6000000000", persisted_bytes: "6000000000", source: "persisted", writable: true },
  });
  const add = vi.spyOn(window, "addEventListener");
  const { user, router } = setup();
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
  const input = await screen.findByRole("textbox", { name: /Nuevo límite de almacenamiento/ });
  await user.click(screen.getByRole("link", { name: "Simulaciones" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/experimentos"));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Ajustes" }));
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
  await screen.findByRole("heading", { name: "Capacidad" });
  expect(await axe(container)).toHaveNoViolations();
});
