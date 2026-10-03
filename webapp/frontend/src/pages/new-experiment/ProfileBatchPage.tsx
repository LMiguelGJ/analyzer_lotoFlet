import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { DatasetListing, Page, ProfileBatchExecutionPolicy, ProfileBatchStrategy, ProfileBatchValidation, ProfileListing } from "../../api/types";
import { moneyUnits, wholeNumber } from "../../lib/profile-input";
import { BATCH_DRAFT_STORAGE_KEY, buildBatchBody, createBatchDraft, parseBatchDraft, serializeBatchDraft, type BatchDraft, type ClosedStrategyDefinition, type StrategyReference } from "./batch-model";

const control = "control";
const hashPattern = /^[0-9a-f]{64}$/;
const genericDefinition = (name: string, coverage: number, selector: ClosedStrategyDefinition["selector"], numbers: number[], seed: number, stake: number, settlement: "all" | "best"): ClosedStrategyDefinition => ({
  definition_version: 1, name, selector, coverage, staking: "flat-per-number/v1",
  selector_parameters: selector === "static-numbers/v1" ? { numbers } : { seed },
  staking_parameters: { per_number_stake: stake }, closing_defaults: { settlement },
});

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
  const [draft, setDraft] = useState<BatchDraft>(() => initialHash ? createBatchDraft(initialHash) : createBatchDraft("0".repeat(64)));
  const [profiles, setProfiles] = useState<Page<ProfileListing> | null>(null);
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
  const restored = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current++; };
  }, []);
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    try {
      const raw = sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY);
      const saved = parseBatchDraft(raw);
      if (saved) {
        setDraft(saved);
        if (initialHash && saved.datasetSha256 !== initialHash) setAlert("El enlace apunta a otro historial; se conservó el borrador. Elegí el historial nuevo para cambiar.");
      } else if (raw) { setStorageWarning(true); setAlert("El borrador guardado ya no es compatible y no se restauró."); }
    } catch { setStorageWarning(true); }
  }, [initialHash]);
  useEffect(() => {
    try { sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, serializeBatchDraft(draft)); }
    catch { setStorageWarning(true); }
  }, [draft]);

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

  const selectedProfile = profiles?.items.find((item) => item.profile.profile_id === draft.profile?.id && item.profile.revision === draft.profile.revision && item.profile_sha256 === draft.profile.sha256) ?? null;
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
  function chooseProfile(item: ProfileListing) {
    mutate((current) => ({ ...current, profile: { id: item.profile.profile_id, revision: item.profile.revision, sha256: item.profile_sha256 }, strategyRefs: [], step: 0 }));
  }
  function chooseDataset(item: DatasetListing) {
    setDeepDataset(item);
    setDrawOffset(0);
    mutate((current) => ({ ...current, datasetSha256: item.dataset_sha256, selectedDraw: null, strategyRefs: [], conditions: { ...current.conditions, start_draw: "" }, step: 0 }));
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
      if (current.strategyRefs.length >= maximum) { setAlert(`Máximo ${maximum} estrategias por lote.`); return current; }
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
      if (mounted.current) { setStrategies((page) => page ? { ...page, items: [saved, ...page.items.filter((item) => item.id !== saved.id)] } : page); setEditTarget(null); setAlert("Estrategia guardada. Elegí qué revisión usar en el lote."); }
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
  async function validateBatch() {
    try {
      const body = makeBody();
      const frozen = { ...body, client_request_id: "validation-only" };
      const key = JSON.stringify({ profile: draft.profile, dataset: draft.datasetSha256, refs: draft.strategyRefs, conditions: draft.conditions });
      setLoading(true); setAlert("");
      const ticket = generation.current;
      const result = await apiClient.validateProfileBatch(frozen);
      if (mounted.current && generation.current === ticket) { setValidated({ bodyKey: key, result }); setDraft((current) => ({ ...current, step: 4 })); }
    } catch (cause) { if (mounted.current) setAlert(cause instanceof Error && !(cause instanceof ApiError) ? cause.message : errorText(cause, "validar el lote")); }
    finally { if (mounted.current) setLoading(false); }
  }
  function retirePending(requestId: string, operation: number) {
    if (pendingOperation.current !== operation) return;
    try {
      const saved = parseBatchDraft(sessionStorage.getItem(BATCH_DRAFT_STORAGE_KEY));
      if (saved?.pending?.clientRequestId === requestId) {
        sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, serializeBatchDraft({ ...saved, pending: null }));
      }
    } catch { if (mounted.current) setStorageWarning(true); }
    flushSync(() => setDraft((current) => current.pending?.clientRequestId === requestId ? { ...current, pending: null } : current));
  }
  async function resolvePending() {
    const pending = draft.pending;
    if (!pending || inFlight.current) return;
    const operation = ++pendingOperation.current;
    inFlight.current = true; setLoading(true); setAlert("");
    try {
      let response;
      try { response = await apiClient.getProfileBatchByClientRequestId(pending.clientRequestId); }
      catch (cause) {
        if (!(cause instanceof ApiError && cause.status === 404)) throw cause;
      }
      response ??= await apiClient.createProfileBatch(pending.frozenBody);
      if (!mounted.current || pendingOperation.current !== operation) return;
      if (!response.id) throw new Error("No se pudo confirmar el lote.");
      retirePending(pending.clientRequestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? "Sin confirmación: el lote pudo haberse creado. Al reintentar, primero se comprueba si ya existe."
        : errorText(cause, "confirmar la creación"));
    } finally { if (pendingOperation.current === operation) { inFlight.current = false; if (mounted.current) setLoading(false); } }
  }
  async function submit() {
    if (draft.pending) { await resolvePending(); return; }
    if (inFlight.current || !currentValidation?.valid || !policy) return;
    let body;
    try { body = makeBody(); } catch (cause) { setAlert(cause instanceof Error ? cause.message : "Revisá los campos."); return; }
    const requestId = body.client_request_id;
    const frozen = { clientRequestId: requestId, frozenBody: body };
    const operation = ++pendingOperation.current;
    setDraft((current) => ({ ...current, pending: frozen }));
    try { sessionStorage.setItem(BATCH_DRAFT_STORAGE_KEY, serializeBatchDraft({ ...draft, pending: frozen })); }
    catch { setStorageWarning(true); }
    inFlight.current = true; setLoading(true); setAlert("");
    try {
      const response = await apiClient.createProfileBatch(body);
      if (!mounted.current || pendingOperation.current !== operation) return;
      if (!response.id) throw new Error("No se pudo confirmar el lote.");
      retirePending(requestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? "Sin confirmación: el lote pudo haberse creado. Usá «Recuperar creación pendiente» o reintentá."
        : errorText(cause, "confirmar la creación"));
    } finally { if (pendingOperation.current === operation) { inFlight.current = false; if (mounted.current) setLoading(false); } }
  }

  const validationSummary = currentValidation && <div role="status" className="space-y-2 border-y border-border py-3"><h4 className="font-medium">{currentValidation.valid ? "Validación aceptada" : "Validación rechazada"}</h4><p>Validar comprueba la solicitud; no reserva capacidad.</p><p>Perfil {currentValidation.profile.id} · revisión {currentValidation.profile.revision} · {selectedProfile?.profile.currency} · {selectedProfile?.profile.positions} posiciones</p><p>Historial {selectedDataset?.source_id ?? String(currentValidation.dataset.source_sha256)} · {selectedDataset?.first_draw}–{selectedDataset?.last_draw} · inicio {draft.conditions.start_draw}</p><p>Estrategias en orden: {draft.strategyRefs.map((ref) => `${ref.id} (revisión ${ref.revision})`).join(" → ")}</p><details><summary className="disclosure-summary">Detalles técnicos</summary><div className="space-y-2 pt-2"><p>Dataset {String(currentValidation.dataset.dataset_sha256)} · filas fuente {String(currentValidation.dataset.row_count)} · archivo autenticado: {String(currentValidation.dataset.archive_bound)}</p><p>Solicitado: {JSON.stringify(currentValidation.requested_constraints)}</p><p>Efectivo tras política: {JSON.stringify(currentValidation.effective_constraints)}</p></div></details>{currentValidation.reasons.map((reason) => <p role="alert" key={reason}>{reason}</p>)}</div>;
  const currentStep = draft.step;
  const setStep = (step: number) => mutate((current) => ({ ...current, step }));
  const page = <div className="max-w-4xl space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-2xl">Crear lote de sesiones</h2></div>
    {requestedHash && !hashPattern.test(requestedHash) && <p role="alert">El enlace del historial no es válido.</p>}
    {storageWarning && <p role="status" className="field-help">No se pudo guardar el borrador.</p>}
    {draft.pending && <div role="status" className="field-help">Hay un lote pendiente de confirmar. <button type="button" className="btn btn-tertiary" disabled={loading} onClick={() => void resolvePending()}>{loading ? "Comprobando…" : "Recuperar creación pendiente"}</button></div>}
    {(errors.catalogs || errors.deepDataset) && <p role="alert">{errors.catalogs || errors.deepDataset} <button type="button" className="btn btn-tertiary" onClick={retryCatalogs}>Reintentar</button></p>}
    {alert && <p role="alert" tabIndex={-1}>{alert}</p>}
    <nav aria-label="Pasos del lote" className="flex flex-wrap gap-2">{["Historial y perfil", "Estrategias", "Condiciones", "Validación", "Simulación"].map((label, index) => <button key={label} type="button" className={`btn btn-tertiary ${index === currentStep ? "border-accent font-semibold underline" : ""}`} aria-current={index === currentStep ? "step" : undefined} onClick={() => setStep(index)}>{label}</button>)}</nav>
    {currentStep === 0 && <section aria-labelledby="context-title" className="space-y-4"><h3 id="context-title" className="section-header">Historial y perfil</h3>
      <label className="field"><span className="field-label">Historial</span><select className={control} value={draft.datasetSha256 === "0".repeat(64) ? "" : draft.datasetSha256} onChange={(e) => { const item = datasets?.items.find((candidate) => candidate.dataset_sha256 === e.target.value); if (item) chooseDataset(item); }}><option value="">Elegí un historial</option>{datasets?.items.map((item) => <option key={item.dataset_sha256} value={item.dataset_sha256}>{item.source_id} · {item.records_total} sorteos</option>)}</select></label>
      {selectedDataset && <p className="field-help">{selectedDataset.source_id} · {selectedDataset.records_total} sorteos · {selectedDataset.first_draw}–{selectedDataset.last_draw}</p>}
      <Pager label="historiales" page={datasets} offset={datasetOffset} setOffset={setDatasetOffset} />
      <label className="field"><span className="field-label">Perfil y revisión</span><select className={control} value={draft.profile ? `${draft.profile.id}@${draft.profile.revision}` : ""} onChange={(e) => { const p = profiles?.items.find((candidate) => `${candidate.profile.profile_id}@${candidate.profile.revision}` === e.target.value); if (p) chooseProfile(p); }}><option value="">Elegí un perfil</option>{profiles?.items.map((p) => <option key={`${p.profile.profile_id}@${p.profile.revision}`} value={`${p.profile.profile_id}@${p.profile.revision}`}>{p.profile.profile_id} · revisión {p.profile.revision} · {p.profile.currency} · {p.profile.positions} posiciones</option>)}</select></label>
      <Pager label="perfiles" page={profiles} offset={profileOffset} setOffset={setProfileOffset} />
      {selectedProfile && selectedDataset && <p className={selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "field-help" : "text-danger"}>{selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "El historial y el perfil coinciden." : "El historial y el perfil no coinciden."}</p>}
    </section>}
    {currentStep === 1 && <section aria-labelledby="strategies-title" className="space-y-4"><h3 id="strategies-title" className="section-header">Estrategias guardadas · {selectedRefs.length}/3</h3>{selectedRefs.length > 0 && <ol aria-label="Orden del lote" className="list-decimal space-y-2 pl-5">{selectedRefs.map((reference, index) => <li key={`${reference.id}@${reference.revision}`}>{index + 1}. {reference.id} · revisión {reference.revision} <button type="button" className="btn btn-tertiary" onClick={() => mutate((current) => ({ ...current, strategyRefs: current.strategyRefs.filter((item) => item.id !== reference.id || item.revision !== reference.revision) }))}>Quitar</button></li>)}</ol>}{!draft.profile && <p>Elegí primero historial y perfil.</p>}
      {strategies?.items.map((strategy) => <article key={`${strategy.id}@${strategy.revision}`} className="space-y-2 border-b border-border py-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><h4 className="font-medium">{strategy.name} · revisión {strategy.revision}{strategy.protected ? " · referencia protegida" : ""}</h4><p className="field-help">{strategy.preset_explanation ?? `Cobertura ${strategy.definition.coverage}`}</p><p className="field-help">{strategy.execution_available ? "Compatible con el perfil." : strategy.execution_unavailable_reason ?? strategy.incompatibilities.join("; ")}</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><dl className="data-list break-all pt-2"><dt>ID y revisión</dt><dd>{strategy.id} · {strategy.revision}</dd><dt>Definición SHA-256</dt><dd className="font-mono">{strategy.definition_sha256}</dd><dt>Selector</dt><dd>{strategy.definition.selector}</dd><dt>Apuesta</dt><dd>{strategy.definition.staking}</dd><dt>Definición guardada</dt><dd><pre className="overflow-x-auto whitespace-pre-wrap break-all">{JSON.stringify(strategy.definition, null, 2)}</pre></dd></dl></details></div><button type="button" className="btn btn-secondary" disabled={!draft.profile} aria-pressed={selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision)} onClick={() => void exactStrategy(strategy)}>{selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision) ? "Quitar" : "Agregar"}</button></div>
        <button type="button" className="btn btn-tertiary" onClick={() => loadEditor(strategy, strategy.protected)}>{strategy.protected ? "Crear copia editable" : "Editar y guardar nueva revisión"}</button> <button type="button" className="btn btn-tertiary" onClick={() => void loadStrategyRevisions(strategy)}>Ver revisiones</button>{strategyRevisions[strategy.id] && <ul aria-label={`Revisiones de ${strategy.name}`} className="list-disc pl-5">{strategyRevisions[strategy.id].map((revision) => <li key={revision.revision}>Revisión {revision.revision} · {revision.definition.name} <button type="button" className="btn btn-tertiary" onClick={() => chooseExactRevision(revision)}>Usar esta revisión</button></li>)}</ul>}</article>)}
      <Pager label="estrategias" page={strategies} offset={strategyOffset} setOffset={setStrategyOffset} />
      {editorAvailable ? <form className="space-y-3 border-t border-border pt-4" onSubmit={(event) => void saveStrategy(event)}><h4 className="font-medium">Nueva estrategia</h4><p className="field-help">Solo selección fija o azar reproducible, con apuesta plana.</p>
        <label className="field"><span className="field-label">Nombre</span><input className={control} value={definitionName} onChange={(e) => setDefinitionName(e.target.value)} maxLength={80} required /></label>
        <label className="field"><span className="field-label">Selector</span><select className={control} value={selector} onChange={(e) => setSelector(e.target.value as typeof selector)}><option value="static-numbers/v1">Números fijos</option><option value="seeded-random/hash-sha256-v1">Azar reproducible</option></select></label>
        <label className="field"><span className="field-label">Cobertura</span><input className={control} inputMode="numeric" value={coverage} onChange={(e) => setCoverage(e.target.value)} /></label>
        {selector === "static-numbers/v1" ? <label className="field"><span className="field-label">Números distintos, separados por comas</span><input className={control} value={numbers} onChange={(e) => setNumbers(e.target.value)} /></label> : <label className="field"><span className="field-label">Semilla</span><input className={control} inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)} /></label>}
        <label className="field"><span className="field-label">Apuesta por número ({selectedProfile?.profile.currency ?? "moneda"})</span><input className={control} inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} /></label>
        <button className="btn btn-secondary" type="submit">{editTarget && !editTarget.protected ? "Guardar nueva revisión" : "Guardar como estrategia nueva"}</button>
      </form> : <p className="field-help border-t border-border pt-4">Esta estrategia no se puede editar ni copiar con este editor.</p>}
    </section>}
    {currentStep === 2 && <section aria-labelledby="conditions-title" className="space-y-4"><h3 id="conditions-title" className="section-header">Condiciones comunes</h3>
      <div className="space-y-6"><fieldset className="min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Capital y meta</legend><div className="grid gap-4 sm:grid-cols-2">{([ ["capital", `Capital inicial (${selectedProfile?.profile.currency ?? "moneda"})`], ["goal", `Meta de saldo (${selectedProfile?.profile.currency ?? "moneda"})`] ] as const).map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className={control} inputMode="decimal" value={draft.conditions[key]} onChange={(e) => updateCondition(key, e.target.value)} /></label>)}</div></fieldset>
        <fieldset className="min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Ventana</legend><div className="grid gap-4 sm:grid-cols-2">{([ ["max_elapsed_draws", "Máximo sorteos transcurridos"], ["max_bet_draws", "Máximo sorteos apostados (opcional)"], ["max_draws", "Límite operativo solicitado"] ] as const).map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className={control} inputMode="decimal" value={draft.conditions[key]} onChange={(e) => updateCondition(key, e.target.value)} /></label>)}</div></fieldset>
        <fieldset className="min-w-0 border-0 p-0"><legend className="section-header mb-3 p-0">Inicio y liquidación</legend><div className="grid gap-4 sm:grid-cols-2"><label className="field"><span className="field-label">Sorteo inicial</span><select className={control} value={draft.conditions.start_draw} onChange={(e) => chooseStartDraw(e.target.value)}><option value="">Elegí un sorteo</option>{draft.selectedDraw?.datasetSha256 === draft.datasetSha256 && !draws?.items.includes(draft.selectedDraw.draw) && <option value={draft.selectedDraw.draw}>{draft.selectedDraw.draw} · guardado</option>}{draws?.items.map((draw) => <option key={draw} value={draw}>{draw}</option>)}</select>{errors.draws && <span role="alert">{errors.draws} <button type="button" className="btn btn-tertiary" onClick={() => void loadDraws()}>Reintentar sorteos</button></span>}</label>
        <label className="field"><span className="field-label">Cómo contar los premios</span><select className={control} value={draft.conditions.settlement} onChange={(e) => updateCondition("settlement", e.target.value)}><option value="">Elegí una regla</option>{selectedProfile?.profile_execution.settlements.map((settlement) => <option key={settlement} value={settlement}>{settlement === "all" ? "Sumar todas las posiciones" : "Mayor premio"}</option>)}</select></label></div></fieldset></div>
      <Pager label="sorteos" page={draws} offset={drawOffset} setOffset={setDrawOffset} />
      {policy && <p className="field-help">Límites actuales: hasta {policy.policy.max_strategies_per_batch} estrategias, {policy.policy.max_bet_draws} sorteos apostados y {policy.policy.max_elapsed_draws} transcurridos.</p>}
      {selectedRefs.map((ref, index) => { const item = strategies?.items.find((strategy) => strategy.id === ref.id && strategy.revision === ref.revision); const recommendation = item?.definition.closing_defaults; return <p key={`${ref.id}@${ref.revision}`} className="field-help">Estrategia {index + 1}: {item?.name ?? ref.id}. Recomienda «{settlementName(recommendation?.settlement)}»; se usa «{settlementName(draft.conditions.settlement)}».</p>; })}
    </section>}
    {currentStep === 3 && <section aria-labelledby="validation-title" className="space-y-4"><h3 id="validation-title" className="section-header">Validar lote</h3><p>Cualquier cambio invalida la validación.</p><button type="button" className="btn btn-primary" disabled={loading || !selectedProfile || !selectedDataset || selectedRefs.length < 1 || !policy} onClick={() => void validateBatch()}>Validar lote</button>
      {validationSummary}
    </section>}
    {currentStep === 4 && <section aria-labelledby="simulate-title" className="space-y-4"><h3 id="simulate-title" className="section-header">Simular lote</h3><p>Se enviará lo que validaste.</p>
      {validationSummary}
      <button type="button" className="btn btn-primary" disabled={loading || !currentValidation?.valid || !draft.pending && !policy} onClick={() => void submit()}>{loading ? "Procesando…" : "Crear lote y simular"}</button></section>}
    <div className="flex justify-between border-t border-border pt-4"><button type="button" className="btn btn-secondary" disabled={currentStep === 0} onClick={() => setStep(currentStep - 1)}>Atrás</button><button type="button" className={currentStep < 3 ? "btn btn-primary" : "btn btn-secondary"} disabled={currentStep >= 4} onClick={() => setStep(currentStep + 1)}>Continuar</button></div>
    <p><Link className="btn btn-tertiary" to="/experimentos/nuevo">Ir al creador clásico</Link> <Link className="btn btn-tertiary" to="/experimentos/nuevo/perfil">Crear sesión con perfil</Link></p>
  </div>;
  return page;
}

function settlementName(value: unknown): string {
  return value === "all" ? "Sumar todas las posiciones" : value === "best" ? "Mayor premio" : "sin elegir";
}

function Pager({ label, page, offset, setOffset }: { label: string; page: Page<unknown> | null; offset: number; setOffset: (offset: number) => void }) {
  if (!page || page.total <= page.limit) return null;
  return <nav aria-label={`Páginas de ${label}`} className="flex items-center gap-3"><button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - page.limit))}>Anterior</button><span>{offset + 1}–{Math.min(offset + page.limit, page.total)} de {page.total}</span><button type="button" className="btn btn-secondary" disabled={offset + page.limit >= page.total} onClick={() => setOffset(offset + page.limit)}>Siguiente</button></nav>;
}
