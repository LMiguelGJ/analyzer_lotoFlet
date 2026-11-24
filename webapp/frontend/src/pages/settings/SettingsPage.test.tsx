import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, NetworkError } from "../../api/client";
import { getHistory, importHistory } from "../../api/history";
import { getLists, setActiveList, setListPrizes } from "../../api/lists";
import { getSettings, updateSettings } from "../../api/settings";
import { SettingsPage } from "./SettingsPage";
import { chanceList, historyFixture, importedHistory, leidsaActiveLists, leidsaList, listsFixture, settingsFixture } from "./test-fixtures";

vi.mock("../../api/history", () => ({ getHistory: vi.fn(), importHistory: vi.fn() }));
vi.mock("../../api/settings", () => ({ getSettings: vi.fn(), updateSettings: vi.fn() }));
vi.mock("../../api/lists", () => ({ getLists: vi.fn(), setActiveList: vi.fn(), setListPrizes: vi.fn() }));
const listsMock = vi.mocked(getLists), activeMock = vi.mocked(setActiveList), prizesMock = vi.mocked(setListPrizes);
const historyMock = vi.mocked(getHistory), importMock = vi.mocked(importHistory);
const settingsMock = vi.mocked(getSettings), updateMock = vi.mocked(updateSettings);
function mount() { return render(<SettingsPage />); }
function installDefaults() { historyMock.mockResolvedValue(historyFixture); settingsMock.mockResolvedValue(settingsFixture); listsMock.mockResolvedValue(listsFixture); }
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
    expect(screen.getByRole("status")).toHaveTextContent("Cargando ajustes");
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudieron cargar los ajustes");
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
  it("shows storage as plain sizes with a simple bar and keeps the editor in MB", async () => {
    mount();
    const input = await screen.findByLabelText("Límite de espacio (MB)");
    expect(input).toHaveAttribute("type", "text");
    expect(input).toHaveValue("2048");
    expect(screen.getByText("500 MB de 2 GB")).toBeInTheDocument();
    expect(screen.getByText(/Quedan 1\,5 GB libres/)).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: "Espacio usado" });
    expect(bar).toHaveAttribute("aria-valuenow", "25");
    expect(screen.queryByText("Queda poco espacio disponible.")).not.toBeInTheDocument();
  });
  it("warns in words when little space is left", async () => {
    settingsMock.mockResolvedValue({ ...settingsFixture, storage: { ...settingsFixture.storage, warning: true } });
    mount(); await screen.findByLabelText("Límite de espacio (MB)");
    expect(screen.getByText("Queda poco espacio disponible.")).toBeInTheDocument();
  });
  it("labels unreliable physical disk numbers only inside Avanzado", async () => {
    settingsMock.mockResolvedValue({ ...settingsFixture, storage: {
      ...settingsFixture.storage, free_disk_bytes: 9007199254740993, database_bytes: Number.NaN,
    } });
    mount(); await screen.findByLabelText("Límite de espacio (MB)");
    expect(screen.getByText("Valor aproximado: ≈ 9,007,199,254,740,992 bytes")).not.toBeVisible();
    expect(screen.getByText("Precisión no disponible")).not.toBeVisible();
    expect(screen.getByText("524,288,000 bytes")).not.toBeVisible();
  });
  it("updates displayed quota and draft from a successful save; preserves an edited draft after 409", async () => {
    const saved = { ...settingsFixture, quota: { ...settingsFixture.quota, effective_bytes: "3145728000", persisted_bytes: "3145728000" } };
    updateMock.mockResolvedValueOnce(saved).mockRejectedValueOnce(new ApiError(409, "La cuota no puede ser menor al uso actual."));
    mount();
    const input = await screen.findByLabelText("Límite de espacio (MB)");
    await userEvent.clear(input); await userEvent.type(input, "3000");
    await userEvent.click(screen.getByRole("button", { name: "Guardar límite" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith("3145728000", expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(await screen.findByText("Límite guardado")).toBeInTheDocument();
    expect(input).toHaveValue("3000");
    await userEvent.clear(input); await userEvent.type(input, "800");
    await userEvent.click(screen.getByRole("button", { name: "Guardar límite" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La cuota no puede ser menor al uso actual.");
    expect(input).toHaveValue("800");
  });
  it("offers «Sin límite»: sends the explicit marker and then shows no meter or finite cap", async () => {
    const unlimited = { ...settingsFixture, quota: { ...settingsFixture.quota, effective_bytes: "9223372036854775807", persisted_bytes: "9223372036854775807", unlimited: true } };
    updateMock.mockResolvedValueOnce(unlimited);
    mount();
    expect(await screen.findByRole("progressbar", { name: "Espacio usado" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sin límite" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith("9223372036854775807", expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(await screen.findByText(/Sin límite: la aplicación solo se detiene si el disco se llena/)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar", { name: "Espacio usado" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Límite de espacio (MB)")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Sin límite" })).not.toBeInTheDocument();
  });
  it("keeps an environment-managed quota read-only", async () => {
    settingsMock.mockResolvedValue({ ...settingsFixture, quota: { ...settingsFixture.quota, source: "environment", writable: false } });
    mount();
    const input = await screen.findByLabelText("Límite de espacio (MB)");
    expect(input).toBeDisabled();
    expect(screen.getByText(/fijado fuera de esta pantalla/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar límite" })).toBeDisabled();
    expect(updateMock).not.toHaveBeenCalled();
  });
  it("rejects invalid quota drafts without sending and never claims success on network failure", async () => {
    updateMock.mockRejectedValue(new NetworkError()); mount();
    const input = await screen.findByLabelText("Límite de espacio (MB)");
    await userEvent.clear(input); await userEvent.type(input, "abc");
    expect(screen.getByText("Escribí un número de MB mayor que 0, con hasta dos decimales.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar límite" })).toBeDisabled();
    await userEvent.clear(input); await userEvent.type(input, "1234");
    await userEvent.click(screen.getByRole("button", { name: "Guardar límite" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo contactar al servidor local");
    expect(screen.queryByText("Límite guardado")).not.toBeInTheDocument();
  });
  it("reads only accepted-size files, sends original text regardless of MIME, and handles already-known imports", async () => {
    importMock.mockResolvedValue({ created: false, added: 0, active: importedHistory });
    mount(); await screen.findByLabelText("Límite de espacio (MB)");
    const raw = '{ "draws" : [1, 2] }';
    const file = chooseFile(raw);
    await waitFor(() => expect(importMock).toHaveBeenCalledWith(raw, expect.objectContaining({ signal: expect.any(AbortSignal) })));
    expect(file.type).toBe("text/plain");
    expect(await screen.findByText("Ya estaba en las fuentes; no se agregaron sorteos.")).toBeInTheDocument();
    expect(await screen.findByText("b".repeat(64))).toBeInTheDocument();
    expect(historyMock).toHaveBeenCalledTimes(2);
  });
  it("rejects oversize files before reading and avoids duplicate submissions while reading", async () => {
    mount(); await screen.findByLabelText("Límite de espacio (MB)");
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
    const view = mount(); await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
    expect(await screen.findByText("Importación confirmada: se agregaron 10 sorteos; el historial activo tiene 130 sorteos.")).toBeInTheDocument();
    expect(screen.getByText("No se pudo actualizar el historial después de la importación confirmada.")).toBeInTheDocument();
    expect(importMock).toHaveBeenCalledTimes(1);

    view.unmount();
    vi.clearAllMocks(); installDefaults(); importMock.mockRejectedValue(new NetworkError());
    mount(); await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
    expect(await screen.findByText("No se pudo confirmar la importación; actualizá el historial para comprobar el resultado.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Actualizar historial" }));
    await waitFor(() => expect(historyMock).toHaveBeenCalledTimes(2));
    expect(importMock).toHaveBeenCalledTimes(1);
  });
  it.each([413, 409, 422])("shows definitive import HTTP %i detail without retry", async (status) => {
    importMock.mockRejectedValue(new ApiError(status, `detalle ${status}`)); mount();
    await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
    expect(await screen.findByRole("alert")).toHaveTextContent(`detalle ${status}`);
    expect(importMock).toHaveBeenCalledTimes(1);
  });
  it("aborts outstanding reads and an unfinished file read on unmount without posting", async () => {
    let resolveText!: (value: string) => void;
    const file = new File(["raw"], "ok.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: vi.fn(() => new Promise<string>((resolve) => { resolveText = resolve; })) });
    const view = mount(); await screen.findByLabelText("Límite de espacio (MB)");
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
    mount(); await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
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
    mount(); await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
    await screen.findByText(/Importación confirmada/);
    const input = screen.getByLabelText("Límite de espacio (MB)");
    await userEvent.clear(input); await userEvent.type(input, "3000");
    updateMock.mockResolvedValue({ ...settingsFixture, quota: { ...settingsFixture.quota, effective_bytes: "3145728000", persisted_bytes: "3145728000" } });
    await userEvent.click(screen.getByRole("button", { name: "Guardar límite" }));
    await waitFor(() => expect(input).toHaveValue("3000"));
    resolveSettings(settingsFixture);
    await Promise.resolve();
    expect(input).toHaveValue("3000");
  });
  it("has no axe violations after load and import", async () => {
    importMock.mockResolvedValue({ created: true, added: 10, active: importedHistory });
    const { container } = mount(); await screen.findByLabelText("Límite de espacio (MB)");
    let { axe } = await import("jest-axe"); expect(await axe(container)).toHaveNoViolations();
    chooseFile(); await screen.findByText(/Importación confirmada/);
    expect(await axe(container)).toHaveNoViolations();
  });

  describe("lista de números", () => {
    it("shows one card per list with friendly dates, marks the active one and offers the switch on the others", async () => {
      mount();
      const cards = await screen.findAllByRole("listitem");
      expect(cards).toHaveLength(2);
      expect(within(cards[0]).getByRole("heading", { name: "Loteka Chance Express" })).toBeInTheDocument();
      expect(within(cards[0]).getByText("1.381 sorteos · del 5 de marzo de 2025 al 25 de septiembre de 2026")).toBeInTheDocument();
      expect(within(cards[0]).getByText("5 números por sorteo")).toBeInTheDocument();
      expect(within(cards[0]).getByText(/En uso/)).toBeInTheDocument();
      expect(within(cards[0]).queryByRole("button")).not.toBeInTheDocument();
      expect(within(cards[1]).getByText("3 números por sorteo")).toBeInTheDocument();
      expect(within(cards[1]).getByRole("button", { name: "Usar esta lista" })).toBeEnabled();
    });
    it("disables an unavailable list and says why", async () => {
      listsMock.mockResolvedValue([chanceList, { ...leidsaList, available: false, draws: 0, first_label: null, last_label: null }]);
      mount();
      expect(await screen.findByText("Falta el archivo de esta lista")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Usar esta lista" })).toBeDisabled();
    });
    it("switches the list, confirms it, refreshes the data and swaps the prize fields", async () => {
      activeMock.mockResolvedValue(leidsaActiveLists);
      listsMock.mockResolvedValueOnce(listsFixture).mockResolvedValue(leidsaActiveLists);
      mount();
      await userEvent.click(await screen.findByRole("button", { name: "Usar esta lista" }));
      expect(activeMock).toHaveBeenCalledWith("leidsa_quiniela", expect.objectContaining({ signal: expect.any(AbortSignal) }));
      expect(await screen.findByText("Ahora trabajás con «Quiniela Leidsa».")).toBeInTheDocument();
      await waitFor(() => expect(settingsMock).toHaveBeenCalledTimes(2));
      expect(screen.getAllByText(/✓ En uso/)).toHaveLength(1);
      expect(screen.getByLabelText("3.er número")).toHaveValue("4");
      expect(screen.queryByLabelText("4.º número")).not.toBeInTheDocument();
    });
    it("shows the server's reason when the switch is refused", async () => {
      activeMock.mockRejectedValue(new ApiError(409, "Falta el archivo de la lista «Quiniela Leidsa»."));
      mount();
      await userEvent.click(await screen.findByRole("button", { name: "Usar esta lista" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Falta el archivo de la lista «Quiniela Leidsa».");
      expect(screen.queryByText(/Ahora trabajás/)).not.toBeInTheDocument();
    });
    it("does not break when /history answers 409 under Leidsa and hides the importer with an explanation", async () => {
      listsMock.mockResolvedValue(leidsaActiveLists);
      historyMock.mockRejectedValue(new ApiError(409, "Con Leidsa no hay historial importable."));
      mount();
      expect(await screen.findByRole("heading", { name: "Premios" })).toBeInTheDocument();
      expect(screen.queryByLabelText("Elegir archivo de historial")).not.toBeInTheDocument();
      expect(screen.getByText(/solo funciona con Loteka Chance Express/)).toBeInTheDocument();
      expect(screen.queryByText("Fuentes de historial")).not.toBeInTheDocument();
    });
  });

  describe("premios", () => {
    it("shows one field per position with ordinal labels, Chance defaults included", async () => {
      mount();
      expect(await screen.findByText("Paga por cada peso")).toBeInTheDocument();
      expect(["1.er número", "2.º número", "3.er número", "4.º número", "5.º número"].map((label) => (screen.getByLabelText(label) as HTMLInputElement).value)).toEqual(["80", "8", "4", "2", "1"]);
      expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "Volver a los valores originales" })).toBeDisabled();
    });
    it("saves edited prizes as numbers and confirms", async () => {
      listsMock.mockResolvedValue(leidsaActiveLists);
      historyMock.mockRejectedValue(new ApiError(409, "x"));
      prizesMock.mockResolvedValue([{ ...chanceList, active: false }, { ...leidsaList, active: true, prizes: [70, 8, 4] }]);
      mount();
      const first = await screen.findByLabelText("1.er número");
      await userEvent.clear(first); await userEvent.type(first, "70");
      await userEvent.click(screen.getByRole("button", { name: "Guardar" }));
      await waitFor(() => expect(prizesMock).toHaveBeenCalledWith("leidsa_quiniela", [70, 8, 4], expect.anything()));
      expect(await screen.findByText("Premios guardados.")).toBeInTheDocument();
      expect(screen.getByLabelText("1.er número")).toHaveValue("70");
      expect(screen.getByRole("button", { name: "Volver a los valores originales" })).toBeEnabled();
    });
    it("restores the original values by sending null", async () => {
      listsMock.mockResolvedValue([{ ...chanceList, prizes: [90, 8, 4, 2, 1] }, leidsaList]);
      prizesMock.mockResolvedValue(listsFixture);
      mount();
      await userEvent.click(await screen.findByRole("button", { name: "Volver a los valores originales" }));
      await waitFor(() => expect(prizesMock).toHaveBeenCalledWith("chance_express", null, expect.anything()));
      expect(await screen.findByText("Se restauraron los valores originales.")).toBeInTheDocument();
      expect(screen.getByLabelText("1.er número")).toHaveValue("80");
    });
    it("shows the server's 422 message inline, tied to the fields, and keeps the draft", async () => {
      const message = "La lista «Loteka Chance Express» necesita 5 premios, uno por posición.";
      prizesMock.mockRejectedValue(new ApiError(422, message));
      mount();
      const second = await screen.findByLabelText("2.º número");
      await userEvent.clear(second); await userEvent.type(second, "9");
      await userEvent.click(screen.getByRole("button", { name: "Guardar" }));
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(message);
      expect(second).toHaveAttribute("aria-invalid", "true");
      expect(second.getAttribute("aria-describedby")).toContain(alert.id);
      expect(second).toHaveValue("9");
    });
    it("rejects non-numeric or out-of-range prizes without calling the server", async () => {
      mount();
      const first = await screen.findByLabelText("1.er número");
      await userEvent.clear(first); await userEvent.type(first, "10001");
      await userEvent.click(screen.getByRole("button", { name: "Guardar" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Cada premio debe ser un número entero mayor que 0 y como máximo 10000.");
      expect(prizesMock).not.toHaveBeenCalled();
    });
  });

  describe("lenguaje sencillo", () => {
    it("keeps Avanzado collapsed and shows no technical jargon outside it", async () => {
      const { container } = mount();
      await screen.findByLabelText("Límite de espacio (MB)");
      const advanced = screen.getByText("Avanzado").closest("details")!;
      expect(advanced).not.toHaveAttribute("open");
      const jargon = /SHA-256|\bWAL\b|\bSHM\b|bytes|SQLite|Uso lógico|Artefactos|congelado|importado|Cuota efectiva/i;
      const leaks = Array.from(container.querySelectorAll("*")).filter((node) => !advanced.contains(node)
        && Array.from(node.childNodes).some((child) => child.nodeType === Node.TEXT_NODE && jargon.test(child.textContent ?? "")));
      expect(leaks.map((node) => node.textContent)).toEqual([]);
      expect(within(advanced).getByText("WAL")).not.toBeVisible();
      expect(within(advanced).getAllByText("SHA-256").length).toBeGreaterThan(0);
    });
    it("opens Avanzado by itself to show an import result", async () => {
      importMock.mockRejectedValue(new ApiError(422, "detalle 422"));
      mount(); await screen.findByLabelText("Límite de espacio (MB)"); chooseFile();
      await screen.findByRole("alert");
      expect(screen.getByText("Avanzado").closest("details")).toHaveAttribute("open");
    });
  });
});
