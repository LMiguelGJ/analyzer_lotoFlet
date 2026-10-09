import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import { isProfileBatchExperiment, type DatasetListing, type Page, type ProfileBatchExecutionPolicy, type ProfileBatchStrategy, type ProfileBatchValidation, type ProfileListing } from "../../api/types";
import { moneyUnits, wholeNumber } from "../../lib/profile-input";
import { FiveStepWizard, useFiveStepWizard } from "../../components/FiveStepWizard";
import { WizardScopeSelector } from "../../components/WizardScopeSelector";
import { GameRulesSummary } from "../../components/GameRulesSummary";
import { profileRulesView, profileSettlementLabel } from "../../lib/game-rules";
import { BATCH_DRAFT_STORAGE_KEY, buildBatchBody, createBatchDraft, parseBatchDraft, serializeBatchDraft, type BatchDraft, type ClosedStrategyDefinition, type StrategyReference } from "./batch-model";
import { prepareBatchRepeat } from "./profile-batch-repeat";

const control = "control";
const hashPattern = /^[0-9a-f]{64}$/;
const genericDefinition = (name: string, coverage: number, selector: ClosedStrategyDefinition["selector"], numbers: number[], seed: number, stake: number, settlement: "all" | "best"): ClosedStrategyDefinition => ({
  definition_version: 1, name, selector, coverage, staking: "flat-per-number/v1",
  selector_parameters: selector === "static-numbers/v1" ? { numbers } : { seed },
  staking_parameters: { per_number_stake: stake }, closing_defaults: { settlement },
});

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function formatMinorUnitsInput(amount: number, scale: number): string {
  if (!Number.isSafeInteger(amount) || amount < 0 || !Number.isInteger(scale) || scale < 0 || scale > 6) {
    throw new RangeError("Stake input requires safe minor units and a supported profile scale");
  }
  const digits = BigInt(amount).toString().padStart(scale + 1, "0");
  return scale ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}` : digits;
}

function errorText(error: unknown, action: string): string {
  if (error instanceof NetworkError) return `No se pudo contactar al servidor para ${action}.`;
  if (error instanceof ApiError && error.status === 409) return "El perfil, el historial o la estrategia cambiaron. Actualizá y validá de nuevo.";
  if (error instanceof ApiError && error.status === 422) return "El servidor rechazó los datos. Revisá los campos.";
  if (error instanceof ApiError && error.status === 507) return "No hay espacio disponible para guardar la estrategia.";
  return `No se pudo ${action}. Reintentá.`;
}

export function ProfileBatchPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const requestedHash = new URLSearchParams(location.search).get("dataset_sha256");
  const initialHash = requestedHash && hashPattern.test(requestedHash) ? requestedHash : "";
  const baseId = new URLSearchParams(location.search).get("base") ?? "";
  const repeatStorageKey = baseId ? `${BATCH_DRAFT_STORAGE_KEY}:repeat:${encodeURIComponent(baseId)}` : BATCH_DRAFT_STORAGE_KEY;
  const [draft, setDraft] = useState<BatchDraft>(() => initialHash ? createBatchDraft(initialHash) : createBatchDraft("0".repeat(64)));
  const wizard = useFiveStepWizard(5, validateWizardStep);
  const liveRecovery = useRef({ step: wizard.step, context: repeatStorageKey, pendingId: draft.pending?.clientRequestId });
  liveRecovery.current = { step: wizard.step, context: repeatStorageKey, pendingId: draft.pending?.clientRequestId };
  const [profiles, setProfiles] = useState<Page<ProfileListing> | null>(null);
  const [pinnedProfile, setPinnedProfile] = useState<{ baseId: string; listing: ProfileListing } | null>(null);
  const [draftContextKey, setDraftContextKey] = useState("");
  const [datasets, setDatasets] = useState<Page<DatasetListing> | null>(null);
  const [deepDataset, setDeepDataset] = useState<DatasetListing | null>(null);
  const [draws, setDraws] = useState<Page<string> | null>(null);
  const [strategies, setStrategies] = useState<Page<ProfileBatchStrategy> | null>(null);
  const [strategyRevisions, setStrategyRevisions] = useState<Record<string, ProfileBatchStrategy[]>>({});
  const [policy, setPolicy] = useState<ProfileBatchExecutionPolicy | null>(null);
  const [profileOffset, setProfileOffset] = useState(0);
  const [datasetOffset, setDatasetOffset] = useState(0);
  const [strategyOffset, setStrategyOffset] = useState(0);
  const [drawOffset, setDrawOffset] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [alert, setAlert] = useState("");
  const [storageWarning, setStorageWarning] = useState(false);
  const [baseLoading, setBaseLoading] = useState(Boolean(baseId));
  const [baseError, setBaseError] = useState("");
  const [repeatReady, setRepeatReady] = useState(!baseId);
  const [loading, setLoading] = useState(false);
  const [definitionName, setDefinitionName] = useState("");
  const [selector, setSelector] = useState<"static-numbers/v1" | "seeded-random/hash-sha256-v1">("static-numbers/v1");
  const [coverage, setCoverage] = useState("1");
  const [numbers, setNumbers] = useState("");
  const [seed, setSeed] = useState("0");
  const [stake, setStake] = useState("1");
  const [editorAvailable, setEditorAvailable] = useState(true);
  const [editDefinition, setEditDefinition] = useState<ClosedStrategyDefinition | null>(null);
  const [editTarget, setEditTarget] = useState<ProfileBatchStrategy | null>(null);
  const [validated, setValidated] = useState<{ bodyKey: string; result: ProfileBatchValidation } | null>(null);
  const generation = useRef(0);
  const catalogGeneration = useRef(0);
  const drawGeneration = useRef(0);
  const pendingOperation = useRef(0);
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const baseGeneration = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current++; };
  }, []);
  useEffect(() => {
    generation.current++;
    setValidated(null);
    setAlert("");
    // Dataset query hints must not reset a repeat whose base loader is unchanged.
    if (baseId) return;
    setBaseLoading(false); setBaseError(""); setRepeatReady(true);
    setDraftContextKey("");
    try {
      const raw = sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY);
      const saved = parseBatchDraft(raw);
      if (saved) {
        hydrateDraft(saved);
        if (initialHash && saved.datasetSha256 !== initialHash) setAlert("El enlace apunta a otro historial; se conservó el borrador. Elegí el historial nuevo para cambiar.");
      } else {
        hydrateDraft({ ...createBatchDraft(initialHash || "0".repeat(64)), step: 1 });
        if (raw) { setStorageWarning(true); setAlert("El borrador guardado ya no es compatible y no se restauró."); }
      }
    } catch { setStorageWarning(true); hydrateDraft({ ...createBatchDraft(initialHash || "0".repeat(64)), step: 1 }); }
    setDraftContextKey(BATCH_DRAFT_STORAGE_KEY);
  }, [initialHash, baseId]);
  useEffect(() => {
    if (draftContextKey !== repeatStorageKey) return;
    try { sessionStorage.setItem(repeatStorageKey, serializeBatchDraft(draft)); }
    catch { setStorageWarning(true); }
  }, [draft, repeatStorageKey, baseId, draftContextKey]);
  useEffect(() => {
    if (!baseId) return;
    const ticket = ++baseGeneration.current;
    let live = true;
    liveRecovery.current.step = 0;
    wizard.goTo(0);
    setBaseLoading(true); setBaseError(""); setRepeatReady(false); setDraftContextKey("");
    void (async () => {
      try {
        const raw = await apiClient.getExperiment(baseId);
        if (raw.id !== baseId) throw new Error("El servidor devolvió otra referencia guardada.");
        if (!isProfileBatchExperiment(raw)) throw new Error("Esta referencia no es una solicitud de lote v5.");
        const prepared = prepareBatchRepeat(raw);
        const datasetIdentity = await apiClient.getDataset(raw.request.dataset_sha256);
        if (datasetIdentity.dataset_sha256 !== raw.batch_admission.source_identity.dataset_sha256 ||
          datasetIdentity.source_sha256 !== raw.batch_admission.source_identity.source_sha256 ||
          datasetIdentity.profile_id !== raw.request.profile_id || datasetIdentity.profile_revision !== raw.request.profile_revision ||
          datasetIdentity.profile_sha256 !== raw.request.profile_sha256) throw new Error("Los datos guardados ya no coinciden con su identidad de origen; no se sustituirán.");
        let profilePageOffset = 0;
        let matchingProfile: ProfileListing | undefined;
        let profileTotal = 0;
        do {
          const page = await apiClient.getProfiles(profilePageOffset, 100);
          matchingProfile = page.items.find((item) => item.profile.profile_id === raw.request.profile_id &&
            item.profile.revision === raw.request.profile_revision && item.profile_sha256 === raw.request.profile_sha256);
          profileTotal = page.total; profilePageOffset += page.items.length;
          if (matchingProfile || page.items.length === 0) break;
        } while (profilePageOffset < profileTotal);
        if (!matchingProfile) throw new Error("No se puede recuperar la revisión exacta del perfil guardado.");
        const verifiedStrategies: ProfileBatchStrategy[] = [];
        for (let index = 0; index < raw.batch_admission.strategy_refs.length; index++) {
          const ref = raw.batch_admission.strategy_refs[index];
          let offset = 0; let total = 0; let exact: ProfileBatchStrategy | undefined;
          do {
            const page = await apiClient.getProfileBatchStrategyRevisions(ref.id, offset, 100);
            exact = page.items.find((item) => item.revision === ref.revision && item.definition_sha256 === ref.definition_sha256);
            total = page.total; offset += page.items.length;
            if (exact || !page.items.length) break;
          } while (offset < total);
          if (!exact || exact.definition_valid !== true || stableJson(exact.definition) !== stableJson(raw.request.strategies[index])) {
            throw new Error("No se puede recuperar la revisión original de una estrategia guardada.");
          }
          verifiedStrategies.push(exact);
        }
        let repeatDraft = prepared.draft;
        try {
          const savedDraft = parseBatchDraft(sessionStorage.getItem(repeatStorageKey));
          if (savedDraft && savedDraft.datasetSha256 === raw.request.dataset_sha256 && savedDraft.profile?.id === raw.request.profile_id &&
            savedDraft.profile.revision === raw.request.profile_revision && savedDraft.profile.sha256 === raw.request.profile_sha256 &&
            (!savedDraft.pending || (savedDraft.pending.frozenBody.dataset_sha256 === raw.request.dataset_sha256 &&
              savedDraft.pending.frozenBody.profile.id === raw.request.profile_id && savedDraft.pending.frozenBody.profile.revision === raw.request.profile_revision &&
              savedDraft.pending.frozenBody.profile.sha256 === raw.request.profile_sha256))) repeatDraft = savedDraft;
        } catch { if (mounted.current) setStorageWarning(true); }
        let foundDraw = false; let offset = 0; let total = 0;
        do {
          const page = await apiClient.getDatasetDraws(raw.request.dataset_sha256, offset, 100);
          const index = page.items.indexOf(repeatDraft.conditions.start_draw);
          if (index >= 0) {
            repeatDraft.selectedDraw = { datasetSha256: raw.request.dataset_sha256, index: page.offset + index, draw: repeatDraft.conditions.start_draw };
            foundDraw = true; break;
          }
          total = page.total; offset += page.items.length;
        } while (offset < total);
        if (!foundDraw) throw new Error("El sorteo inicial de la solicitud no está en el historial recuperado.");
        if (!live || !mounted.current || baseGeneration.current !== ticket) return;
        setPinnedProfile({ baseId, listing: matchingProfile });
        setStrategies((page) => page ? { ...page, items: [...verifiedStrategies, ...page.items.filter((item) => !verifiedStrategies.some((verified) => verified.id === item.id && verified.revision === item.revision))] } : page);
        setDeepDataset(datasetIdentity); hydrateDraft(repeatDraft); setRepeatReady(true); setDraftContextKey(repeatStorageKey);
      } catch (cause) {
        if (live && mounted.current && baseGeneration.current === ticket) setBaseError(cause instanceof Error ? cause.message : "No se pudo verificar la referencia guardada.");
      } finally {
        if (live && mounted.current && baseGeneration.current === ticket) setBaseLoading(false);
      }
    })();
    return () => { live = false; };
  }, [baseId]);

  const refreshCatalogs = useCallback(() => {
    const ticket = ++catalogGeneration.current;
    void Promise.all([
      apiClient.getProfiles(profileOffset, 20), apiClient.getDatasets(datasetOffset, 20),
      apiClient.listProfileBatchStrategies(strategyOffset, 20), apiClient.getProfileBatchExecutionPolicy(),
    ]).then(([p, d, s, policyResult]) => {
      if (!mounted.current || catalogGeneration.current !== ticket) return;
      setProfiles(p); setDatasets(d); setStrategies(s); setPolicy(policyResult); setErrors({});
    }).catch((cause: unknown) => { if (mounted.current && catalogGeneration.current === ticket) setErrors((old) => ({ ...old, catalogs: errorText(cause, "cargar las listas") })); });
  }, [profileOffset, datasetOffset, strategyOffset]);
  useEffect(() => { refreshCatalogs(); }, [refreshCatalogs]);
  function retryCatalogs() {
    refreshCatalogs();
    if (!initialHash) return;
    void apiClient.getDataset(initialHash).then((item) => { if (mounted.current) setDeepDataset(item); })
      .catch((cause: unknown) => { if (mounted.current) setErrors((old) => ({ ...old, deepDataset: errorText(cause, "abrir el historial enlazado") })); });
  }
  useEffect(() => {
    if (!initialHash || datasets?.items.some((item) => item.dataset_sha256 === initialHash)) return;
    let live = true;
    void apiClient.getDataset(initialHash).then((item) => { if (live && mounted.current) setDeepDataset(item); })
      .catch((cause: unknown) => { if (live && mounted.current) setErrors((old) => ({ ...old, deepDataset: errorText(cause, "abrir el historial enlazado") })); });
    return () => { live = false; };
  }, [initialHash, datasets]);

  const activePinnedProfile = pinnedProfile?.baseId === baseId && pinnedProfile.listing.profile.profile_id === draft.profile?.id &&
    pinnedProfile.listing.profile.revision === draft.profile.revision && pinnedProfile.listing.profile_sha256 === draft.profile.sha256 ? pinnedProfile.listing : null;
  const selectedProfile = activePinnedProfile ?? profiles?.items.find((item) => item.profile.profile_id === draft.profile?.id && item.profile.revision === draft.profile.revision && item.profile_sha256 === draft.profile.sha256) ?? null;
  const selectedDataset = datasets?.items.find((item) => item.dataset_sha256 === draft.datasetSha256) ??
    (deepDataset?.dataset_sha256 === draft.datasetSha256 ? deepDataset : null);
  const selectedRefs = useMemo(() => draft.strategyRefs, [draft.strategyRefs]);
  const currentBodyKey = useMemo(() => JSON.stringify({ profile: draft.profile, dataset: draft.datasetSha256, refs: draft.strategyRefs, conditions: draft.conditions }), [draft]);
  const currentValidation = validated?.bodyKey === currentBodyKey ? validated.result : null;

  const mutate = useCallback((fn: (current: BatchDraft) => BatchDraft) => {
    generation.current++;
    setValidated(null); setAlert("");
    setDraft((current) => fn(current));
  }, []);
  function updateCondition(key: keyof BatchDraft["conditions"], value: string) {
    mutate((current) => ({ ...current, conditions: { ...current.conditions, [key]: value } }));
  }
  // Restore the UI with every hydration, even when the storage context key is unchanged.
  function hydrateDraft(value: BatchDraft) {
    const storedToUi: Record<number, number> = { 0: 2, 1: 0, 2: 3, 3: 4, 4: 4 };
    const step = value.pending ? 4 : storedToUi[value.step] ?? 0;
    liveRecovery.current = { step, context: repeatStorageKey, pendingId: value.pending?.clientRequestId };
    wizard.goTo(step);
    setDraft({ ...value, step: [1, 1, 0, 2, 3][step] });
  }
  // Strategy and Rules share stored stage 1; restore at Strategy to recheck both.
  // Scope=0, Capital=2, Review=3. Never write a five-step index into the native draft.
  function goToStep(step: number) {
    liveRecovery.current.step = step;
    wizard.goTo(step);
    mutate((current) => ({ ...current, step: [1, 1, 0, 2, 3][step] }));
  }
  function nextStep() {
    if (loading || inFlight.current || draft.pending || wizard.step >= 4) return;
    if (validateWizardStep(wizard.step)) goToStep(wizard.step + 1);
  }
  function backStep() {
    if (loading || inFlight.current || draft.pending) return;
    goToStep(Math.max(0, wizard.step - 1));
  }
  function chooseProfile(item: ProfileListing) {
    mutate((current) => ({ ...current, profile: { id: item.profile.profile_id, revision: item.profile.revision, sha256: item.profile_sha256 }, strategyRefs: [], step: 1 }));
    wizard.goTo(0);
    setAlert("El perfil cambió. Elegí de nuevo las estrategias compatibles antes de continuar.");
  }
  function chooseDataset(item: DatasetListing) {
    setDeepDataset(item);
    setDrawOffset(0);
    mutate((current) => ({ ...current, datasetSha256: item.dataset_sha256, selectedDraw: null, strategyRefs: [], conditions: { ...current.conditions, start_draw: "" }, step: 1 }));
    wizard.goTo(0);
    setAlert("El historial cambió. Se retiraron las estrategias seleccionadas; elegí de nuevo sus revisiones compatibles y luego el sorteo inicial.");
  }
  function chooseStartDraw(value: string) {
    const index = draws?.items.indexOf(value) ?? -1;
    if (index < 0 || !selectedDataset || !draws) { mutate((current) => ({ ...current, selectedDraw: null, conditions: { ...current.conditions, start_draw: value } })); return; }
    mutate((current) => ({ ...current, selectedDraw: { datasetSha256: selectedDataset.dataset_sha256, index: draws.offset + index, draw: value },
      conditions: { ...current.conditions, start_draw: value } }));
  }
  async function loadDraws() {
    if (!selectedDataset) return;
    const datasetSha256 = selectedDataset.dataset_sha256;
    const offset = drawOffset;
    const ticket = ++drawGeneration.current;
    try { const page = await apiClient.getDatasetDraws(datasetSha256, offset, 100); if (mounted.current && drawGeneration.current === ticket) setDraws(page); }
    catch (cause) { if (mounted.current && drawGeneration.current === ticket) setErrors((old) => ({ ...old, draws: errorText(cause, "cargar sorteos") })); }
  }
  useEffect(() => {
    setDraws(null);
    if (!selectedDataset) return;
    let live = true;
    const ticket = ++drawGeneration.current;
    void apiClient.getDatasetDraws(selectedDataset.dataset_sha256, drawOffset, 100)
      .then((page) => { if (live && mounted.current && drawGeneration.current === ticket) setDraws(page); })
      .catch((cause: unknown) => { if (live && mounted.current && drawGeneration.current === ticket) setErrors((old) => ({ ...old, draws: errorText(cause, "cargar sorteos") })); });
    return () => { live = false; };
  }, [selectedDataset?.dataset_sha256, drawOffset]);

  function toggleStrategy(strategy: ProfileBatchStrategy) {
    if (strategy.execution_available !== true || strategy.profile_compatible !== true) { setAlert("Esta estrategia no es compatible con el perfil."); return; }
    const key = (ref: StrategyReference) => `${ref.id}@${ref.revision}`;
    mutate((current) => {
      const has = current.strategyRefs.some((ref) => key(ref) === `${strategy.id}@${strategy.revision}`);
      if (has) return { ...current, strategyRefs: current.strategyRefs.filter((ref) => key(ref) !== `${strategy.id}@${strategy.revision}`) };
      const maximum = Math.min(3, policy?.policy.max_strategies_per_batch ?? 3);
      if (current.strategyRefs.length >= maximum) { setAlert(`Máximo ${maximum} estrategias por simulación.`); return current; }
      return { ...current, strategyRefs: [...current.strategyRefs, { id: strategy.id, revision: strategy.revision, definition_sha256: strategy.definition_sha256 }] };
    });
  }
  function loadEditor(strategy?: ProfileBatchStrategy, makeCopy = false) {
    const d = strategy?.definition;
    const supported = !d || ((d.selector === "static-numbers/v1" || d.selector === "seeded-random/hash-sha256-v1") && d.staking === "flat-per-number/v1");
    setEditorAvailable(supported);
    setEditTarget(makeCopy ? null : strategy ?? null);
    setEditDefinition(d ? { ...d, selector_parameters: { ...d.selector_parameters }, staking_parameters: { ...d.staking_parameters }, closing_defaults: { ...d.closing_defaults } } : null);
    if (!supported) { setAlert("No se puede editar ni copiar esta estrategia sin cambiarla."); return; }
    setDefinitionName(d ? makeCopy ? `${d.name} copia` : d.name : ""); setCoverage(String(d?.coverage ?? 1)); setSelector(d?.selector === "seeded-random/hash-sha256-v1" ? d.selector : "static-numbers/v1");
    setNumbers(Array.isArray(d?.selector_parameters.numbers) ? d.selector_parameters.numbers.join(", ") : "");
    setSeed(String(d?.selector_parameters.seed ?? 0));
    const storedStake = d?.staking_parameters.per_number_stake;
    setStake(d ? formatMinorUnitsInput(typeof storedStake === "number" ? storedStake : 1, selectedProfile?.profile.scale ?? 0) : "1");
  }
  async function saveStrategy(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedProfile) return;
    try {
      const count = wholeNumber(coverage, "Cobertura", 1n, BigInt(Math.min(1000, selectedProfile.profile.universe_size, selectedProfile.profile.max_coverage)));
      const nums = selector === "static-numbers/v1" ? numbers.split(",").map((part) => part.trim()).map(Number) : [];
      if (selector === "static-numbers/v1" && (nums.length !== count || nums.some((n) => !Number.isSafeInteger(n) || n < 0 || n >= selectedProfile.profile.universe_size) || new Set(nums).size !== nums.length)) throw new Error("Ingresá tantos números distintos como la cobertura, dentro del universo.");
      const seedNumber = selector === "static-numbers/v1" ? 0 : wholeNumber(seed, "Semilla", 0n, BigInt(Number.MAX_SAFE_INTEGER));
      const stakeNumber = moneyUnits(stake, selectedProfile.profile.scale, "Apuesta por número");
      if (stakeNumber < selectedProfile.profile.minimum_stake || stakeNumber > selectedProfile.profile.maximum_stake || stakeNumber % selectedProfile.profile.stake_increment) throw new Error("La apuesta debe respetar el mínimo, el máximo y el incremento del perfil.");
      if (!definitionName.trim()) throw new Error("Ingresá un nombre para la estrategia.");
      const definition: ClosedStrategyDefinition = {
        ...(editDefinition ?? genericDefinition(definitionName.trim(), count, selector, nums, seedNumber, stakeNumber, "all")),
        name: definitionName.trim(), coverage: count, selector, staking: "flat-per-number/v1",
        selector_parameters: selector === "static-numbers/v1" ? { numbers: nums } : { seed: seedNumber },
        staking_parameters: { ...editDefinition?.staking_parameters, per_number_stake: stakeNumber },
        closing_defaults: { ...editDefinition?.closing_defaults },
      };
      const saved = editTarget && !editTarget.protected
        ? await apiClient.reviseProfileBatchStrategy(editTarget.id, editTarget.latest_revision, definition)
        : await apiClient.createProfileBatchStrategy(definition);
      if (mounted.current) { setStrategies((page) => page ? { ...page, items: [saved, ...page.items.filter((item) => item.id !== saved.id)] } : page); setEditTarget(null); setAlert("Estrategia guardada. Elegí qué revisión usar."); }
    } catch (cause) { if (mounted.current) setAlert(cause instanceof Error && !(cause instanceof ApiError) ? cause.message : errorText(cause, "guardar la estrategia")); }
  }
  async function loadStrategyRevisions(strategy: ProfileBatchStrategy) {
    try {
      const revisions: ProfileBatchStrategy[] = [];
      let offset = 0;
      let total = 0;
      do {
        const page = await apiClient.getProfileBatchStrategyRevisions(strategy.id, offset, 100);
        revisions.push(...page.items); total = page.total; offset += page.items.length;
        if (!page.items.length) break;
      } while (offset < total);
      if (mounted.current) setStrategyRevisions((current) => ({ ...current, [strategy.id]: revisions }));
    } catch (cause) { if (mounted.current) setAlert(errorText(cause, "cargar las revisiones")); }
  }
  function chooseExactRevision(strategy: ProfileBatchStrategy) {
    if (!draft.profile || !strategy.definition_sha256 || !hashPattern.test(strategy.definition_sha256)) return;
    if (strategy.definition_valid !== true) { setAlert("Esa revisión no es válida."); return; }
    if (draft.strategyRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision)) return;
    if (draft.strategyRefs.length >= Math.min(3, policy?.policy.max_strategies_per_batch ?? 3)) { setAlert("Se alcanzó el máximo de estrategias."); return; }
    mutate((current) => ({ ...current, strategyRefs: [...current.strategyRefs, { id: strategy.id, revision: strategy.revision, definition_sha256: strategy.definition_sha256 }] }));
    setAlert("Revisión agregada.");
  }
  async function exactStrategy(strategy: ProfileBatchStrategy) {
    if (!draft.profile) return;
    const ticket = generation.current;
    try {
      const exact = await apiClient.getProfileBatchStrategy(strategy.id, draft.profile);
      if (!mounted.current || generation.current !== ticket) return;
      if (exact.revision !== strategy.revision || exact.definition_sha256 !== strategy.definition_sha256) throw new Error("La estrategia cambió; actualizá y elegí de nuevo.");
      if (!exact.profile_compatible) throw new Error(exact.incompatibilities.join("; ") || "La estrategia no es compatible con este perfil.");
      toggleStrategy(exact);
    } catch (cause) { setAlert(cause instanceof Error ? cause.message : errorText(cause, "leer estrategia")); }
  }
  function makeBody() {
    if (!selectedProfile) throw new Error("Elegí un perfil compatible con los datos.");
    if (!draft.selectedDraw || draft.selectedDraw.datasetSha256 !== draft.datasetSha256 || draft.selectedDraw.draw !== draft.conditions.start_draw) {
      throw new Error("Elegí un sorteo inicial de estos datos.");
    }
    return buildBatchBody(draft, selectedProfile.profile.scale, crypto.randomUUID());
  }
  function validateWizardStep(step: number): boolean {
    if (step === 0) return Boolean(selectedProfile && selectedRefs.length > 0);
    if (step === 1) return Boolean(draft.conditions.settlement);
    if (step === 2) return Boolean(selectedDataset && draft.selectedDraw?.datasetSha256 === draft.datasetSha256 && draft.selectedDraw.draw === draft.conditions.start_draw && repeatReady && !baseError);
    if (step === 3) {
      try { makeBody(); return true; } catch (cause) { setAlert(cause instanceof Error ? cause.message : "Revisá los campos."); return false; }
    }
    return true;
  }
  async function validateBatch() {
    try {
      const body = makeBody();
      const frozen = { ...body, client_request_id: "validation-only" };
      const key = JSON.stringify({ profile: draft.profile, dataset: draft.datasetSha256, refs: draft.strategyRefs, conditions: draft.conditions });
      setLoading(true); setAlert("");
      const ticket = generation.current;
      const result = await apiClient.validateProfileBatch(frozen);
      if (mounted.current && generation.current === ticket) setValidated({ bodyKey: key, result });
    } catch (cause) {
      if (mounted.current) {
        const message = cause instanceof Error && !(cause instanceof ApiError) ? cause.message : errorText(cause, "validar la simulación");
        setAlert(message);
        goToStep(/sorteo|historial|perfil/i.test(message) ? 2 : /liquid|premio/i.test(message) ? 1 : 3);
        setAlert(message);
      }
    }
    finally { if (mounted.current) setLoading(false); }
  }
  function retirePending(requestId: string, operation: number) {
    if (pendingOperation.current !== operation) return;
    try {
      const saved = parseBatchDraft(sessionStorage.getItem(repeatStorageKey));
      if (saved?.pending?.clientRequestId === requestId) {
        sessionStorage.setItem(repeatStorageKey, serializeBatchDraft({ ...saved, pending: null }));
      }
    } catch { if (mounted.current) setStorageWarning(true); }
    flushSync(() => setDraft((current) => current.pending?.clientRequestId === requestId ? { ...current, pending: null } : current));
  }
  async function resolvePending() {
    const pending = draft.pending;
    if (!pending || inFlight.current || wizard.step !== 4 || liveRecovery.current.step !== 4) return;
    const context = repeatStorageKey;
    const operation = ++pendingOperation.current;
    inFlight.current = true; setLoading(true); setAlert("");
    try {
      let response;
      try { response = await apiClient.getProfileBatchByClientRequestId(pending.clientRequestId); }
      catch (cause) {
        if (!(cause instanceof ApiError && cause.status === 404)) throw cause;
      }
      if (!response) {
        // The lookup can outlive query navigation/unmount. Only this Review may POST.
        if (!mounted.current || pendingOperation.current !== operation || liveRecovery.current.step !== 4 ||
            liveRecovery.current.context !== context || liveRecovery.current.pendingId !== pending.clientRequestId) return;
        response = await apiClient.createProfileBatch(pending.frozenBody);
      }
      if (!mounted.current || pendingOperation.current !== operation || liveRecovery.current.context !== context ||
          liveRecovery.current.pendingId !== pending.clientRequestId || liveRecovery.current.step !== 4) return;
      if (!response.id) throw new Error("No se pudo confirmar la simulación.");
      retirePending(pending.clientRequestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? "Sin confirmación: la simulación pudo haberse creado. Al reintentar, primero se comprueba si ya existe."
        : errorText(cause, "confirmar la creación"));
    } finally { if (pendingOperation.current === operation) { inFlight.current = false; if (mounted.current) setLoading(false); } }
  }
  async function submit() {
    if (wizard.step !== 4) return;
    if (draft.pending) { await resolvePending(); return; }
    if (inFlight.current || !currentValidation?.valid || !policy) return;
    let body;
    try { body = makeBody(); } catch (cause) { setAlert(cause instanceof Error ? cause.message : "Revisá los campos."); return; }
    const requestId = body.client_request_id;
    const frozen = { clientRequestId: requestId, frozenBody: body };
    const operation = ++pendingOperation.current;
    setDraft((current) => ({ ...current, pending: frozen }));
    try { sessionStorage.setItem(repeatStorageKey, serializeBatchDraft({ ...draft, pending: frozen })); }
    catch { setStorageWarning(true); }
    inFlight.current = true; setLoading(true); setAlert("");
    try {
      const response = await apiClient.createProfileBatch(body);
      if (!mounted.current || pendingOperation.current !== operation) return;
      if (!response.id) throw new Error("No se pudo confirmar la simulación.");
      retirePending(requestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? "Sin confirmación: la simulación pudo haberse creado. Usá «Recuperar creación pendiente» o reintentá."
        : errorText(cause, "confirmar la creación"));
    } finally { if (pendingOperation.current === operation) { inFlight.current = false; if (mounted.current) setLoading(false); } }
  }

  const validationSummary = currentValidation && <div role="status" className="space-y-2 border-y border-border py-3"><h4 className="font-medium">{currentValidation.valid ? "Validación aceptada" : "Validación rechazada"}</h4><p>Validar comprueba la solicitud; no reserva capacidad.</p><p>Perfil seleccionado · {selectedProfile?.profile.currency} · {selectedProfile?.profile.positions} posiciones</p><p>Historial · {selectedDataset?.first_draw}–{selectedDataset?.last_draw} · inicio {draft.conditions.start_draw}</p><p>Estrategias seleccionadas: {draft.strategyRefs.length}</p><details><summary className="disclosure-summary">Detalles técnicos</summary><div className="space-y-2 pt-2"><p>Perfil {currentValidation.profile.id} · revisión {currentValidation.profile.revision}</p><p>Historial {selectedDataset?.source_id ?? String(currentValidation.dataset.source_sha256)}</p><p>Estrategias: {draft.strategyRefs.map((ref) => `${ref.id} (revisión ${ref.revision})`).join(" → ")}</p><p>Dataset {String(currentValidation.dataset.dataset_sha256)} · filas fuente {String(currentValidation.dataset.row_count)} · archivo autenticado: {String(currentValidation.dataset.archive_bound)}</p><p>Solicitado: {JSON.stringify(currentValidation.requested_constraints)}</p><p>Efectivo tras política: {JSON.stringify(currentValidation.effective_constraints)}</p></div></details>{currentValidation.reasons.map((reason) => <p role="alert" key={reason}>{reason}</p>)}</div>;
  const currentStep = wizard.step;
  const page = <div className="max-w-4xl space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-2xl">Lote de simulaciones</h2></div>
    {requestedHash && !hashPattern.test(requestedHash) && <p role="alert">El enlace del historial no es válido.</p>}
    {storageWarning && <p role="status" className="field-help">No se pudo guardar el borrador.</p>}
    {draft.pending && currentStep === 4 && <div role="status" className="field-help">Hay una simulación pendiente de confirmar. <button type="button" className="btn btn-tertiary" disabled={loading} onClick={() => void resolvePending()}>{loading ? "Comprobando…" : "Recuperar creación pendiente"}</button></div>}
    {baseLoading && <p role="status">Recuperando y verificando la simulación guardada…</p>}
    {baseError && <p role="alert">No se puede repetir esta simulación guardada: {baseError} Revisá que la referencia siga disponible; no se sustituirán datos ni estrategias.</p>}
    {(errors.catalogs || errors.deepDataset) && <p role="alert">{errors.catalogs || errors.deepDataset} <button type="button" className="btn btn-tertiary" onClick={retryCatalogs}>Reintentar</button></p>}
    {alert && <p role="alert" tabIndex={-1}>{alert}</p>}
    <FiveStepWizard steps={[{ title: "1 · Estrategia", description: "Elegí el perfil requerido y el orden exacto de estrategias." }, { title: "2 · Reglas", description: "Definí cómo liquidar los premios del perfil." }, { title: "3 · Alcance", description: "Vinculá el historial y el sorteo inicial." }, { title: "4 · Capital y datos", description: "Completá capital, meta, presupuesto y límites." }, { title: "5 · Revisá y creá", description: "Validá la solicitud actual y confirmá la creación." }]} activeStep={currentStep} maxReachableStep={wizard.maxReachableStep} onSelectStep={goToStep} onNext={nextStep} onBack={backStep} busy={loading || baseLoading || inFlight.current || Boolean(draft.pending)}>
    {currentStep === 0 && <section aria-labelledby="strategy-prerequisite-title" className="space-y-4"><h3 id="strategy-prerequisite-title" className="section-header">Perfil y estrategias</h3>
      <label className="field"><span className="field-label">Perfil de juego</span><select className={control} value={draft.profile ? `${draft.profile.id}@${draft.profile.revision}` : ""} onChange={(e) => { const p = profiles?.items.find((candidate) => `${candidate.profile.profile_id}@${candidate.profile.revision}` === e.target.value) ?? (activePinnedProfile && `${activePinnedProfile.profile.profile_id}@${activePinnedProfile.profile.revision}` === e.target.value ? activePinnedProfile : undefined); if (p) chooseProfile(p); }}><option value="">Elegí un perfil</option>{activePinnedProfile && !profiles?.items.some((p) => p.profile.profile_id === activePinnedProfile.profile.profile_id && p.profile.revision === activePinnedProfile.profile.revision) && <option value={`${activePinnedProfile.profile.profile_id}@${activePinnedProfile.profile.revision}`}>Perfil guardado · {activePinnedProfile.profile.currency} · {activePinnedProfile.profile.positions} posiciones</option>}{profiles?.items.map((p, index) => <option key={`${p.profile.profile_id}@${p.profile.revision}`} value={`${p.profile.profile_id}@${p.profile.revision}`}>Perfil {index + 1} · {p.profile.currency} · {p.profile.positions} posiciones</option>)}</select></label>
    </section>}
    {currentStep === 2 && <section aria-labelledby="context-title" className="space-y-4"><h3 id="context-title" className="section-header">Historial y perfil</h3>
      <label className="field"><span className="field-label">Historial</span><select className={control} value={draft.datasetSha256 === "0".repeat(64) ? "" : draft.datasetSha256} onChange={(e) => { const item = datasets?.items.find((candidate) => candidate.dataset_sha256 === e.target.value); if (item) chooseDataset(item); }}><option value="">Elegí un historial</option>{datasets?.items.map((item, index) => <option key={item.dataset_sha256} value={item.dataset_sha256}>Historial {index + 1} · {item.records_total} sorteos</option>)}</select></label>
      {selectedDataset && <p className="field-help">{selectedDataset.records_total} sorteos · {selectedDataset.first_draw}–{selectedDataset.last_draw}</p>}<details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all">{selectedDataset?.source_id} · {selectedDataset?.source_revision} · {selectedDataset?.dataset_sha256}</p></details>
      <Pager label="historiales" page={datasets} offset={datasetOffset} setOffset={setDatasetOffset} />
      <label className="field"><span className="field-label">Perfil de juego</span><select className={control} value={draft.profile ? `${draft.profile.id}@${draft.profile.revision}` : ""} onChange={(e) => { const p = profiles?.items.find((candidate) => `${candidate.profile.profile_id}@${candidate.profile.revision}` === e.target.value) ?? (activePinnedProfile && `${activePinnedProfile.profile.profile_id}@${activePinnedProfile.profile.revision}` === e.target.value ? activePinnedProfile : undefined); if (p) chooseProfile(p); }}><option value="">Elegí un perfil de juego</option>{activePinnedProfile && !profiles?.items.some((p) => p.profile.profile_id === activePinnedProfile.profile.profile_id && p.profile.revision === activePinnedProfile.profile.revision) && <option value={`${activePinnedProfile.profile.profile_id}@${activePinnedProfile.profile.revision}`}>Perfil guardado · {activePinnedProfile.profile.currency} · {activePinnedProfile.profile.positions} posiciones</option>}{profiles?.items.map((p, index) => <option key={`${p.profile.profile_id}@${p.profile.revision}`} value={`${p.profile.profile_id}@${p.profile.revision}`}>Perfil {index + 1} · {p.profile.currency} · {p.profile.positions} posiciones</option>)}</select></label><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all">{selectedProfile?.profile.profile_id} · revisión {selectedProfile?.profile.revision} · esquema {selectedProfile?.profile.schema_version} · {selectedProfile?.profile_sha256}</p></details>
      <Pager label="perfiles" page={profiles} offset={profileOffset} setOffset={setProfileOffset} />
      {selectedProfile && selectedDataset && <p className={selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "field-help" : "text-danger"}>{selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "El historial y el perfil coinciden." : "El historial y el perfil no coinciden."}</p>}
      {selectedDataset && <label className="field"><span className="field-label">Sorteo inicial</span><select className={control} aria-label="Sorteo inicial" value={draft.conditions.start_draw} onChange={(e) => chooseStartDraw(e.target.value)}><option value="">Elegí un sorteo</option>{draft.selectedDraw?.datasetSha256 === draft.datasetSha256 && !draws?.items.includes(draft.selectedDraw.draw) && <option value={draft.selectedDraw.draw}>{draft.selectedDraw.draw} · guardado</option>}{draws?.items.map((draw) => <option key={draw} value={draw}>{draw}</option>)}</select>{errors.draws && <span role="alert">{errors.draws} <button type="button" className="btn btn-tertiary" onClick={() => void loadDraws()}>Reintentar sorteos</button></span>}<Pager label="sorteos" page={draws} offset={drawOffset} setOffset={setDrawOffset} /></label>}
      <WizardScopeSelector currentMode="batch" busy={loading || baseLoading || inFlight.current || Boolean(draft.pending)} />
    </section>}
    {currentStep === 0 && <section aria-labelledby="strategies-title" className="space-y-4"><h3 id="strategies-title" className="section-header">Estrategias guardadas · {selectedRefs.length}/3</h3>{selectedRefs.length > 0 && <ol aria-label="Orden de estrategias" className="list-decimal space-y-2 pl-5">{selectedRefs.map((reference, index) => <li key={`${reference.id}@${reference.revision}`}>{index + 1}. {strategies?.items.find((item) => item.id === reference.id && item.revision === reference.revision)?.name ?? "Estrategia seleccionada"} <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p>{reference.id} · revisión {reference.revision}</p></details> <button type="button" className="btn btn-tertiary" onClick={() => mutate((current) => ({ ...current, strategyRefs: current.strategyRefs.filter((item) => item.id !== reference.id || item.revision !== reference.revision) }))}>Quitar</button></li>)}</ol>}{!draft.profile && <p>Elegí primero historial y perfil.</p>}
      {strategies?.items.map((strategy) => <article key={`${strategy.id}@${strategy.revision}`} className="space-y-2 border-b border-border py-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><h4 className="font-medium">{strategy.name}</h4><p className="field-help">{strategy.preset_explanation ?? `Cobertura ${strategy.definition.coverage}`}</p><p className="field-help">{strategy.execution_available ? "Compatible con el perfil." : strategy.execution_unavailable_reason ?? strategy.incompatibilities.join("; ")}</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><dl className="data-list break-all pt-2"><dt>ID y revisión</dt><dd>{strategy.id} · {strategy.revision}</dd><dt>Definición SHA-256</dt><dd className="font-mono">{strategy.definition_sha256}</dd><dt>Selector</dt><dd>{strategy.definition.selector}</dd><dt>Apuesta</dt><dd>{strategy.definition.staking}</dd><dt>Definición guardada</dt><dd><pre className="overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(strategy.definition, null, 2)}</pre></dd></dl></details></div><button type="button" className="btn btn-secondary" disabled={!draft.profile} aria-pressed={selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision)} onClick={() => void exactStrategy(strategy)}>{selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision) ? "Quitar" : "Agregar"}</button></div>
        <button type="button" className="btn btn-tertiary" onClick={() => loadEditor(strategy, strategy.protected)}>{strategy.protected ? "Crear copia editable" : "Editar y guardar nueva revisión"}</button> <button type="button" className="btn btn-tertiary" onClick={() => void loadStrategyRevisions(strategy)}>Ver revisiones</button>{strategyRevisions[strategy.id] && <details><summary className="disclosure-summary text-sm">Detalles técnicos · revisiones</summary><ul aria-label={`Revisiones de ${strategy.name}`} className="list-disc pl-5">{strategyRevisions[strategy.id].map((revision) => <li key={revision.revision}>Revisión {revision.revision} · {revision.definition.name} <button type="button" className="btn btn-tertiary" onClick={() => chooseExactRevision(revision)}>Usar esta revisión</button></li>)}</ul></details>}</article>)}
      <Pager label="estrategias" page={strategies} offset={strategyOffset} setOffset={setStrategyOffset} />
      {editorAvailable ? <form className="space-y-3 border-t border-border pt-4" onSubmit={(event) => void saveStrategy(event)}><h4 className="font-medium">Nueva estrategia</h4><p className="field-help">Solo selección fija o azar reproducible, con apuesta plana.</p>
        <label className="field"><span className="field-label">Nombre</span><input className={control} value={definitionName} onChange={(e) => setDefinitionName(e.target.value)} maxLength={80} required /></label>
        <details><summary className="disclosure-summary">Ajustes avanzados</summary><div className="space-y-3 pt-3">
          <label className="field"><span className="field-label">Selector</span><select className={control} value={selector} onChange={(e) => setSelector(e.target.value as typeof selector)}><option value="static-numbers/v1">Números fijos</option><option value="seeded-random/hash-sha256-v1">Azar reproducible</option></select></label>
          <label className="field"><span className="field-label">Cobertura</span><input className={control} inputMode="numeric" value={coverage} onChange={(e) => setCoverage(e.target.value)} /></label>
          {selector === "static-numbers/v1" ? <label className="field"><span className="field-label">Números distintos, separados por comas</span><input className={control} value={numbers} onChange={(e) => setNumbers(e.target.value)} /></label> : <label className="field"><span className="field-label">Semilla</span><input className={control} inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)} /></label>}
          <label className="field"><span className="field-label">Apuesta por número ({selectedProfile?.profile.currency ?? "moneda"})</span><input className={control} inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} /></label>
        </div></details>
        <button className="btn btn-secondary" type="submit">{editTarget && !editTarget.protected ? "Guardar nueva revisión" : "Guardar como estrategia nueva"}</button>
      </form> : <p className="field-help border-t border-border pt-4">Esta estrategia no se puede editar ni copiar con este editor.</p>}
    </section>}
    {currentStep === 1 && <section aria-labelledby="batch-rules-title" className="space-y-4"><h3 id="batch-rules-title" className="section-header">Reglas del perfil</h3>{selectedProfile ? <GameRulesSummary view={profileRulesView(selectedProfile, "Catálogo de perfiles /catalog/profiles · revisión exacta seleccionada para el lote", draft.conditions.settlement === "all" || draft.conditions.settlement === "best" ? draft.conditions.settlement : undefined)} /> : <p>Elegí un perfil en Estrategia.</p>}<label className="field"><span className="field-label">Cómo contar los premios</span><select className={control} disabled={!selectedProfile} value={draft.conditions.settlement} onChange={(e) => updateCondition("settlement", e.target.value)}><option value="">Elegí una regla</option>{selectedProfile?.profile_execution.settlements.map((settlement) => <option key={settlement} value={settlement}>{profileSettlementLabel(selectedProfile.profile, settlement)}</option>)}</select></label></section>}
    {currentStep === 3 && <section aria-labelledby="conditions-title" className="space-y-4"><h3 id="conditions-title" className="section-header">Condiciones comunes</h3>
      <div className="space-y-6"><fieldset className="min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Capital y meta</legend><div className="grid gap-4 sm:grid-cols-2">{([ ["capital", `Capital inicial (${selectedProfile?.profile.currency ?? "moneda"})`], ["goal", `Meta de saldo (${selectedProfile?.profile.currency ?? "moneda"})`] ] as const).map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className={control} inputMode="decimal" value={draft.conditions[key]} onChange={(e) => updateCondition(key, e.target.value)} /></label>)}</div></fieldset>
        <fieldset className="min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Ventana</legend><div className="grid gap-4 sm:grid-cols-2">{([ ["max_elapsed_draws", "Máximo sorteos transcurridos"], ["max_bet_draws", "Máximo sorteos apostados (opcional)"], ["max_draws", "Límite operativo solicitado"] ] as const).map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className={control} inputMode="decimal" value={draft.conditions[key]} onChange={(e) => updateCondition(key, e.target.value)} /></label>)}</div></fieldset>
</div>
      {policy && <p className="field-help">Límites actuales: hasta {policy.policy.max_strategies_per_batch} estrategias, {policy.policy.max_bet_draws} sorteos apostados y {policy.policy.max_elapsed_draws} transcurridos.</p>}
      {selectedRefs.map((ref, index) => { const item = strategies?.items.find((strategy) => strategy.id === ref.id && strategy.revision === ref.revision); const recommendation = item?.definition.closing_defaults; return <p key={`${ref.id}@${ref.revision}`} className="field-help">Estrategia {index + 1}: {item?.name ?? "seleccionada"}. Recomienda «{settlementName(recommendation?.settlement)}»; se usa «{settlementName(draft.conditions.settlement)}».</p>; })}
    </section>}
    {currentStep === 4 && <section aria-labelledby="simulate-title" className="space-y-4"><h3 id="simulate-title" className="section-header">Revisar, validar y confirmar</h3><p>Cualquier cambio invalida la validación. Se enviará únicamente la solicitud que se validó.</p>
      <dl className="data-list"><dt>Capital</dt><dd>{draft.conditions.capital} {selectedProfile?.profile.currency ?? "moneda"}</dd><dt>Meta</dt><dd>{draft.conditions.goal} {selectedProfile?.profile.currency ?? "moneda"}</dd><dt>Duración</dt><dd>{draft.conditions.max_elapsed_draws || "Sin límite"} sorteos transcurridos</dd><dt>Advertencia</dt><dd>Simula, no predice ni garantiza rentabilidad.</dd></dl>
      <button type="button" className="btn btn-secondary" disabled={loading || baseLoading || !repeatReady || Boolean(baseError) || !selectedProfile || !selectedDataset || selectedRefs.length < 1 || !policy} onClick={() => void validateBatch()}>Validar solicitud actual</button>
      {validationSummary}
      <button type="button" className="btn btn-primary" disabled={loading || baseLoading || !repeatReady || Boolean(baseError) || !currentValidation?.valid || !policy} onClick={() => void submit()}>{loading ? "Procesando…" : "Crear simulaciones"}</button></section>}
    </FiveStepWizard>
  </div>;
  return page;
}

function settlementName(value: unknown): string {
  if (value === "all") return "Sumar todas las posiciones";
  if (value === "best") return "Mayor premio";
  return "sin elegir";
}

function Pager({ label, page, offset, setOffset }: { label: string; page: Page<unknown> | null; offset: number; setOffset: (offset: number) => void }) {
  if (!page || page.total <= page.limit) return null;
  return <nav aria-label={`Páginas de ${label}`} className="flex items-center gap-3"><button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - page.limit))}>Anterior</button><span>{offset + 1}–{Math.min(offset + page.limit, page.total)} de {page.total}</span><button type="button" className="btn btn-secondary" disabled={offset + page.limit >= page.total} onClick={() => setOffset(offset + page.limit)}>Siguiente</button></nav>;
}
