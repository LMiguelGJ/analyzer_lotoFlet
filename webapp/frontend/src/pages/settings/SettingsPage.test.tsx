import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "../../api/client";
import { getHistory, importHistory } from "../../api/history";
import { getSettings, updateSettings } from "../../api/settings";
import { SettingsPage } from "./SettingsPage";
import { historyFixture, importedHistory, settingsFixture } from "./test-fixtures";

vi.mock("../../api/history", () => ({ getHistory: vi.fn(), importHistory: vi.fn() }));
vi.mock("../../api/settings", () => ({ getSettings: vi.fn(), updateSettings: vi.fn() }));
const historyMock = vi.mocked(getHistory), importMock = vi.mocked(importHistory);
const settingsMock = vi.mocked(getSettings), updateMock = vi.mocked(updateSettings);
function mount() { return render(<SettingsPage />); }
function installDefaults() { historyMock.mockResolvedValue(historyFixture); settingsMock.mockResolvedValue(settingsFixture); }
function chooseFile(raw = '{ "draws" : [] }', name = "historial.json") {
  const file = new File([raw], name, { type: "text/plain" });
  Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue(raw) });
  fireEvent.change(screen.getByLabelText("Elegir archivo de historial"), { target: { files: [file] } });
  return file;
}
beforeEach(() => { vi.clearAllMocks(); installDefaults(); });

describe("settings page", () => {
  it("announces loading and recovers both resources after an initial read error", async () => {
    historyMock.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(historyFixture);
    mount();
    expect(screen.getByRole("status")).toHaveTextContent("Cargando ajustes e historial");
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar los ajustes y el historial");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Fuentes de historial" )).toBeInTheDocument();
  });
  it("separates active from origin, reports coverage distinctly, and wraps complete fingerprints", async () => {
    mount();
    expect(await screen.findByText("a".repeat(64))).toBeInTheDocument();
    expect(screen.getByText("Activo · Historial congelado")).toBeInTheDocument();
    expect(screen.getByText("Inactivo · Historial importado")).toBeInTheDocument();
    expect(screen.getByText((_text, element) => element?.tagName === "DD" && element.textContent === "100 de 120")).toBeInTheDocument();
    expect(screen.getByText((_text, element) => element?.tagName === "DD" && element.textContent === "105 de 130")).toBeInTheDocument();
  });
  it("uses exact storage bytes, computes remaining bytes with BigInt and does not use number inputs", async () => {
    mount();
    const input = await screen.findByLabelText("Cuota en bytes");
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("1000");
    expect(screen.getByText("9,007,199,254,740,993 bytes")).toBeInTheDocument();
    expect(screen.getByText("0 bytes")).toBeInTheDocument();
    expect(screen.getByText("Poco margen de almacenamiento o de disco")).toBeInTheDocument();
  });
  it("labels unreliable physical disk numbers without weakening exact logical byte values", async () => {
    settingsMock.mockResolvedValue({ ...settingsFixture, storage: {
      ...settingsFixture.storage, free_disk_bytes: 9007199254740993, database_bytes: Number.NaN,
    } });
    mount(); await screen.findByLabelText("Cuota en bytes");
    expect(screen.getByText("Valor aproximado: ≈ 9,007,199,254,740,992 bytes")).toBeInTheDocument();
    expect(screen.getByText("Precisión no disponible")).toBeInTheDocument();
    expect(screen.getByText("9,007,199,254,740,993 bytes")).toBeInTheDocument();
  });
  it("updates displayed quota and draft from a successful save; preserves an edited draft after 409", async () => {
    const saved = { ...settingsFixture, quota: { ...settingsFixture.quota, effective_bytes: "2000", persisted_bytes: "2000" } };
    updateMock.mockResolvedValueOnce(saved).mockRejectedValueOnce(new ApiError(409, "La cuota no puede ser menor al uso actual."));
    mount();
    const input = await screen.findByLabelText("Cuota en bytes");
    await userEvent.clear(input); await userEvent.type(input, "2000");
    await userEvent.click(screen.getByRole("button", { name: "Guardar cuota" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith("2000", expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(await screen.findByText("Cuota guardada")).toBeInTheDocument();
    expect(input).toHaveValue("2000");
    await userEvent.clear(input); await userEvent.type(input, "800");
    await userEvent.click(screen.getByRole("button", { name: "Guardar cuota" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La cuota no puede ser menor al uso actual.");
    expect(input).toHaveValue("800");
  });
  it("keeps an environment-managed quota read-only", async () => {
    settingsMock.mockResolvedValue({ ...settingsFixture, quota: { ...settingsFixture.quota, source: "environment", writable: false } });
    mount();
    const input = await screen.findByLabelText("Cuota en bytes");
    expect(input).toBeDisabled();
    expect(screen.getByText(/solo lectura, definida fuera de esta pantalla/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar cuota" })).toBeDisabled();
    expect(updateMock).not.toHaveBeenCalled();
  });
  it("rejects invalid quota drafts without sending and never claims success on network failure", async () => {
    updateMock.mockRejectedValue(new NetworkError()); mount();
    const input = await screen.findByLabelText("Cuota en bytes");
    await userEvent.clear(input); await userEvent.type(input, "01");
    expect(screen.getByText("Ingresá bytes como un entero decimal positivo, sin ceros iniciales." )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar cuota" })).toBeDisabled();
    await userEvent.clear(input); await userEvent.type(input, "1234");
    await userEvent.click(screen.getByRole("button", { name: "Guardar cuota" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo contactar al servidor local");
    expect(screen.queryByText("Cuota guardada")).not.toBeInTheDocument();
  });
  it("reads only accepted-size files, sends original text regardless of MIME, and handles already-known imports", async () => {
    importMock.mockResolvedValue({ created: false, added: 0, active: importedHistory });
    mount(); await screen.findByLabelText("Cuota en bytes");
    const raw = '{ "draws" : [1, 2] }';
    const file = chooseFile(raw);
    await waitFor(() => expect(importMock).toHaveBeenCalledWith(raw, expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(file.type).toBe("text/plain");
    expect(await screen.findByText("Ya estaba en las fuentes; no se agregaron sorteos.")).toBeInTheDocument();
    expect(await screen.findByText("b".repeat(64))).toBeInTheDocument();
    expect(historyMock).toHaveBeenCalledTimes(2);
  });
  it("rejects oversize files before reading and avoids duplicate submissions while reading", async () => {
    mount(); await screen.findByLabelText("Cuota en bytes");
    const control = screen.getByLabelText("Elegir archivo de historial");
    const tooLarge = new File(["x"], "big.json", { type: "application/json" });
    Object.defineProperty(tooLarge, "size", { value: 33_554_433 });
    const text = vi.fn(); Object.defineProperty(tooLarge, "text", { value: text });
    fireEvent.change(control, { target: { files: [tooLarge] } });
    expect(text).not.toHaveBeenCalled(); expect(importMock).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent("32 MiB");
    let resolveText!: (value: string) => void;
    const file = new File(["raw"], "ok.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: vi.fn(() => new Promise<string>((resolve) => { resolveText = resolve; })) });
    fireEvent.change(control, { target: { files: [file] } });
    fireEvent.change(control, { target: { files: [file] } });
    expect(importMock).not.toHaveBeenCalled();
    resolveText("raw");
    await waitFor(() => expect(importMock).toHaveBeenCalledTimes(1));
  });
  it("keeps confirmed import success when refresh fails and lets the user reconcile ambiguous transport errors with GET only", async () => {
    importMock.mockResolvedValue({ created: true, added: 10, active: importedHistory });
    historyMock.mockResolvedValueOnce(historyFixture).mockRejectedValueOnce(new Error("offline"));
    const view = mount(); await screen.findByLabelText("Cuota en bytes"); chooseFile();
    expect(await screen.findByText("Importación confirmada: se agregaron 10 sorteos; el historial activo tiene 130 sorteos.")).toBeInTheDocument();
    expect(screen.getByText("No se pudo actualizar el historial después de la importación confirmada.")).toBeInTheDocument();
    expect(importMock).toHaveBeenCalledTimes(1);

    view.unmount();
    vi.clearAllMocks(); installDefaults(); importMock.mockRejectedValue(new NetworkError());
    mount(); await screen.findByLabelText("Cuota en bytes"); chooseFile();
    expect(await screen.findByText("No se pudo confirmar la importación; actualizá el historial para comprobar el resultado.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Actualizar historial" }));
    await waitFor(() => expect(historyMock).toHaveBeenCalledTimes(2));
    expect(importMock).toHaveBeenCalledTimes(1);
  });
  it.each([413, 409, 422])("shows definitive import HTTP %i detail without retry", async (status) => {
    importMock.mockRejectedValue(new ApiError(status, `detalle ${status}`)); mount();
    await screen.findByLabelText("Cuota en bytes"); chooseFile();
    expect(await screen.findByRole("alert")).toHaveTextContent(`detalle ${status}`);
    expect(importMock).toHaveBeenCalledTimes(1);
  });
  it("aborts outstanding reads and an unfinished file read on unmount without posting", async () => {
    let resolveText!: (value: string) => void;
    const file = new File(["raw"], "ok.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: vi.fn(() => new Promise<string>((resolve) => { resolveText = resolve; })) });
    const view = mount(); await screen.findByLabelText("Cuota en bytes");
    fireEvent.change(screen.getByLabelText("Elegir archivo de historial"), { target: { files: [file] } });
    const [historyOptions] = historyMock.mock.calls[0];
    view.unmount();
    expect(historyOptions?.signal).toBeInstanceOf(AbortSignal);
    expect(historyOptions?.signal?.aborted).toBe(true);
    resolveText("raw");
    await Promise.resolve();
    expect(importMock).not.toHaveBeenCalled();
  });
  it.each(["stale success", "stale rejection"] as const)("does not let a reconciliation %s overwrite a newer successful import", async (outcome) => {
    let resolveHistory!: (value: typeof historyFixture) => void;
    let rejectHistory!: (reason: Error) => void;
    let resolveSettings!: (value: typeof settingsFixture) => void;
    const deferredHistory = new Promise<typeof historyFixture>((resolve, reject) => { resolveHistory = resolve; rejectHistory = reject; });
    const deferredSettings = new Promise<typeof settingsFixture>((resolve) => { resolveSettings = resolve; });
    historyMock.mockResolvedValueOnce(historyFixture).mockImplementationOnce(() => deferredHistory);
    settingsMock.mockResolvedValueOnce(settingsFixture).mockImplementationOnce(() => deferredSettings);
    importMock.mockRejectedValueOnce(new NetworkError()).mockResolvedValueOnce({ created: true, added: 10, active: importedHistory });
    mount(); await screen.findByLabelText("Cuota en bytes"); chooseFile();
    await screen.findByRole("button", { name: "Actualizar historial" });
    await userEvent.click(screen.getByRole("button", { name: "Actualizar historial" }));
    await waitFor(() => expect(historyMock).toHaveBeenCalledTimes(2));

    chooseFile();
    expect(await screen.findByText(/Importación confirmada/)).toBeInTheDocument();
    if (outcome === "stale rejection") rejectHistory(new Error("late read failure"));
    else resolveHistory(historyFixture);
    resolveSettings(settingsFixture);
    await waitFor(() => expect(settingsMock).toHaveBeenCalledTimes(3));
    await Promise.resolve();

    expect(screen.getByText(/Importación confirmada/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Actualizar historial" })).not.toBeInTheDocument();
    expect(screen.queryByText("No se pudo confirmar la importación; actualizá el historial para comprobar el resultado.")).not.toBeInTheDocument();
    expect(screen.queryByText("No se pudo actualizar el historial.")).not.toBeInTheDocument();
  });
  it("does not let the post-import refresh overwrite a newer quota save", async () => {
    const active = { ...importedHistory, active: true };
    importMock.mockResolvedValue({ created: true, added: 10, active });
    let resolveSettings!: (value: typeof settingsFixture) => void;
    settingsMock.mockResolvedValueOnce(settingsFixture).mockImplementationOnce(() => new Promise((resolve) => { resolveSettings = resolve; }));
    historyMock.mockResolvedValueOnce(historyFixture).mockImplementationOnce(() => new Promise(() => {}));
    mount(); await screen.findByLabelText("Cuota en bytes"); chooseFile();
    await screen.findByText(/Importación confirmada/);
    const input = screen.getByLabelText("Cuota en bytes");
    await userEvent.clear(input); await userEvent.type(input, "2000");
    updateMock.mockResolvedValue({ ...settingsFixture, quota: { ...settingsFixture.quota, effective_bytes: "2000", persisted_bytes: "2000" } });
    await userEvent.click(screen.getByRole("button", { name: "Guardar cuota" }));
    await waitFor(() => expect(input).toHaveValue("2000"));
    resolveSettings(settingsFixture);
    await Promise.resolve();
    expect(input).toHaveValue("2000");
  });
  it("has no axe violations after load and import", async () => {
    importMock.mockResolvedValue({ created: true, added: 10, active: importedHistory });
    const { container } = mount(); await screen.findByLabelText("Cuota en bytes");
    let { axe } = await import("jest-axe"); expect(await axe(container)).toHaveNoViolations();
    chooseFile(); await screen.findByText(/Importación confirmada/);
    expect(await axe(container)).toHaveNoViolations();
  });
});
