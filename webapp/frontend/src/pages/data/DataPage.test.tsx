import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
// Contract coverage: F-LIST-038–F-LIST-048 — task-order/profile discovery and import, explicit source/context, preview hash gate, stale/pending promotion, quota/conflict uncertainty, file-size validation and accessible first-error focus.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import { DataPage } from "./index";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getProfiles: vi.fn(), getDatasets: vi.fn(), registerProfile: vi.fn(), previewImport: vi.fn(), promoteImport: vi.fn() } };
});
const hash = "a".repeat(64);
const readiness = { ready: true, selector_capabilities: ["static-numbers/v1"], staking_capabilities: ["flat-per-number/v1"], entry_policies: ["all_rows/v1"], settlements: ["all", "best"] as const, requires_compatible_dataset: true };
const profile = { schema_version: 1, profile_id: "saved", revision: 2, universe_size: 100, positions: 2,
  allows_repeats: true, multipliers: [{ numerator: 80, denominator: 1 }, { numerator: 8, denominator: 1 }],
  currency: "DOP", scale: 0, stake_increment: 1, minimum_stake: 1, maximum_stake: 100,
  max_coverage: 50, max_exposure: 500, best_rule: "maximum-payout/v1" as const };
const valid = { promotable: true, source_sha256: "b".repeat(64), dataset_sha256: hash,
  rows_seen: 2, records_total: 1, duplicates_merged: 1, error_count: 0, errors_truncated: false,
  errors: [], sample: [{ date: "2025-01-01", time: "10:30", numbers: [1, 2] }], execution_supported: false as const };
const file = () => new File([new Uint8Array([0, 255, 10])], "draws.csv", { type: "text/csv" });

async function setup() {
  const user = userEvent.setup();
  render(<DataPage />);
  await user.click(screen.getByText("Importar archivo CSV o JSON"));
  await user.click(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ }));
  await screen.findByLabelText("Perfil guardado completo");
  await user.upload(screen.getByLabelText(/Archivo de datos/), file());
  await user.selectOptions(screen.getByLabelText(/Formato del archivo/), "csv");
  await user.selectOptions(screen.getByLabelText("Interpretación de la hora"), "naive_legacy");
  await user.selectOptions(screen.getByLabelText("Perfil guardado completo"), "saved@2");
  await user.type(screen.getByLabelText("Identificador de fuente"), "ledger");
  await user.type(screen.getByLabelText("Revisión o corrección"), "r1");
  await user.type(screen.getByLabelText("Procedencia de los datos"), "manual");
  return user;
}
async function preview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
  return screen.findByRole("heading", { name: /Vista previa/ });
}

beforeEach(() => {
  vi.mocked(apiClient.getProfiles).mockReset().mockResolvedValue({ total: 1, offset: 0, limit: 100,
    items: [{ profile, profile_sha256: hash, profile_execution: readiness, execution_supported: false }], templates: [{ name: "Example", provenance: "reference",
      known_fields: { positions: 2 }, missing_fields: ["profile_id"], execution_supported: false }] });
  vi.mocked(apiClient.getDatasets).mockReset().mockResolvedValue({ total: 0, offset: 0, limit: 20, items: [] });
  vi.mocked(apiClient.registerProfile).mockReset();
  vi.mocked(apiClient.previewImport).mockReset().mockResolvedValue(valid);
  vi.mocked(apiClient.promoteImport).mockReset().mockResolvedValue({ dataset_sha256: hash, created_at: "2025-01-01T00:00:00Z",
    created: true, duplicate_source_differs: false, retained_source_sha256: valid.source_sha256,
    submitted_source_sha256: valid.source_sha256, rows_seen: 2, records_total: 1,
    duplicates_merged: 1, execution_supported: false });
});

describe("import mode presentation", () => {
  it("keeps both modes in the same segmented radio group and advanced content disclosure", async () => {
    render(<DataPage />);
    const group = await screen.findByRole("group", { name: "Tipo de importación" });
    expect(within(group).getByRole("radio", { name: /Historial ordinario/ })).toBeChecked();
    expect(within(group).getByRole("radio", { name: /Archivo avanzado CSV o JSON/ })).not.toBeChecked();
    expect(screen.getByText("Importar archivo CSV o JSON").closest("details")).not.toHaveAttribute("open");
  });
});

describe("visible game profiles", () => {
  it("shows profile creation before import and opens it without an advanced disclosure", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 0, offset: 0, limit: 100, items: [], templates: [] });
    render(<DataPage />);
    const profiles = await screen.findByRole("region", { name: "Perfiles de juego" });
    const create = within(profiles).getByRole("button", { name: "Crear perfil" });
    expect(create).toBeVisible();
    const importing = await screen.findByRole("region", { name: "Importar historial" });
    expect(profiles.compareDocumentPosition(importing) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText("Importar archivo CSV o JSON")?.closest("details")).not.toHaveAttribute("open");
    await userEvent.setup().click(create);
    expect(screen.getByLabelText(/Tamaño del universo/)).toBeVisible();
  });

  it("distinguishes history import from the advanced file-import path", async () => {
    render(<DataPage />);
    const library = await screen.findByRole("region", { name: "Biblioteca de historiales" });
    expect(within(library).getByRole("status")).toHaveTextContent(/Todavía no hay historiales guardados/);
    expect(within(library).getByRole("link", { name: "Ir a importar historial" })).toHaveAttribute("href", "#import-entry-title");
    expect(screen.getByRole("heading", { name: "Importar historial" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar historial" })).toBeDisabled();
    expect(screen.getByRole("heading", { name: "Más formas de importar" })).toBeInTheDocument();
    expect(screen.getByText("Importar archivo CSV o JSON")).toBeInTheDocument();
  });

  it("offers profile creation in context when importing without a saved profile", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 0, offset: 0, limit: 100, items: [], templates: [] });
    render(<DataPage />);
    const importing = await screen.findByRole("region", { name: "Importar historial" });
    expect(within(importing).getByRole("button", { name: "Crear perfil" })).toBeVisible();
    expect(within(importing).getByRole("link", { name: /Ver Perfiles de juego/ })).toHaveAttribute("href", "#perfiles");
  });

  it("makes the empty-state create-profile actions primary", async () => {
    vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 0, offset: 0, limit: 100, items: [], templates: [] });
    render(<DataPage />);
    const importing = await screen.findByRole("region", { name: "Importar historial" });
    expect(within(importing).getByRole("button", { name: "Crear perfil" })).toHaveClass("btn-primary");
  });

  it("offers a retry for failed profile loads in both sections and re-runs the profiles fetch", async () => {
    vi.mocked(apiClient.getProfiles).mockRejectedValueOnce(new NetworkError());
    const user = userEvent.setup();
    render(<DataPage />);
    const importing = await screen.findByRole("region", { name: "Importar historial" });
    const retryInImport = await within(importing).findByRole("button", { name: "Reintentar perfiles" });
    expect(within(screen.getByRole("region", { name: "Perfiles de juego" })).getByRole("button", { name: "Reintentar perfiles" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Reintentar perfiles" })).toHaveLength(2);
    expect(apiClient.getProfiles).toHaveBeenCalledTimes(1);
    await user.click(retryInImport);
    await waitFor(() => expect(apiClient.getProfiles).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryAllByRole("button", { name: "Reintentar perfiles" })).toHaveLength(0));
  });
});

describe("bounded local import", () => {
  it("selects a newly registered profile for import and invalidates an earlier preview", async () => {
    const user = await setup();
    await preview(user);
    const created = { ...profile, profile_id: "new-profile", revision: 1, positions: 1, multipliers: [{ numerator: 1, denominator: 1 }] };
    vi.mocked(apiClient.registerProfile).mockResolvedValueOnce({ profile: created, profile_sha256: hash,
      profile_execution: readiness, execution_supported: false });
    await user.click(within(screen.getByRole("region", { name: "Perfiles de juego" })).getByRole("button", { name: "Crear perfil" }));
    await user.clear(screen.getByLabelText("ID nuevo del perfil"));
    await user.type(screen.getByLabelText("ID nuevo del perfil"), "new-profile");
    await user.clear(screen.getByLabelText(/Posiciones por sorteo/));
    await user.type(screen.getByLabelText(/Posiciones por sorteo/), "1");
    await user.clear(screen.getByLabelText("Posición 1 · premio por unidad apostada"));
    await user.type(screen.getByLabelText("Posición 1 · premio por unidad apostada"), "1");
    await user.clear(screen.getByLabelText(/Apuesta máxima/));
    await user.type(screen.getByLabelText(/Apuesta máxima/), "1");
    await user.clear(screen.getByLabelText(/Exposición máxima/));
    await user.type(screen.getByLabelText(/Exposición máxima/), "1");
    await user.clear(screen.getByLabelText(/Cobertura máxima/));
    await user.type(screen.getByLabelText(/Cobertura máxima/), "1");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await waitFor(() => expect(screen.getByLabelText("Perfil guardado completo")).toHaveValue("new-profile@1"));
    expect(screen.queryByRole("heading", { name: /Vista previa/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Columna de posición 1")).toHaveValue("pos1");
    expect(screen.queryByLabelText("Columna de posición 2")).not.toBeInTheDocument();
    await preview(user);
    expect(apiClient.previewImport).toHaveBeenLastCalledWith(expect.objectContaining({ profile: created }));
  // This multi-step profile/import flow needs headroom under full-suite worker contention.
  }, 15_000);

  it("uses persisted profiles only and sends original bytes with explicit context, then confirms saved hash", async () => {
    const user = await setup();
    expect(screen.queryByRole("option", { name: /Example/ })).not.toBeInTheDocument();
    expect(screen.getByText(/plantillas de catálogo son parciales/i)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Tipo de fuente"), "artificial");
    await user.selectOptions(screen.getByLabelText("Interpretación de la hora"), "iana");
    await user.type(screen.getByLabelText("Zona horaria (ej. America/Santo_Domingo)"), "America/Santo_Domingo");
    await user.clear(screen.getByLabelText("Columna de posición 1"));
    await user.type(screen.getByLabelText("Columna de posición 1"), "first");
    await preview(user);
    await user.click(screen.getAllByText("Detalles técnicos").at(-1)!);
    expect(within(screen.getByRole("region", { name: /Vista previa/ })).getByText("Importar guarda datos, no ejecuta ni calcula pagos.")).toBeInTheDocument();
    expect(apiClient.previewImport).toHaveBeenCalledWith({ raw_base64: "AP8K", format: "csv",
      mapping: { date: "date", time: "time", positions: ["first", "pos2"] },
      source: { source_id: "ledger", kind: "artificial", revision: "r1", provenance: "manual" },
      clock: { mode: "iana", zone: "America/Santo_Domingo" }, profile });
    expect(screen.getByText(/Filas leídas: 2/)).toHaveTextContent(/Duplicados: 1/);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("heading", { name: "Importación guardada" })).toBeInTheDocument();
    await user.click(screen.getAllByText("Detalles técnicos").at(-1)!);
    expect(screen.getByText(/Identidad canónica \(SHA-256\):/)).toHaveTextContent(hash);
    expect(screen.getAllByText("Importar guarda datos, no ejecuta ni calcula pagos.")).toHaveLength(2);
    expect(apiClient.promoteImport).toHaveBeenCalledWith({ ...vi.mocked(apiClient.previewImport).mock.calls[0][0], expected_dataset_sha256: hash });
  });

  it("requires deliberate format and clock choices and supports JSON without altering raw bytes", async () => {
    const user = userEvent.setup();
    render(<DataPage />);
    await user.click(screen.getByText("Importar archivo CSV o JSON"));
    await user.click(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ }));
    await screen.findByLabelText("Perfil guardado completo");
    await user.upload(screen.getByLabelText(/Archivo de datos/), file());
    await user.selectOptions(screen.getByLabelText("Perfil guardado completo"), "saved@2");
    await user.type(screen.getByLabelText("Identificador de fuente"), "ledger");
    await user.type(screen.getByLabelText("Revisión o corrección"), "r1");
    await user.type(screen.getByLabelText("Procedencia de los datos"), "manual");
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Elegí el formato del archivo/);
    expect(apiClient.previewImport).not.toHaveBeenCalled();
    await user.selectOptions(screen.getByLabelText(/Formato del archivo/), "json");
    await user.selectOptions(screen.getByLabelText("Interpretación de la hora"), "naive_legacy");
    await preview(user);
    expect(apiClient.previewImport).toHaveBeenCalledWith(expect.objectContaining({ raw_base64: "AP8K", format: "json", clock: { mode: "naive_legacy", zone: null } }));
  });

  it("shows invalid preview and blocks promotion without a valid hash", async () => {
    vi.mocked(apiClient.previewImport).mockResolvedValue({ ...valid, promotable: false, dataset_sha256: null,
      error_count: 1, errors: [{ row: 2, code: "date", message: "date must be YYYY-MM-DD" }], sample: [] });
    const user = await setup();
    await preview(user);
    expect(screen.getByText(/Fila 2: date must be YYYY-MM-DD/)).toBeInTheDocument();
    await user.click(screen.getAllByText("Detalles técnicos").at(-1)!);
    expect(screen.getByText("Fila 2 · date")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirmar y guardar importación" })).toBeDisabled();
    expect(apiClient.promoteImport).not.toHaveBeenCalled();
  });

  it("rejects an inconsistent promotable response without a valid dataset hash", async () => {
    vi.mocked(apiClient.previewImport).mockResolvedValue({ ...valid, dataset_sha256: "not-a-hash" });
    const user = await setup();
    await preview(user);
    expect(screen.getByRole("button", { name: "Confirmar y guardar importación" })).toBeDisabled();
    expect(apiClient.promoteImport).not.toHaveBeenCalled();
  });

  it("allows a fresh preview after a context change while the old request hangs; stale finalizers cannot clear newer busy state", async () => {
    let resolveOld!: (value: typeof valid) => void;
    let resolveNew!: (value: typeof valid) => void;
    vi.mocked(apiClient.previewImport)
      .mockImplementationOnce(() => new Promise((done) => { resolveOld = done; }))
      .mockImplementationOnce(() => new Promise((done) => { resolveNew = done; }));
    const user = await setup();
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    await waitFor(() => expect(apiClient.previewImport).toHaveBeenCalledTimes(1));
    await user.type(screen.getByLabelText("Revisión o corrección"), "2");
    expect(screen.queryByRole("status", { name: /Validando/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    await waitFor(() => expect(apiClient.previewImport).toHaveBeenCalledTimes(2));
    expect(vi.mocked(apiClient.previewImport).mock.calls[1][0].source.revision).toBe("r12");
    await act(async () => { resolveOld(valid); });
    expect(screen.getByText("Validando archivo…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar vista previa" })).toBeDisabled();
    expect(screen.queryByRole("heading", { name: /Vista previa/ })).not.toBeInTheDocument();
    await act(async () => { resolveNew({ ...valid, rows_seen: 3 }); });
    expect(screen.getByText(/Filas leídas: 3/)).toBeInTheDocument();
    await user.upload(screen.getByLabelText(/Archivo de datos/), new File(["changed"], "other.csv"));
    expect(screen.queryByRole("button", { name: "Confirmar y guardar importación" })).not.toBeInTheDocument();
    expect(apiClient.promoteImport).not.toHaveBeenCalled();
  });

  it("keeps a pending promotion locked and honestly unconfirmed until it settles, without duplicate submission", async () => {
    let resolve!: (value: Awaited<ReturnType<typeof apiClient.promoteImport>>) => void;
    vi.mocked(apiClient.promoteImport).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const user = await setup();
    await preview(user);
    const confirm = screen.getByRole("button", { name: "Confirmar y guardar importación" });
    fireEvent.click(confirm); fireEvent.click(confirm);
    expect(apiClient.promoteImport).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Tipo de fuente")).toBeDisabled();
    expect(screen.getByLabelText(/Archivo de datos/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generar vista previa" })).toBeDisabled();
    expect(confirm).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Historial ordinario/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Historial ordinario/ }));
    expect(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ })).toBeChecked();
    expect(screen.getByText(/esperá la respuesta/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Importación guardada" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Tipo de fuente"), { target: { value: "artificial" } });
    expect(screen.getByLabelText("Tipo de fuente")).toHaveValue("historical");
    await act(async () => { resolve({ dataset_sha256: hash, created_at: "now", created: true,
      duplicate_source_differs: false, retained_source_sha256: hash, submitted_source_sha256: hash,
      rows_seen: 2, records_total: 1, duplicates_merged: 1, execution_supported: false }); });
    expect(screen.getByRole("heading", { name: "Importación guardada" })).toBeInTheDocument();
    expect(apiClient.promoteImport).toHaveBeenCalledTimes(1);
  });

  it("reports 409 quota/conflict and clears preview; duplicate outcome remains explicit", async () => {
    vi.mocked(apiClient.promoteImport).mockRejectedValueOnce(new ApiError(409, "dataset quota has insufficient headroom"))
      .mockResolvedValueOnce({ dataset_sha256: hash, created_at: "now", created: false,
        duplicate_source_differs: true, retained_source_sha256: "c".repeat(64), submitted_source_sha256: "b".repeat(64),
        rows_seen: 2, records_total: 1, duplicates_merged: 1, execution_supported: false });
    const user = await setup();
    await preview(user);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no hay espacio/i);
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Confirmar y guardar importación" })).not.toBeInTheDocument();
    await preview(user);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("heading", { name: "Historial ya guardado" })).toBeInTheDocument();
    expect(screen.getByText(/otro archivo de origen/)).toBeInTheDocument();
    await user.click(screen.getAllByText("Detalles técnicos").at(-1)!);
    expect(screen.getByText(/Identidad canónica \(SHA-256\):/)).toHaveTextContent(hash);
    expect(screen.getByText(/Archivo retenido \(SHA-256\):/)).toHaveTextContent("c".repeat(64));
    expect(screen.getByText(/Archivo enviado \(SHA-256\):/)).toHaveTextContent("b".repeat(64));
  });

  it("rejects over-2-MiB file without reading/sending it and focuses the error", async () => {
    const user = await setup();
    await user.upload(screen.getByLabelText(/Archivo de datos/),
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "huge.csv"));
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/2 MiB/);
    // Field-level validation lands on the invalid field, linked to the error; server failures keep focusing the alert.
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveFocus();
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveAttribute("aria-describedby", screen.getByRole("alert").id);
    expect(apiClient.previewImport).not.toHaveBeenCalled();
  });

  it("opens a collapsed advanced disclosure on validation failure, keeps typed values and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    render(<DataPage />);
    const summary = screen.getByText("Importar archivo CSV o JSON");
    const details = summary.closest("details") as HTMLDetailsElement;
    await user.click(summary);
    await user.click(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ }));
    await screen.findByLabelText("Perfil guardado completo");
    await user.type(screen.getByLabelText("Identificador de fuente"), "ledger");
    details.open = false;
    expect(details.open).toBe(false);
    fireEvent.submit(screen.getByRole("form", { name: "Importar datos" }));
    expect(details.open).toBe(true);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/Elegí un archivo CSV o JSON/);
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveFocus();
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveAttribute("aria-describedby", alert.id);
    expect(screen.getByLabelText("Identificador de fuente")).toHaveValue("ledger");
    expect(apiClient.previewImport).not.toHaveBeenCalled();
  });

  it("points at the first field that fails a later check, not the first field of the form", async () => {
    const user = await setup();
    await user.clear(screen.getByLabelText("Revisión o corrección"));
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    expect(screen.getByLabelText("Revisión o corrección")).toHaveFocus();
    expect(screen.getByLabelText("Revisión o corrección")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Identificador de fuente")).not.toHaveAttribute("aria-invalid");
    await user.type(screen.getByLabelText("Revisión o corrección"), "r1");
    expect(screen.getByLabelText("Revisión o corrección")).not.toHaveAttribute("aria-invalid");
  });

  it("does not assume an uncertain network promotion failed and never retries automatically", async () => {
    vi.mocked(apiClient.promoteImport).mockRejectedValueOnce(new NetworkError());
    const user = await setup(); await preview(user);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo contactar al servidor para guardar el archivo/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/Iniciá el laboratorio desde el lanzador y volvé a intentar/);
    expect(apiClient.promoteImport).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Confirmar y guardar importación" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar vista previa" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Historial ordinario/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Historial ordinario/ }));
    expect(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ })).toBeChecked();
    expect(screen.getByText(/Comprobá el estado desde la cola o la biblioteca/)).toBeVisible();
  });

  it("uses one shared form and retains native drafts and hash-bound previews across explicit mode switches", async () => {
    const user = await setup();
    const form = screen.getByRole("form", { name: "Importar datos" });
    expect(document.querySelectorAll("form form")).toHaveLength(0);
    expect(screen.getAllByRole("form", { name: "Importar datos" })).toHaveLength(1);
    expect(within(form).queryByRole("button", { name: "Importar historial" })).not.toBeInTheDocument();
    await preview(user);
    await user.click(screen.getByRole("radio", { name: /Historial ordinario/ }));
    expect(within(form).getByRole("button", { name: "Importar historial" })).toBeVisible();
    expect(within(form).queryByRole("button", { name: "Generar vista previa" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Archivo avanzado CSV o JSON/ }));
    expect(screen.getByLabelText("Identificador de fuente")).toHaveValue("ledger");
    expect(screen.getByLabelText(/Archivo de datos/)).toHaveProperty("files", expect.objectContaining({ length: 1 }));
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(apiClient.promoteImport).toHaveBeenCalledWith({ ...vi.mocked(apiClient.previewImport).mock.calls[0][0], expected_dataset_sha256: hash });
  });
});
