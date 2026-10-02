import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
  await user.click(screen.getByText(/Importación avanzada/));
  await screen.findByLabelText("Perfil guardado completo");
  await user.upload(screen.getByLabelText(/Archivo local CSV o JSON/), file());
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

describe("bounded local import", () => {
  it("selects a newly registered profile for import and invalidates an earlier preview", async () => {
    const user = await setup();
    await preview(user);
    const created = { ...profile, profile_id: "new-profile", revision: 1, positions: 1, multipliers: [{ numerator: 1, denominator: 1 }] };
    vi.mocked(apiClient.registerProfile).mockResolvedValueOnce({ profile: created, profile_sha256: hash,
      profile_execution: readiness, execution_supported: false });
    await user.click(screen.getByRole("button", { name: "Crear perfil" }));
    await user.type(screen.getByLabelText("ID nuevo del perfil"), "new-profile");
    await user.type(screen.getByLabelText(/Revisión \(1/), "1");
    await user.type(screen.getByLabelText(/Tamaño del universo/), "100");
    await user.type(screen.getByLabelText(/Posiciones por sorteo/), "1");
    await user.selectOptions(screen.getByLabelText(/Se repiten números/), "yes");
    await user.type(screen.getByLabelText("Posición 1 · multiplicador"), "1");
    await user.type(screen.getByLabelText(/Moneda \(código/), "DOP");
    await user.type(screen.getByLabelText(/Escala decimal/), "0");
    for (const label of [/Incremento de apuesta/, /Apuesta mínima/, /Apuesta máxima/, /Exposición máxima/]) await user.type(screen.getByLabelText(label), "1");
    await user.type(screen.getByLabelText(/Cobertura máxima/), "1");
    await user.click(screen.getByRole("button", { name: "Registrar perfil inmutable" }));
    await waitFor(() => expect(screen.getByLabelText("Perfil guardado completo")).toHaveValue("new-profile@1"));
    expect(screen.queryByRole("heading", { name: /Vista previa/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Columna de posición 1")).toHaveValue("pos1");
    expect(screen.queryByLabelText("Columna de posición 2")).not.toBeInTheDocument();
    await preview(user);
    expect(apiClient.previewImport).toHaveBeenLastCalledWith(expect.objectContaining({ profile: created }));
  });

  it("uses persisted profiles only and sends original bytes with explicit context, then confirms saved hash", async () => {
    const user = await setup();
    expect(screen.queryByRole("option", { name: /Example/ })).not.toBeInTheDocument();
    expect(screen.getByText(/plantillas de catálogo son parciales/i)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Tipo de fuente"), "artificial");
    await user.selectOptions(screen.getByLabelText("Interpretación de la hora"), "iana");
    await user.type(screen.getByLabelText(/Zona IANA/), "America/Santo_Domingo");
    await user.clear(screen.getByLabelText("Columna de posición 1"));
    await user.type(screen.getByLabelText("Columna de posición 1"), "first");
    await preview(user);
    expect(screen.getByText(/El archivo queda guardado en la biblioteca local y puede abrirse desde «Continuar con este historial»; esta importación aún no habilita su ejecución/i)).toBeInTheDocument();
    expect(apiClient.previewImport).toHaveBeenCalledWith({ raw_base64: "AP8K", format: "csv",
      mapping: { date: "date", time: "time", positions: ["first", "pos2"] },
      source: { source_id: "ledger", kind: "artificial", revision: "r1", provenance: "manual" },
      clock: { mode: "iana", zone: "America/Santo_Domingo" }, profile });
    expect(screen.getByText(/Filas leídas: 2/)).toHaveTextContent("Duplicados idénticos unidos: 1");
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("heading", { name: "Importación guardada" })).toBeInTheDocument();
    expect(screen.getByText(/Hash guardado:/)).toHaveTextContent(hash);
    expect(screen.getByText(/Este artefacto no se puede ejecutar todavía/i)).toBeInTheDocument();
    expect(apiClient.promoteImport).toHaveBeenCalledWith({ ...vi.mocked(apiClient.previewImport).mock.calls[0][0], expected_dataset_sha256: hash });
  });

  it("requires deliberate format and clock choices and supports JSON without altering raw bytes", async () => {
    const user = userEvent.setup();
    render(<DataPage />);
    await user.click(screen.getByText(/Importación avanzada/));
    await screen.findByLabelText("Perfil guardado completo");
    await user.upload(screen.getByLabelText(/Archivo local CSV o JSON/), file());
    await user.selectOptions(screen.getByLabelText("Perfil guardado completo"), "saved@2");
    await user.type(screen.getByLabelText("Identificador de fuente"), "ledger");
    await user.type(screen.getByLabelText("Revisión o corrección"), "r1");
    await user.type(screen.getByLabelText("Procedencia de los datos"), "manual");
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Elegí explícitamente/);
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
    expect(screen.getByText(/Fila 2 · date/)).toBeInTheDocument();
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
    await user.upload(screen.getByLabelText(/Archivo local CSV o JSON/), new File(["changed"], "other.csv"));
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
    expect(screen.getByLabelText(/Archivo local CSV o JSON/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generar vista previa" })).toBeDisabled();
    expect(confirm).toBeDisabled();
    expect(screen.getByText(/respuesta pendiente/)).toBeInTheDocument();
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
    expect(await screen.findByRole("alert")).toHaveTextContent(/cuota/i);
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Confirmar y guardar importación" })).not.toBeInTheDocument();
    await preview(user);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("heading", { name: "Dataset ya guardado" })).toBeInTheDocument();
    expect(screen.getByText(/bytes de origen diferentes/)).toBeInTheDocument();
  });

  it("rejects over-2-MiB file without reading/sending it and focuses the error", async () => {
    const user = await setup();
    await user.upload(screen.getByLabelText(/Archivo local CSV o JSON/),
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "huge.csv"));
    await user.click(screen.getByRole("button", { name: "Generar vista previa" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/2 MiB/);
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(apiClient.previewImport).not.toHaveBeenCalled();
  });

  it("does not assume an uncertain network promotion failed and never retries automatically", async () => {
    vi.mocked(apiClient.promoteImport).mockRejectedValueOnce(new NetworkError());
    const user = await setup(); await preview(user);
    await user.click(screen.getByRole("button", { name: "Confirmar y guardar importación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/podría haber llegado/i);
    expect(apiClient.promoteImport).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Confirmar y guardar importación" })).not.toBeInTheDocument();
  });
});
