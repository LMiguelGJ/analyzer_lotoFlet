import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
// Contract coverage: F-LIST-038–F-LIST-055 — ordered history/import tasks, original Blob and explicit confirmation, hash-bound promote, library paging/errors/stale requests, uncertain promotion lock, and no continuation for non-executable profiles.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import { DataPage } from "./index";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getProfiles: vi.fn(), getDatasets: vi.fn(),
    previewHistoryImport: vi.fn(), promoteHistoryImport: vi.fn() } };
});
const historyClient = apiClient as typeof apiClient & {
  previewHistoryImport: (file: Blob, profile: import("../../api/types").ProfileListing, source: string, timezone: string) => Promise<unknown>;
  promoteHistoryImport: (...args: unknown[]) => Promise<unknown>;
};
const digest = "a".repeat(64);
const profile = { schema_version: 1 as const, profile_id: "local", revision: 1, universe_size: 100, positions: 2,
  allows_repeats: true, multipliers: [{ numerator: 80, denominator: 1 }, { numerator: 8, denominator: 1 }],
  currency: "DOP", scale: 0, stake_increment: 1, minimum_stake: 1, maximum_stake: 100,
  max_coverage: 50, max_exposure: 500, best_rule: "maximum-payout/v1" as const };
const listing = { profile, profile_sha256: digest, execution_supported: false, profile_execution: { ready: true,
  selector_capabilities: [], staking_capabilities: [], entry_policies: [], settlements: ["all", "best"] as const,
  requires_compatible_dataset: true } };
const metadata = { schema_version: 1, juego: "Juego", origen: "operador-local", endpoint: "https://example.invalid",
  zona_horaria: "America/Santo_Domingo", cantidad_sorteos: 1, rango_seleccionado: { desde: "2025-01-01", hasta: "2025-01-01" } };
const validPreview = { promotable: true, source_sha256: "b".repeat(64), dataset_sha256: "c".repeat(64), rows_seen: 1,
  records_total: 1, duplicates_merged: 0, error_count: 0, errors_truncated: false, errors: [],
  sample: [{ date: "2025-01-01", time: "10:30", numbers: [1, 2] }], execution_supported: false as const,
  profile_compatibility: { profile_id: "local", profile_revision: 1, profile_sha256: digest, registered: true,
    execution_supported: false as const, rules_source: "registered_game_profile" } };
const dataset = { dataset_sha256: "c".repeat(64), source_sha256: "b".repeat(64), source_format: "history_json" as const,
  created_at: "2025-01-02T00:00:00Z", source_id: "operador-local", source_kind: "historical" as const, source_revision: "1",
  profile_id: "local", profile_revision: 1, profile_sha256: digest, positions: 2, universe_size: 100,
  records_total: 1, first_draw: "2025-01-01 10:30", last_draw: "2025-01-01 10:30",
  clock: { mode: "iana" as const, zone: "America/Santo_Domingo" }, execution_supported: false as const,
  profile_execution: listing.profile_execution };

afterEach(() => { vi.restoreAllMocks(); });

beforeEach(() => {
  vi.mocked(apiClient.getProfiles).mockReset().mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [listing], templates: [] });
  vi.mocked(apiClient.getDatasets).mockReset().mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [dataset] });
  vi.mocked(historyClient.previewHistoryImport).mockReset().mockResolvedValue(validPreview);
  vi.mocked(historyClient.promoteHistoryImport).mockReset().mockResolvedValue({ dataset_sha256: dataset.dataset_sha256,
    created_at: dataset.created_at, created: true, duplicate_source_differs: false, retained_source_sha256: dataset.source_sha256,
    submitted_source_sha256: dataset.source_sha256, rows_seen: 1, records_total: 1, duplicates_merged: 0,
    execution_supported: false });
});

function mount() { render(<MemoryRouter><DataPage /></MemoryRouter>); }

describe("canonical history import and saved library", () => {
  it("shows metadata for confirmation, uploads original Blob bytes, and lists reusable paginated datasets", async () => {
    const user = userEvent.setup();
    mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: { "2025-01-01": [{ hora: "10:30", numeros: [1, 2] }] } });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json", { type: "application/json" }));
    expect(await screen.findByText(/Juego: Juego/)).toBeInTheDocument();
    expect(screen.getAllByText(/America\/Santo_Domingo/).length).toBeGreaterThan(0);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await waitFor(() => expect(historyClient.previewHistoryImport).toHaveBeenCalledTimes(1));
    const [blob, profileContext, source, timezone] = vi.mocked(historyClient.previewHistoryImport).mock.calls[0];
    expect(blob).toBeInstanceOf(Blob);
    expect(profileContext).toEqual(listing);
    expect(source).toBe(metadata.origen);
    expect(timezone).toBe(metadata.zona_horaria);
    await user.click(await screen.findByRole("button", { name: /Confirmar y guardar historial/i }));
    expect(await screen.findByText("Historial guardado.")).toBeInTheDocument();
    expect(await screen.findByText(/Historial · 1 sorteos/)).toBeInTheDocument();
    expect(screen.getByText(/Historial · 1 sorteos/).closest("li")).toHaveClass("dataset-card");
    expect(within(library()).getByRole("status")).toHaveTextContent("Reglas disponibles para usar este historial.");
    expect(within(library()).getByText(/Fuente: operador-local/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Usar este historial/i })).toHaveAttribute("href", `/simulaciones/nueva/sesion?dataset_sha256=${dataset.dataset_sha256}`);
  });

  it("pages through the saved dataset library without changing the selected profile", async () => {
    vi.mocked(apiClient.getDatasets).mockImplementation(async (offset = 0) => {
      if (offset === 0) return { total: 21, offset, limit: 20, items: [] };
      return { total: 21, offset, limit: 20, items: [dataset] };
    });
    const user = userEvent.setup(); mount();
    expect(await screen.findByText("1–20 de 21")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText(/Historial · 1 sorteos/)).toBeInTheDocument();
    expect(apiClient.getDatasets).toHaveBeenLastCalledWith(20, 20);
    expect(screen.getByRole("link", { name: /Usar este historial/ })).toHaveAttribute("href", `/simulaciones/nueva/sesion?dataset_sha256=${dataset.dataset_sha256}`);
  });

  it("keeps file metadata when the profile changes while FileReader is pending", async () => {
    let finishRead!: (text: string) => void;
    vi.spyOn(FileReader.prototype, "readAsText").mockImplementation(function (this: FileReader) {
      finishRead = (text) => {
        Object.defineProperty(this, "result", { configurable: true, value: text });
        this.onload?.(new ProgressEvent("load") as ProgressEvent<FileReader>);
      };
    });
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await act(async () => { finishRead(raw); });
    expect(await screen.findByText(/Juego: Juego/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Importar historial/i })).toBeEnabled();
  });

  it("ignores a superseded file read and a pending preview after child unmount", async () => {
    let finishFirstRead!: (text: string) => void;
    vi.spyOn(FileReader.prototype, "readAsText").mockImplementationOnce(function (this: FileReader) {
      finishFirstRead = (text) => { Object.defineProperty(this, "result", { configurable: true, value: text }); this.onload?.(new ProgressEvent("load") as ProgressEvent<FileReader>); };
    });
    let resolvePreview!: (value: typeof validPreview) => void;
    vi.mocked(historyClient.previewHistoryImport).mockImplementationOnce(() => new Promise((resolve) => { resolvePreview = resolve; }));
    const user = userEvent.setup(); const view = render(<MemoryRouter><DataPage /></MemoryRouter>);
    const oldRaw = JSON.stringify({ metadata: { ...metadata, juego: "Archivo anterior" }, sorteos_por_fecha: {} });
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    const input = await screen.findByLabelText("Archivo del historial (hasta 32 MB)");
    await user.upload(input, new File([oldRaw], "old.json"));
    await user.upload(input, new File([raw], "new.json"));
    await screen.findByText(/Juego: Juego/);
    await act(async () => { finishFirstRead(oldRaw); });
    expect(screen.getByText(/Juego: Juego/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await waitFor(() => expect(historyClient.previewHistoryImport).toHaveBeenCalledTimes(1));
    view.unmount();
    await act(async () => { resolvePreview(validPreview); });
    expect(historyClient.promoteHistoryImport).not.toHaveBeenCalled();
    expect(apiClient.getDatasets).toHaveBeenCalledTimes(1);
    vi.restoreAllMocks();
  });

  it("does not publish a promotion response or refresh the library after child unmount", async () => {
    let resolvePromotion!: (value: Awaited<ReturnType<typeof historyClient.promoteHistoryImport>>) => void;
    vi.mocked(historyClient.promoteHistoryImport).mockImplementationOnce(() => new Promise((resolve) => { resolvePromotion = resolve; }));
    const user = userEvent.setup(); const view = render(<MemoryRouter><DataPage /></MemoryRouter>);
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await user.click(await screen.findByRole("button", { name: /Confirmar y guardar historial/i }));
    await waitFor(() => expect(historyClient.promoteHistoryImport).toHaveBeenCalledTimes(1));
    view.unmount();
    await act(async () => { resolvePromotion({ dataset_sha256: dataset.dataset_sha256, created_at: dataset.created_at,
      created: true, duplicate_source_differs: false, retained_source_sha256: dataset.source_sha256,
      submitted_source_sha256: dataset.source_sha256, rows_seen: 1, records_total: 1, duplicates_merged: 0,
      execution_supported: false }); });
    expect(historyClient.promoteHistoryImport).toHaveBeenCalledTimes(1);
    expect(apiClient.getDatasets).toHaveBeenCalledTimes(1);
  });

  it("keeps only the newest preview when the file/profile context changes mid-request", async () => {
    let resolveOld!: (value: typeof validPreview) => void;
    vi.mocked(historyClient.previewHistoryImport).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }));
    vi.mocked(historyClient.previewHistoryImport).mockResolvedValueOnce(validPreview);
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    const profileChoice = screen.getByLabelText("Reglas del juego");
    await user.selectOptions(profileChoice, "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await waitFor(() => expect(historyClient.previewHistoryImport).toHaveBeenCalledTimes(1));
    await user.selectOptions(profileChoice, "");
    await user.selectOptions(profileChoice, "local@1");
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await screen.findByRole("button", { name: /Confirmar y guardar historial/i });
    await act(async () => { resolveOld({ ...validPreview, dataset_sha256: "d".repeat(64) }); });
    expect(screen.getAllByText(new RegExp(validPreview.dataset_sha256!)).length).toBeGreaterThan(0);
    expect(screen.queryByText(new RegExp("d".repeat(64)))).not.toBeInTheDocument();
  });

  it("invalidates a preview when the profile binding changes before promotion", async () => {
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await screen.findByRole("button", { name: /Confirmar y guardar historial/i });
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "");
    expect(screen.queryByRole("button", { name: /Confirmar y guardar historial/i })).not.toBeInTheDocument();
    expect(historyClient.promoteHistoryImport).not.toHaveBeenCalled();
  });

  it("surfaces backend binding mismatch and never promotes its rejected preview", async () => {
    vi.mocked(historyClient.previewHistoryImport).mockRejectedValueOnce(new ApiError(409, "registered profile hash does not match identity"));
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Los datos cambiaron o no hay espacio/);
    expect(historyClient.promoteHistoryImport).not.toHaveBeenCalled();
  });

  it("locks promotion after an uncertain response instead of retrying", async () => {
    vi.mocked(historyClient.promoteHistoryImport).mockRejectedValueOnce(new NetworkError());
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await user.click(await screen.findByRole("button", { name: /Confirmar y guardar historial/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo contactar al servidor/);
    expect(screen.getByText(/Comprobá el estado desde la cola/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Importar historial/i })).toBeDisabled();
    expect(historyClient.promoteHistoryImport).toHaveBeenCalledTimes(1);
    await user.click(screen.getByText("Importar archivo CSV o JSON"));
    const recordsMode = screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ });
    expect(recordsMode).toBeDisabled();
    fireEvent.click(recordsMode);
    expect(screen.getByRole("radio", { name: /Historial ordinario/ })).toBeChecked();
    expect(screen.getByText(/Comprobá el estado desde la cola/)).toBeVisible();
  });

  it("preserves history metadata, confirmations and its preview snapshot when switching idle modes", async () => {
    const user = userEvent.setup(); mount();
    const original = new File([JSON.stringify({ metadata, sorteos_por_fecha: {} })], "history.json");
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), original);
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: "Importar historial" }));
    await screen.findByRole("button", { name: /Confirmar y guardar historial/ });
    const form = screen.getByRole("form", { name: "Importar datos" });
    expect(document.querySelectorAll("form form")).toHaveLength(0);
    await user.click(screen.getByText("Importar archivo CSV o JSON"));
    await user.click(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ }));
    expect(within(form).queryByRole("button", { name: /Confirmar y guardar historial/ })).not.toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "Generar vista previa" })).toBeVisible();
    await user.click(screen.getByRole("radio", { name: /Historial ordinario/ }));
    expect(screen.getByRole("checkbox", { name: /Confirmo la fuente/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ })).toBeChecked();
    await user.click(screen.getByRole("button", { name: /Confirmar y guardar historial/ }));
    expect(historyClient.promoteHistoryImport).toHaveBeenCalledWith(original, listing, metadata.origen, metadata.zona_horaria, validPreview.dataset_sha256);
  });

  it("retries a failed library request and recovers without selecting a dataset", async () => {
    vi.mocked(apiClient.getDatasets).mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ total: 1, offset: 0, limit: 20, items: [dataset] });
    const user = userEvent.setup(); mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo cargar la biblioteca/);
    await user.click(screen.getByRole("button", { name: "Reintentar biblioteca" }));
    expect(await screen.findByText(/Historial · 1 sorteos/)).toBeInTheDocument();
    expect(apiClient.getDatasets).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("link", { name: /Usar este historial/ })).toBeInTheDocument();
  });

  it("requires exact explicit metadata confirmation and does not preview on mismatch", async () => {
    const user = userEvent.setup(); mount();
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(await screen.findByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Confirmá la fuente y la zona horaria/i);
    expect(historyClient.previewHistoryImport).not.toHaveBeenCalled();
  });
});

const library = () => screen.getByRole("region", { name: "Biblioteca de historiales" });
const importRegion = () => screen.getByRole("region", { name: "Importar historial" });
const advancedRegion = () => screen.getByRole("region", { name: "Más formas de importar" });
const follows = (first: HTMLElement, second: HTMLElement) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
const emptyLibrary = { total: 0, offset: 0, limit: 20, items: [] };
const primaries = () => Array.from(document.querySelectorAll<HTMLElement>(".btn-primary"));

describe("regions, resolved-state order and single dominant action", () => {
  it("shows Perfiles, Historiales, Importar and advanced options in task order", async () => {
    mount();
    await screen.findByText(/Historial · 1 sorteos/);
    const profiles = screen.getByRole("region", { name: "Perfiles de juego" });
    expect(profiles).toHaveAttribute("id", "perfiles");
    expect(library()).toHaveAttribute("id", "historiales");
    expect(follows(profiles, library())).toBe(true);
    expect(follows(library(), importRegion())).toBe(true);
    expect(follows(importRegion(), advancedRegion())).toBe(true);
    expect(within(importRegion()).queryByRole("list", { name: "Cómo importar el primer historial" })).not.toBeInTheDocument();
  });

  it("keeps Historiales before Importar and gives first-import guidance when empty", async () => {
    vi.mocked(apiClient.getDatasets).mockResolvedValue(emptyLibrary);
    mount();
    await screen.findByText(/Todavía no hay historiales guardados/);
    expect(follows(library(), importRegion())).toBe(true);
    expect(follows(importRegion(), advancedRegion())).toBe(true);
    const steps = within(importRegion()).getByRole("list", { name: "Cómo importar el primer historial" });
    expect(steps).toHaveTextContent(/perfil de juego/i);
    expect(within(importRegion()).getByLabelText("Reglas del juego")).toBeInTheDocument();
    expect(within(importRegion()).getByText("Importar guarda datos, no ejecuta ni calcula pagos.")).toBeInTheDocument();
  });

  it("keeps task sections in place while the first history list is pending", async () => {
    let resolveList!: (value: typeof emptyLibrary) => void;
    vi.mocked(apiClient.getDatasets).mockImplementationOnce(() => new Promise((resolve) => { resolveList = resolve; }));
    mount();
    expect(screen.getByText("Cargando historiales guardados…")).toHaveAttribute("role", "status");
    expect(library()).toBeInTheDocument();
    expect(importRegion()).toBeInTheDocument();
    expect(follows(library(), importRegion())).toBe(true);
    expect(screen.queryByText(/Todavía no hay historiales guardados/)).not.toBeInTheDocument();
    await act(async () => { resolveList(emptyLibrary); });
    expect(screen.queryByText("Cargando historiales guardados…")).not.toBeInTheDocument();
    expect(follows(library(), importRegion())).toBe(true);
    expect(follows(importRegion(), advancedRegion())).toBe(true);
  });

  it("does not present loading as an empty library and offers the import form once resolved", async () => {
    let resolveList!: (value: typeof emptyLibrary) => void;
    vi.mocked(apiClient.getDatasets).mockImplementationOnce(() => new Promise((resolve) => { resolveList = resolve; }));
    mount();
    expect(screen.getByText("Cargando historiales guardados…")).toHaveAttribute("role", "status");
    expect(screen.queryByText(/Todavía no hay historiales guardados/)).not.toBeInTheDocument();
    await act(async () => { resolveList(emptyLibrary); });
    expect(screen.getByLabelText("Archivo del historial (hasta 32 MB)")).toBeEnabled();
    expect(screen.getByText(/Todavía no hay historiales guardados/)).toBeInTheDocument();
  });

  it("keeps cause and retry for a list failure and never shows it as an empty library", async () => {
    vi.mocked(apiClient.getDatasets).mockRejectedValueOnce(new Error("offline"));
    mount();
    expect(await screen.findByRole("region", { name: "Biblioteca de historiales" })).toBeInTheDocument();
    expect(within(library()).getByRole("alert")).toHaveTextContent(/No se pudo cargar la biblioteca/);
    expect(follows(library(), importRegion())).toBe(true);
    expect(within(library()).getByRole("button", { name: "Reintentar biblioteca" })).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay historiales guardados/)).not.toBeInTheDocument();
    expect(within(importRegion()).queryByRole("list", { name: "Cómo importar el primer historial" })).not.toBeInTheDocument();
  });

  it("keeps the decided order after the first import refreshes an empty library", async () => {
    vi.mocked(apiClient.getDatasets).mockResolvedValueOnce(emptyLibrary);
    const user = userEvent.setup(); mount();
    await screen.findByText(/Todavía no hay historiales guardados/);
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(screen.getByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: /Importar historial/i }));
    await user.click(await screen.findByRole("button", { name: /Confirmar y guardar historial/i }));
    expect(await screen.findByText(/Historial · 1 sorteos/)).toBeInTheDocument();
    expect(follows(library(), importRegion())).toBe(true);
  });

  it("keeps the pagination controls mounted while the next page loads", async () => {
    let resolveNext!: (value: { total: number; offset: number; limit: number; items: typeof dataset[] }) => void;
    vi.mocked(apiClient.getDatasets).mockImplementation((offset = 0) => offset === 0
      ? Promise.resolve({ total: 21, offset, limit: 20, items: [dataset] })
      : new Promise((resolve) => { resolveNext = resolve; }));
    const user = userEvent.setup(); mount();
    const next = await screen.findByRole("button", { name: "Siguiente" });
    await user.click(next);
    expect(screen.getByRole("button", { name: "Siguiente" })).toBe(next);
    expect(screen.getByRole("navigation", { name: "Páginas de historiales" })).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay historiales guardados/)).not.toBeInTheDocument();
    await act(async () => { resolveNext({ total: 21, offset: 20, limit: 20, items: [dataset] }); });
    expect(screen.getByText("21–21 de 21")).toBeInTheDocument();
  });

  it("offers no continuation link and explains why when the saved profile no longer allows it", async () => {
    vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [{ ...dataset,
      profile_execution: { ...dataset.profile_execution, ready: false } }] });
    mount();
    await screen.findByText(/Historial · 1 sorteos/);
    expect(screen.queryByRole("link", { name: /Usar este historial/ })).not.toBeInTheDocument();
    expect(within(library()).getByText(/ya no están guardadas/i)).toBeInTheDocument();
  });

  it("keeps profile creation available while confirmation replaces the history import action", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByText(/Historial · 1 sorteos/);
    expect(screen.getByRole("button", { name: "Importar historial" })).toBeVisible();
    expect(primaries().map((item) => item.textContent)).toEqual(["Importar historial"]);
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(screen.getByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    await user.selectOptions(screen.getByLabelText("Reglas del juego"), "local@1");
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la fuente/ }));
    await user.click(screen.getByRole("checkbox", { name: /Confirmo la zona horaria/ }));
    await user.click(screen.getByRole("button", { name: "Importar historial" }));
    await screen.findByRole("button", { name: /Confirmar y guardar historial/i });
    expect(primaries().map((item) => item.textContent)).toEqual(["Confirmar y guardar historial"]);
    expect(screen.queryByRole("button", { name: "Importar historial" })).not.toBeInTheDocument();
  });

  it("wraps each confirmation in a control-choice label and explains why import is not yet available", async () => {
    const user = userEvent.setup(); mount();
    const submit = await screen.findByRole("button", { name: "Importar historial" });
    expect(submit).toBeDisabled();
    expect(submit).toHaveAccessibleDescription(/archivo/i);
    const raw = JSON.stringify({ metadata, sorteos_por_fecha: {} });
    await user.upload(screen.getByLabelText("Archivo del historial (hasta 32 MB)"), new File([raw], "history.json"));
    await screen.findByText(/Juego: Juego/);
    for (const name of [/Confirmo la fuente/, /Confirmo la zona horaria/]) {
      expect(screen.getByRole("checkbox", { name }).closest("label")).toHaveClass("control-choice");
    }
    expect(submit).toHaveAccessibleDescription(/perfil/i);
  });
});
