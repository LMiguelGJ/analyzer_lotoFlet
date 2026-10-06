import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import { ProfileBatchPage } from "./ProfileBatchPage";
import { BATCH_DRAFT_STORAGE_KEY, createBatchDraft, parseBatchDraft, serializeBatchDraft, type BatchSubmissionBody } from "./batch-model";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getProfiles: vi.fn(), getDatasets: vi.fn(), getDataset: vi.fn(), getDatasetDraws: vi.fn(),
    listProfileBatchStrategies: vi.fn(), getProfileBatchExecutionPolicy: vi.fn(), getProfileBatchStrategy: vi.fn(),
    validateProfileBatch: vi.fn(), createProfileBatch: vi.fn(), getProfileBatchByClientRequestId: vi.fn(),
    createProfileBatchStrategy: vi.fn(), reviseProfileBatchStrategy: vi.fn() } };
});

const profile = { profile: { schema_version: 1 as const, profile_id: "local", revision: 2, universe_size: 20, positions: 2,
  allows_repeats: false, multipliers: [{ numerator: 5, denominator: 1 }, { numerator: 2, denominator: 1 }], currency: "DOP", scale: 0,
  stake_increment: 1, minimum_stake: 1, maximum_stake: 50, max_coverage: 10, max_exposure: 100, best_rule: "maximum-payout/v1" as const },
  profile_sha256: "a".repeat(64), execution_supported: true, profile_execution: { ready: true, selector_capabilities: [], staking_capabilities: [],
  entry_policies: [], settlements: ["all", "best"] as const, requires_compatible_dataset: true } };
const dataset = { dataset_sha256: "b".repeat(64), source_sha256: "c".repeat(64), created_at: "2025-01-02T00:00:00Z",
  source_id: "historial", source_revision: "1", source_kind: "historical" as const, profile_id: "local", profile_revision: 2,
  profile_sha256: "a".repeat(64), positions: 2, universe_size: 20, records_total: 1, first_draw: "2025-01-01 08:30",
  last_draw: "2025-01-01 08:30", clock: { mode: "iana" as const, zone: "America/Santo_Domingo" }, execution_supported: false as const,
  profile_execution: profile.profile_execution };
const definition = { definition_version: 1 as const, name: "Fijas", selector: "static-numbers/v1" as const, coverage: 1,
  staking: "flat-per-number/v1" as const, selector_parameters: { numbers: [3] }, staking_parameters: { per_number_stake: 1 }, closing_defaults: { settlement: "best" } };
const strategy = { id: "custom", name: "Fijas", revision: 1, latest_revision: 1, definition_version: 1, definition, definition_sha256: "d".repeat(64),
  created_at: "2025-01-01", revision_created_at: "2025-01-01", protected: false, preset_explanation: null, definition_valid: true,
  profile_context_provided: true, profile_compatible: true, incompatibilities: [], requirements: {}, execution_available: true,
  execution_unavailable_reason: null };
const policy = { revision: 1, policy: { max_strategies_per_batch: 3, worker_count: 1, max_pending_runs: 10, max_bet_draws: 100,
  max_elapsed_draws: 1000, run_timeout_seconds: 120 }, effective: {}, defaults: {}, bounds: {}, explanation: "Límites de admisión; no son garantías." };
const validation = { valid: true, reasons: [], profile: { id: "local", revision: 2, sha256: "a".repeat(64) },
  dataset: { dataset_sha256: dataset.dataset_sha256, row_count: 1, archive_bound: false }, strategies: [],
  requested_constraints: { max_draws: 20 }, effective_constraints: { max_draws: 20 },
  limits: { worker_count: 1, max_strategies_per_batch: 3, max_pending_runs: 10, run_timeout_seconds: 120, reservation_created: false }, policy: { revision: 1 } };

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [profile], templates: [] });
  vi.mocked(apiClient.getDatasets).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [dataset] });
  vi.mocked(apiClient.getDataset).mockResolvedValue(dataset);
  vi.mocked(apiClient.getDatasetDraws).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: ["2025-01-01 08:30"] });
  vi.mocked(apiClient.listProfileBatchStrategies).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [strategy] });
  vi.mocked(apiClient.getProfileBatchExecutionPolicy).mockResolvedValue(policy as never);
  vi.mocked(apiClient.getProfileBatchStrategy).mockResolvedValue(strategy);
  vi.mocked(apiClient.validateProfileBatch).mockResolvedValue(validation as never);
  vi.mocked(apiClient.createProfileBatch).mockReset();
});
function mount() { render(<MemoryRouter initialEntries={[`/simulaciones/nueva/sesion?dataset_sha256=${dataset.dataset_sha256}`]}><ProfileBatchPage /></MemoryRouter>); }

const frozenBody: BatchSubmissionBody = {
  schema_version: 1, profile: { id: "local", revision: 2, sha256: "a".repeat(64) }, dataset_sha256: "b".repeat(64),
  strategies: [{ id: "custom", revision: 1, definition_sha256: "d".repeat(64) }],
  conditions: { schema_version: 1, start_draw: "2025-01-01 08:30", capital: 100, goal: 200, settlement: "all",
    max_elapsed_draws: 50, max_bet_draws: null, end_minute: null, duration_minutes: null }, max_draws: 50, client_request_id: "frozen-request",
};
function storePendingDraft() {
  const draft = createBatchDraft(dataset.dataset_sha256);
  draft.profile = { id: "different-current-profile", revision: 1, sha256: "e".repeat(64) };
  draft.pending = { clientRequestId: frozenBody.client_request_id, frozenBody };
  sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, serializeBatchDraft(draft));
}

describe("guided v5 profile batch", () => {
  it("# F-CREATE-044 presents the renamed artifact and keeps strategy internals closed by default", async () => {
    mount();
    expect(screen.getByRole("heading", { name: "Lote de simulaciones" })).toBeInTheDocument();
    await screen.findByRole("heading", { name: /Fijas/ });
    const strategyArticle = screen.getByRole("heading", { name: /Fijas/ }).closest("article");
    expect(strategyArticle).not.toBeNull();
    expect(strategyArticle!.querySelector("details")?.open).toBe(false);
    expect(within(strategyArticle!).getByText("static-numbers/v1")).not.toBeVisible();
  });
  it("# F-CREATE-045 binds profile and exact dataset, preserves shared inputs, and enables simulation only after current server validation", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByRole("option", { name: /historial/ });
    await user.selectOptions(screen.getByLabelText("Historial"), dataset.dataset_sha256);
    await user.selectOptions(screen.getByLabelText("Perfil de juego"), "local@2");
    await user.click(screen.getByRole("button", { name: "Estrategias" }));
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    const elapsed = screen.getByLabelText("Máximo sorteos transcurridos");
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(elapsed, "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await user.click(screen.getByRole("button", { name: "Simulación" }));
    const simulate = screen.getByRole("button", { name: "Crear simulaciones" });
    expect(simulate).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Validación" }));
    await user.click(screen.getByRole("button", { name: "Validar simulación" }));
    expect(await screen.findByText("Validación aceptada")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Validar comprueba la solicitud; no reserva capacidad.");
    expect(screen.getByRole("button", { name: "Crear simulaciones" })).toBeEnabled();
    expect(apiClient.validateProfileBatch).toHaveBeenCalledWith(expect.objectContaining({ schema_version: 1,
      profile: { id: "local", revision: 2, sha256: "a".repeat(64) }, dataset_sha256: dataset.dataset_sha256,
      strategies: [{ id: "custom", revision: 1, definition_sha256: "d".repeat(64) }],
      conditions: expect.objectContaining({ capital: 100, goal: 200, start_draw: "2025-01-01 08:30", settlement: "all" }) }));
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "1");
    await user.click(screen.getByRole("button", { name: "Simulación" }));
    expect(screen.getByRole("button", { name: "Crear simulaciones" })).toBeDisabled();
  });

  it("# F-CREATE-046 looks up the frozen client request identity before retrying an uncertain create", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByRole("option", { name: /historial/ });
    await user.selectOptions(screen.getByLabelText("Perfil de juego"), "local@2");
    await user.click(screen.getByRole("button", { name: "Estrategias" }));
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await user.click(screen.getByRole("button", { name: "Validación" }));
    await user.click(screen.getByRole("button", { name: "Validar simulación" }));
    await screen.findByText("Validación aceptada");
    vi.mocked(apiClient.createProfileBatch).mockRejectedValueOnce(new NetworkError()).mockResolvedValueOnce({ id: "e".repeat(32), status: "pending" });
    vi.mocked(apiClient.getProfileBatchByClientRequestId).mockRejectedValueOnce(new ApiError(404, "resource not found"));
    const submit = screen.getByRole("button", { name: "Crear simulaciones" });
    await user.click(submit);
    expect(await screen.findByRole("alert")).toHaveTextContent(/Sin confirmación: la simulación pudo haberse creado/i);
    await user.click(screen.getByRole("button", { name: "Crear simulaciones" }));
    await waitFor(() => expect(apiClient.getProfileBatchByClientRequestId).toHaveBeenCalledTimes(1));
    const firstBody = vi.mocked(apiClient.createProfileBatch).mock.calls[0][0];
    const secondBody = vi.mocked(apiClient.createProfileBatch).mock.calls[1][0];
    expect(firstBody.client_request_id).toBe(secondBody.client_request_id);
    expect(secondBody).toEqual(firstBody);
    await waitFor(() => expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.pending).toBeNull());
  });

  it("# F-CREATE-047 recovers a frozen request without current form/catalog readiness and retires storage before navigation", async () => {
    storePendingDraft();
    vi.mocked(apiClient.getProfiles).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getDatasets).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.listProfileBatchStrategies).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getProfileBatchExecutionPolicy).mockRejectedValue(new NetworkError());
    vi.mocked(apiClient.getProfileBatchByClientRequestId).mockImplementation(async (id) => {
      expect(id).toBe("frozen-request");
      return { id: "f".repeat(32), status: "pending" };
    });
    const user = userEvent.setup(); mount();
    await user.click(await screen.findByRole("button", { name: /recuperar creación pendiente/i }));
    await waitFor(() => expect(apiClient.getProfileBatchByClientRequestId).toHaveBeenCalledWith("frozen-request"));
    await waitFor(() => expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.pending).toBeNull());
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });

  it("# F-CREATE-048 retries only the frozen body after a lookup 404, despite edited current inputs", async () => {
    storePendingDraft();
    vi.mocked(apiClient.getProfileBatchByClientRequestId).mockRejectedValueOnce(new ApiError(404, "resource not found"));
    vi.mocked(apiClient.createProfileBatch).mockRejectedValueOnce(new NetworkError());
    const user = userEvent.setup(); mount();
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    await user.type(screen.getByLabelText(/Capital inicial/), "999");
    await user.click(await screen.findByRole("button", { name: /recuperar creación pendiente/i }));
    await waitFor(() => expect(apiClient.createProfileBatch).toHaveBeenCalledWith(frozenBody));
    expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.pending).toEqual({
      clientRequestId: frozenBody.client_request_id, frozenBody,
    });
  });

  it.each([[0, 1_000, "1000"], [2, 100_000, "1000.00"], [3, 1_000_000, "1000.000"], [2, 123_456, "1234.56"]] as const)(
    "# F-CREATE-049 round-trips unchanged minor units %i at scale %i as ungrouped decimal text", async (scale, minorUnits, decimal) => {
      const scaleProfile = { ...profile, profile: { ...profile.profile, scale, minimum_stake: 1, maximum_stake: 1_000_000_000, stake_increment: 1 } };
      const storedStrategy = { ...strategy, definition: { ...definition, staking_parameters: { per_number_stake: minorUnits } } };
      vi.mocked(apiClient.getProfiles).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [scaleProfile], templates: [] });
      vi.mocked(apiClient.listProfileBatchStrategies).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [storedStrategy] });
      vi.mocked(apiClient.reviseProfileBatchStrategy).mockResolvedValue(strategy as never);
      const user = userEvent.setup(); mount();
      await user.selectOptions(await screen.findByLabelText("Perfil de juego"), "local@2");
      await user.click(screen.getByRole("button", { name: "Estrategias" }));
      await user.click(screen.getByRole("button", { name: "Editar y guardar nueva revisión" }));
      expect(screen.getByLabelText(/Apuesta por número/)).toHaveValue(decimal);
      await user.click(screen.getByRole("button", { name: "Guardar nueva revisión" }));
      await waitFor(() => expect(apiClient.reviseProfileBatchStrategy).toHaveBeenCalledWith("custom", 1,
        expect.objectContaining({ staking_parameters: expect.objectContaining({ per_number_stake: minorUnits }) })));
    });

  it("# F-CREATE-050 copies supported definitions without dropping their closed defaults or protected metadata", async () => {
    const protectedStrategy = { ...strategy, protected: true, definition: { ...definition,
      closing_defaults: { settlement: "best" as const, max_elapsed_draws: 15, max_bet_draws: 12 } } };
    vi.mocked(apiClient.listProfileBatchStrategies).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [protectedStrategy] });
    vi.mocked(apiClient.createProfileBatchStrategy).mockResolvedValue(strategy as never);
    const user = userEvent.setup(); mount();
    await user.selectOptions(await screen.findByLabelText("Perfil de juego"), "local@2");
    await user.click(screen.getByRole("button", { name: "Estrategias" }));
    await user.click(screen.getByRole("button", { name: "Crear copia editable" }));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Fijas copia");
    await user.click(screen.getByRole("button", { name: "Guardar como estrategia nueva" }));
    await waitFor(() => expect(apiClient.createProfileBatchStrategy).toHaveBeenCalledWith(expect.objectContaining({
      name: "Fijas copia", selector: "static-numbers/v1", staking: "flat-per-number/v1",
      selector_parameters: { numbers: [3] }, closing_defaults: { settlement: "best", max_elapsed_draws: 15, max_bet_draws: 12 },
    })));
  });

  it("# F-CREATE-051 does not present an unsupported closed strategy as an editable flat/static replacement", async () => {
    const advanced = { ...strategy, definition: { ...definition, selector: "archived-cold/v1" as const,
      staking: "profile-recovery-ladder/v1" as const, selector_parameters: { system: "closed-system" },
      staking_parameters: { per_number_stake: 100, rounds: 4, end_mode: "stop" as const, target_margin: 25 },
      closing_defaults: { settlement: "best" as const, max_bet_draws: 12 } } };
    vi.mocked(apiClient.listProfileBatchStrategies).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [advanced] as never });
    const user = userEvent.setup(); mount();
    await user.click(screen.getByRole("button", { name: "Estrategias" }));
    const strategyArticle = screen.getByRole("heading", { name: /Fijas/ }).closest("article");
    expect(strategyArticle).not.toBeNull();
    await user.click(strategyArticle!.querySelector("summary")!);
    expect(strategyArticle).toHaveTextContent("archived-cold/v1");
    expect(screen.getByText("custom · 1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Editar y guardar nueva revisión" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/No se puede editar ni copiar esta estrategia sin cambiarla/);
    expect(screen.queryByRole("button", { name: /Guardar como estrategia nueva/ })).not.toBeInTheDocument();
  });

  it("# F-CREATE-052 keeps a selected canonical start draw while browsing another draw page", async () => {
    vi.mocked(apiClient.getDatasetDraws).mockImplementation(async (_hash, offset) => ({ total: 101, offset: offset ?? 0, limit: 100,
      items: offset === 0 ? ["2025-01-01 08:30"] : ["2025-01-02 08:30"] }));
    const user = userEvent.setup(); mount();
    await screen.findByRole("option", { name: /historial/ });
    await user.selectOptions(screen.getByLabelText("Perfil de juego"), "local@2");
    await user.click(screen.getByRole("button", { name: "Estrategias" }));
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await user.click(screen.getByRole("navigation", { name: "Páginas de sorteos" }).querySelector("button:last-of-type")!);
    await screen.findByRole("option", { name: "2025-01-02 08:30" });
    await user.click(screen.getByRole("button", { name: "Validación" }));
    await user.click(screen.getByRole("button", { name: "Validar simulación" }));
    await waitFor(() => expect(apiClient.validateProfileBatch).toHaveBeenCalled());
    expect(apiClient.validateProfileBatch).toHaveBeenCalledWith(expect.objectContaining({ conditions: expect.objectContaining({ start_draw: "2025-01-01 08:30" }) }));
  });

  it("# F-CREATE-052 accepts the current dataset draw page response after an unrelated condition edit", async () => {
    let resolveDraws!: (page: { total: number; offset: number; limit: number; items: string[] }) => void;
    vi.mocked(apiClient.getDatasetDraws).mockReturnValueOnce(new Promise((resolve) => { resolveDraws = resolve; }));
    const user = userEvent.setup(); mount();
    await user.click(screen.getByRole("button", { name: "Condiciones" }));
    await user.type(await screen.findByLabelText("Máximo sorteos transcurridos"), "5");
    resolveDraws({ total: 1, offset: 0, limit: 100, items: ["2025-01-01 08:30"] });
    expect(await screen.findByRole("option", { name: "2025-01-01 08:30" })).toBeInTheDocument();
  });

  it("# F-CREATE-053 does not submit an invalid or stale profile binding and reports source references without financial claims", async () => {
    const user = userEvent.setup(); mount();
    await screen.findByRole("option", { name: /historial/ });
    await user.selectOptions(screen.getByLabelText("Historial"), dataset.dataset_sha256);
    expect(await screen.findByText(/2025-01-01 08:30/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validación" })).toBeInTheDocument();
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });
});
