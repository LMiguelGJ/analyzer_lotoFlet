import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { ProfileBatchExperimentSummary } from "../../api/types";
import { ProfileBatchPage } from "./ProfileBatchPage";
import { BATCH_DRAFT_STORAGE_KEY, createBatchDraft, parseBatchDraft, serializeBatchDraft, type BatchSubmissionBody } from "./batch-model";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return { ...actual, apiClient: { ...actual.apiClient, getProfiles: vi.fn(), getDatasets: vi.fn(), getDataset: vi.fn(), getDatasetDraws: vi.fn(), getExperiment: vi.fn(),
    listProfileBatchStrategies: vi.fn(), getProfileBatchStrategyRevisions: vi.fn(), getProfileBatchExecutionPolicy: vi.fn(), getProfileBatchStrategy: vi.fn(),
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
  vi.mocked(apiClient.getExperiment).mockRejectedValue(new ApiError(404, "resource not found"));
  vi.mocked(apiClient.getProfileBatchStrategyRevisions).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: [strategy] });
  vi.mocked(apiClient.getDatasetDraws).mockResolvedValue({ total: 1, offset: 0, limit: 100, items: ["2025-01-01 08:30"] });
  vi.mocked(apiClient.listProfileBatchStrategies).mockResolvedValue({ total: 1, offset: 0, limit: 20, items: [strategy] });
  vi.mocked(apiClient.getProfileBatchExecutionPolicy).mockResolvedValue(policy as never);
  vi.mocked(apiClient.getProfileBatchStrategy).mockResolvedValue(strategy);
  vi.mocked(apiClient.validateProfileBatch).mockResolvedValue(validation as never);
  vi.mocked(apiClient.createProfileBatch).mockReset();
});
function mount(path = `/simulaciones/nueva/sesion?dataset_sha256=${dataset.dataset_sha256}`) { render(<MemoryRouter initialEntries={[path]}><ProfileBatchPage /></MemoryRouter>); }
function currentWizardStep() {
  return {
    progress: screen.getByRole("progressbar").getAttribute("aria-valuenow"),
    heading: screen.getByRole("heading", { level: 2, name: /^(?:[1-5] · )/ }).textContent,
  };
}
async function nextBatchStep(user: ReturnType<typeof userEvent.setup>) {
  const before = Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"));
  const step = currentWizardStep();
  console.info(`[ProfileBatchPage wizard] ${JSON.stringify(step)}`);
  await user.click(document.querySelector(".m3-wizard-actions .btn-primary") as HTMLButtonElement);
  await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(before + 1)));
}
async function goToStep(user: ReturnType<typeof userEvent.setup>, step: string) {
  const wizard = within(screen.getByRole("navigation", { name: "Pasos de la simulación" }));
  const state = currentWizardStep();
  console.info(`[ProfileBatchPage wizard] ${JSON.stringify(state)}`);
  const button = wizard.getAllByRole("button").find((candidate) => candidate.textContent?.trim().endsWith(step));
  if (!button) throw new Error(`Wizard step button not found: ${step}`);
  if (button.getAttribute("aria-current") !== "step") await user.click(button);
  await waitFor(() => expect(button).toHaveAttribute("aria-current", "step"));
}
async function advanceBatchTo(user: ReturnType<typeof userEvent.setup>, step: number) {
  while (Number(screen.getByRole("progressbar").getAttribute("aria-valuenow")) < step + 1) await nextBatchStep(user);
}
const nextWizardStep = nextBatchStep;
const advanceTo = advanceBatchTo;
async function reachScope(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(await screen.findByLabelText("Perfil de juego"), "local@2");
  await user.click(await screen.findByRole("button", { name: "Agregar" }));
  const strategyArticle = screen.getByRole("heading", { name: "Fijas" }).closest("article");
  await waitFor(() => expect(within(strategyArticle!).getByRole("button", { name: "Quitar" })).toHaveAttribute("aria-pressed", "true"));
  await nextWizardStep(user);
  await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
  await nextWizardStep(user);
  await screen.findByRole("option", { name: "2025-01-01 08:30" });
}
async function reachCapital(user: ReturnType<typeof userEvent.setup>) {
  await reachScope(user);
  await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
  await nextWizardStep(user);
}

const savedBatch = { request_kind: "profile", request_schema_version: 5, id: "saved-base", status: "completed", created_at: null,
  request: { schema_version: 5, kind: "profile_batch", profile_id: "local", profile_revision: 2, profile_sha256: "a".repeat(64), dataset_sha256: dataset.dataset_sha256,
    conditions: { schema_version: 1, start_draw: "2025-01-01 08:30", capital: 100, goal: 200, settlement: "best", max_elapsed_draws: 50, max_bet_draws: 20, end_minute: null, duration_minutes: null },
    strategies: [definition], max_draws: 40, source_version: "canonical-history/v1" }, profile: profile.profile, display: {}, sources: {}, runs: [],
  batch_admission: { strategy_refs: [{ id: "custom", revision: 1, definition_sha256: "d".repeat(64) }],
    source_identity: { dataset_sha256: dataset.dataset_sha256, source_sha256: dataset.source_sha256, canonical_sha256: "e".repeat(64), row_count: 1,
      profile_id: "local", profile_revision: 2, profile_sha256: "a".repeat(64), archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null },
    requested_constraints: { max_draws: 40, max_elapsed_draws: 50, max_bet_draws: 20 }, effective_constraints: { max_draws: 10 }, policy_revision: 1, policy: { max_draws: 10 } } } as unknown as ProfileBatchExperimentSummary;

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
  it.each([false, true])("keeps pending Review and its exact recovery context across same-mounted dataset hints for repeat=%s", async (repeat) => {
    const saved = createBatchDraft(dataset.dataset_sha256);
    saved.profile = frozenBody.profile;
    saved.strategyRefs = frozenBody.strategies;
    saved.selectedDraw = { datasetSha256: dataset.dataset_sha256, index: 0, draw: frozenBody.conditions.start_draw };
    saved.conditions = { start_draw: frozenBody.conditions.start_draw, capital: "100", goal: "200", settlement: "all", max_elapsed_draws: "50", max_bet_draws: "", max_draws: "50" };
    saved.pending = { clientRequestId: frozenBody.client_request_id, frozenBody };
    const storageKey = repeat ? `${BATCH_DRAFT_STORAGE_KEY}:repeat:saved-base` : BATCH_DRAFT_STORAGE_KEY;
    sessionStorage.setItem(storageKey, serializeBatchDraft(saved));
    if (repeat) vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    const baseQuery = repeat ? "base=saved-base&" : "";
    render(<MemoryRouter initialEntries={[`/simulaciones/nueva/sesion?${baseQuery}dataset_sha256=${dataset.dataset_sha256}`]}>
      <Link to={`?${baseQuery}dataset_sha256=${"f".repeat(64)}`}>Cambiar pista de historial</Link>
      <Link to={repeat ? "?base=saved-base" : "/simulaciones/nueva/sesion"}>Quitar pista de historial</Link>
      <ProfileBatchPage />
    </MemoryRouter>);
    expect(await screen.findByRole("button", { name: /recuperar creación pendiente/i })).toBeEnabled();
    const baseLoads = vi.mocked(apiClient.getExperiment).mock.calls.length;
    const user = userEvent.setup();
    for (const name of ["Cambiar pista de historial", "Quitar pista de historial"]) {
      await user.click(screen.getByRole("link", { name }));
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
      expect(screen.getByRole("button", { name: /recuperar creación pendiente/i })).toBeEnabled();
      const restored = parseBatchDraft(sessionStorage.getItem(storageKey));
      expect(restored?.pending).toEqual({ clientRequestId: frozenBody.client_request_id, frozenBody });
      expect(restored?.step).toBe(3);
      expect(restored?.strategyRefs).toEqual(frozenBody.strategies);
    }
    expect(apiClient.getExperiment).toHaveBeenCalledTimes(baseLoads);
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });
  it.each([[0, 3], [1, 1], [2, 4], [3, 5]])("rehydrates native stage %s at UI step %s when only the fresh dataset query changes", async (stage, uiStep) => {
    const saved = createBatchDraft(dataset.dataset_sha256);
    saved.step = stage;
    sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, serializeBatchDraft(saved));
    render(<MemoryRouter initialEntries={["/simulaciones/nueva/sesion"]}>
      <Link to={`?dataset_sha256=${"f".repeat(64)}`}>Cambiar pista de historial</Link><ProfileBatchPage />
    </MemoryRouter>);
    await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(uiStep)));
    await userEvent.setup().click(screen.getByRole("link", { name: "Cambiar pista de historial" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", String(uiStep));
    expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.step).toBe(stage);
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });
  it.each([false, true])("persists five-step navigation using native stages for repeat=%s and returns to Strategy after a dataset change", async (repeat) => {
    const saved = createBatchDraft(dataset.dataset_sha256);
    saved.step = 2;
    saved.profile = { id: "local", revision: 2, sha256: profile.profile_sha256 };
    saved.strategyRefs = frozenBody.strategies;
    saved.selectedDraw = { datasetSha256: dataset.dataset_sha256, index: 0, draw: "2025-01-01 08:30" };
    saved.conditions = { start_draw: "2025-01-01 08:30", capital: "100", goal: "200", settlement: "all", max_elapsed_draws: "50", max_bet_draws: "", max_draws: "50" };
    const storageKey = repeat ? `${BATCH_DRAFT_STORAGE_KEY}:repeat:saved-base` : BATCH_DRAFT_STORAGE_KEY;
    sessionStorage.setItem(storageKey, serializeBatchDraft(saved));
    if (repeat) vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    mount(repeat ? "/simulaciones/nueva/sesion?base=saved-base" : "/simulaciones/nueva/sesion");
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "4"));
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
    expect(parseBatchDraft(sessionStorage.getItem(storageKey))?.step).toBe(3);
    await user.click(screen.getByRole("button", { name: "Atrás" }));
    expect(parseBatchDraft(sessionStorage.getItem(storageKey))?.step).toBe(2);
    await user.click(screen.getByRole("button", { name: "Atrás" }));
    expect(parseBatchDraft(sessionStorage.getItem(storageKey))?.step).toBe(0);
    await user.selectOptions(screen.getByLabelText("Historial"), dataset.dataset_sha256);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByRole("alert")).toHaveTextContent(/historial cambió.*retiraron las estrategias/i);
    expect(parseBatchDraft(sessionStorage.getItem(storageKey))?.strategyRefs).toEqual([]);
    expect(parseBatchDraft(sessionStorage.getItem(storageKey))?.step).toBe(1);
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });
  it("restores pending recovery at Review and does not POST after the lookup outlives a source change", async () => {
    storePendingDraft();
    let rejectLookup!: (reason: unknown) => void;
    vi.mocked(apiClient.getProfileBatchByClientRequestId).mockReturnValueOnce(new Promise((_resolve, reject) => { rejectLookup = reject; }));
    render(<MemoryRouter initialEntries={["/simulaciones/nueva/sesion"]}><Link to="?base=missing">Cambiar referencia</Link><ProfileBatchPage /></MemoryRouter>);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /recuperar creación pendiente/i }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
    await waitFor(() => expect(apiClient.getProfileBatchByClientRequestId).toHaveBeenCalledWith("frozen-request"));
    await user.click(screen.getByRole("link", { name: "Cambiar referencia" }));
    rejectLookup(new ApiError(404, "resource not found"));
    await screen.findByText(/No se puede repetir esta simulación guardada/);
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
    expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.pending?.frozenBody).toEqual(frozenBody);
  });
  it("restores a fresh pending request after visiting and leaving a saved repeat base on the same mount", async () => {
    storePendingDraft();
    vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    render(<MemoryRouter initialEntries={[`/simulaciones/nueva/sesion?dataset_sha256=${dataset.dataset_sha256}`]}>
      <Link to="?base=saved-base">Repeat saved</Link><Link to={`?dataset_sha256=${dataset.dataset_sha256}`}>Fresh creator</Link><ProfileBatchPage />
    </MemoryRouter>);
    expect(await screen.findByRole("button", { name: /recuperar creación pendiente/i })).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("link", { name: "Repeat saved" }));
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    await user.click(screen.getByRole("link", { name: "Fresh creator" }));
    expect(await screen.findByRole("button", { name: /recuperar creación pendiente/i })).toBeInTheDocument();
    expect(parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY))?.pending?.clientRequestId).toBe("frozen-request");
  });
  it("keeps the verified base profile selected when the normal profile catalog resolves without that old revision", async () => {
    let resolveCatalog!: (page: Awaited<ReturnType<typeof apiClient.getProfiles>>) => void;
    vi.mocked(apiClient.getProfiles).mockImplementation((_offset, limit) => limit === 20
      ? new Promise((resolve) => { resolveCatalog = resolve; })
      : Promise.resolve({ total: 1, offset: 0, limit: 100, items: [profile], templates: [] }));
    vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    mount(`/simulaciones/nueva/sesion?base=saved-base`);
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    resolveCatalog({ total: 25, offset: 0, limit: 20, items: [], templates: [] });
    await waitFor(() => expect(apiClient.getProfiles).toHaveBeenCalledWith(0, 20));
    const user = userEvent.setup();
    await advanceTo(user, 3);
    await goToStep(user, "Estrategia");
    expect(screen.getByLabelText("Perfil de juego")).toHaveValue("local@2");
    expect(screen.getByLabelText("Apuesta por número (DOP)")).toBeInTheDocument();
  });
  it("hydrates a verified saved v5 batch into a separate editable repeat draft", async () => {
    const priorDraft = createBatchDraft(dataset.dataset_sha256);
    priorDraft.pending = { clientRequestId: "prior-request", frozenBody };
    const priorSerialized = serializeBatchDraft(priorDraft);
    sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, priorSerialized);
    vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    const user = userEvent.setup();
    mount(`/simulaciones/nueva/sesion?base=saved-base`);
    await waitFor(() => expect(apiClient.getExperiment).toHaveBeenCalledWith("saved-base"));
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    await advanceTo(user, 3);
    expect(screen.getByLabelText("Capital inicial (DOP)")).toHaveValue("100");
    expect(screen.getByLabelText("Meta de saldo (DOP)")).toHaveValue("200");
    expect(screen.getByLabelText("Máximo sorteos transcurridos")).toHaveValue("50");
    expect(screen.getByLabelText("Máximo sorteos apostados (opcional)")).toHaveValue("20");
    expect(screen.getByLabelText("Límite operativo solicitado")).toHaveValue("40");
    await goToStep(user, "Reglas");
    expect(screen.getByLabelText("Cómo contar los premios")).toHaveValue("best");
    await goToStep(user, "Capital y meta");
    const maxDraws = screen.getByLabelText("Límite operativo solicitado");
    await user.clear(maxDraws); await user.type(maxDraws, "41");
    expect(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY)).toBe(priorSerialized);
    await advanceTo(user, 4);
    await user.click(screen.getByRole("button", { name: "Validar solicitud actual" }));
    await screen.findByText("Validación aceptada");
    expect(apiClient.validateProfileBatch).toHaveBeenCalledWith(expect.objectContaining({ max_draws: 41,
      strategies: savedBatch.batch_admission.strategy_refs, client_request_id: expect.not.stringMatching(/^saved-base$/) }));
    expect(sessionStorage.getItem(`${BATCH_DRAFT_STORAGE_KEY}:repeat:saved-base`)).not.toBeNull();
  });
  it("invalidates a pending validation when switching between bases with the same request body", async () => {
    let resolveValidation!: (value: typeof validation) => void;
    vi.mocked(apiClient.getExperiment).mockImplementation(async (id) => ({ ...savedBatch, id }));
    vi.mocked(apiClient.validateProfileBatch).mockReturnValueOnce(new Promise((resolve) => { resolveValidation = (value) => resolve(value as never); }));
    render(<MemoryRouter initialEntries={["/simulaciones/nueva/sesion?base=base-one"]}>
      <Link to="?base=base-two">Switch base</Link><ProfileBatchPage />
    </MemoryRouter>);
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    const user = userEvent.setup();
    await advanceTo(user, 4);
    await user.click(screen.getByRole("button", { name: "Validar solicitud actual" }));
    await waitFor(() => expect(apiClient.validateProfileBatch).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("link", { name: "Switch base" }));
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    resolveValidation(validation);
    await waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3"));
    expect(screen.getByRole("heading", { level: 2, name: "3 · Alcance" })).toBeInTheDocument();
    expect(screen.queryByText("Validación aceptada")).not.toBeInTheDocument();
  });
  it("keeps hydration from a previous base from overwriting the active base", async () => {
    let resolveFirst!: (value: typeof savedBatch) => void;
    const second = { ...savedBatch, id: "base-two", request: { ...savedBatch.request,
      conditions: { ...savedBatch.request.conditions, capital: 120 } } };
    vi.mocked(apiClient.getExperiment).mockImplementation((id) => id === "base-one"
      ? new Promise((resolve) => { resolveFirst = resolve; }) : Promise.resolve(second));
    render(<MemoryRouter initialEntries={["/simulaciones/nueva/sesion?base=base-one"]}>
      <Link to="?base=base-two">Cambiar referencia</Link><ProfileBatchPage />
    </MemoryRouter>);
    await userEvent.setup().click(screen.getByRole("link", { name: "Cambiar referencia" }));
    await waitFor(() => expect(screen.queryByText(/Recuperando y verificando/)).not.toBeInTheDocument());
    await advanceTo(userEvent.setup(), 3);
    expect(screen.getByLabelText("Capital inicial (DOP)")).toHaveValue("120");
    resolveFirst(savedBatch);
    await waitFor(() => expect(screen.getByLabelText("Capital inicial (DOP)")).toHaveValue("120"));
  });
  it("blocks a saved base when retrieved source identity differs", async () => {
    vi.mocked(apiClient.getExperiment).mockResolvedValue(savedBatch);
    vi.mocked(apiClient.getDataset).mockResolvedValue({ ...dataset, source_sha256: "f".repeat(64) });
    mount(`/simulaciones/nueva/sesion?base=saved-base`);
    expect(await screen.findByRole("alert")).toHaveTextContent(/identidad de origen/);
    expect(apiClient.validateProfileBatch).not.toHaveBeenCalled();
  });
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
    await reachScope(user);
    await screen.findByRole("option", { name: /Historial 1/ });
    await user.selectOptions(screen.getByLabelText("Historial"), dataset.dataset_sha256);
    await user.selectOptions(screen.getByLabelText("Perfil de juego"), "local@2");
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    await nextWizardStep(user);
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await nextWizardStep(user);
    await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
    await nextWizardStep(user);
    const elapsed = screen.getByLabelText("Máximo sorteos transcurridos");
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(elapsed, "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await nextWizardStep(user);
    const simulate = screen.getByRole("button", { name: "Crear simulaciones" });
    expect(simulate).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Validar solicitud actual" }));
    expect(await screen.findByText("Validación aceptada")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Validar comprueba la solicitud; no reserva capacidad.");
    expect(screen.getByRole("button", { name: "Crear simulaciones" })).toBeEnabled();
    expect(apiClient.validateProfileBatch).toHaveBeenCalledWith(expect.objectContaining({ schema_version: 1,
      profile: { id: "local", revision: 2, sha256: "a".repeat(64) }, dataset_sha256: dataset.dataset_sha256,
      strategies: [{ id: "custom", revision: 1, definition_sha256: "d".repeat(64) }],
      conditions: expect.objectContaining({ capital: 100, goal: 200, start_draw: "2025-01-01 08:30", settlement: "all" }) }));
    await goToStep(user, "Capital y meta");
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "1");
    await advanceTo(user, 4);
    expect(screen.getByRole("button", { name: "Crear simulaciones" })).toBeDisabled();
  });

  it("# F-CREATE-046 looks up the frozen client request identity before retrying an uncertain create", async () => {
    const user = userEvent.setup(); mount();
    await reachCapital(user);
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await nextWizardStep(user);
    await user.click(screen.getByRole("button", { name: "Validar solicitud actual" }));
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
    // C: pending recovery locks wizard navigation; editing the prior draft is superseded by frozen-request recovery.
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
    const stepButtons = within(screen.getByRole("navigation", { name: "Pasos de la simulación" })).getAllByRole("button");
    expect(stepButtons).toHaveLength(5);
    stepButtons.forEach((button) => expect(button).toBeDisabled());
    expect(screen.getByRole("button", { name: /recuperar creación pendiente/i })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: /recuperar creación pendiente/i }));
    await waitFor(() => expect(apiClient.createProfileBatch).toHaveBeenCalledWith(frozenBody));
    await screen.findByRole("alert");
    expect(apiClient.createProfileBatch).toHaveBeenCalledTimes(1);
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
      await goToStep(user, "Estrategia");
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
    await goToStep(user, "Estrategia");
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
    await goToStep(user, "Estrategia");
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
    await reachCapital(user);
    await user.type(screen.getByLabelText("Capital inicial (DOP)"), "100");
    await user.type(screen.getByLabelText("Meta de saldo (DOP)"), "200");
    await user.type(screen.getByLabelText("Máximo sorteos transcurridos"), "50");
    await user.type(screen.getByLabelText("Límite operativo solicitado"), "50");
    await goToStep(user, "Alcance");
    await user.selectOptions(screen.getByLabelText("Sorteo inicial"), "2025-01-01 08:30");
    await goToStep(user, "Reglas");
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await goToStep(user, "Alcance");
    await user.click(screen.getByRole("navigation", { name: "Páginas de sorteos" }).querySelector("button:last-of-type")!);
    await screen.findByRole("option", { name: "2025-01-02 08:30" });
    await goToStep(user, "Capital y meta");
    await nextWizardStep(user);
    await user.click(screen.getByRole("button", { name: "Validar solicitud actual" }));
    await waitFor(() => expect(apiClient.validateProfileBatch).toHaveBeenCalled());
    expect(apiClient.validateProfileBatch).toHaveBeenCalledWith(expect.objectContaining({ conditions: expect.objectContaining({ start_draw: "2025-01-01 08:30" }) }));
  });

  it("# F-CREATE-052 accepts the current dataset draw page response after an unrelated condition edit", async () => {
    let resolveDraws!: (page: { total: number; offset: number; limit: number; items: string[] }) => void;
    vi.mocked(apiClient.getDatasetDraws).mockReturnValueOnce(new Promise((resolve) => { resolveDraws = resolve; }));
    const user = userEvent.setup(); mount();
    await user.selectOptions(await screen.findByLabelText("Perfil de juego"), "local@2");
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    const strategyArticle = screen.getByRole("heading", { name: "Fijas" }).closest("article");
    await waitFor(() => expect(within(strategyArticle!).getByRole("button", { name: "Quitar" })).toHaveAttribute("aria-pressed", "true"));
    await nextWizardStep(user);
    // Unrelated condition edit while the draw catalog request is still in flight.
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await act(async () => { resolveDraws({ total: 1, offset: 0, limit: 100, items: ["2025-01-01 08:30"] }); });
    await nextWizardStep(user);
    expect(await screen.findByRole("option", { name: "2025-01-01 08:30" })).toBeInTheDocument();
  });
  it("# F-CREATE-053 does not submit an invalid or stale profile binding and reports source references without financial claims", async () => {
    const user = userEvent.setup(); mount();
    await reachScope(user);
    await screen.findByRole("option", { name: /Historial 1/ });
    expect(await screen.findByText("2025-01-01 08:30", { exact: false, selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(`${dataset.source_id} · ${dataset.source_revision} · ${dataset.dataset_sha256}`)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Historial"), dataset.dataset_sha256);
    await user.selectOptions(screen.getByLabelText("Perfil de juego"), "local@2");
    await user.click(await screen.findByRole("button", { name: "Agregar" }));
    await nextWizardStep(user);
    await user.selectOptions(screen.getByLabelText("Cómo contar los premios"), "all");
    await nextWizardStep(user);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3");
    expect(apiClient.createProfileBatch).not.toHaveBeenCalled();
  });
});
