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
  if (error instanceof NetworkError) return `No se pudo contactar al servidor para ${action}. No afirmamos que el servidor se haya detenido.`;
  if (error instanceof ApiError && error.status === 409) return "El perfil, dataset, estrategia, política o capacidad cambió. Actualizá la información y validá de nuevo.";
  if (error instanceof ApiError && error.status === 422) return "El servidor rechazó la entrada. Revisá los campos y las capacidades de las estrategias.";
  if (error instanceof ApiError && error.status === 507) return "No hay espacio disponible para guardar la estrategia.";
  return `No se pudo ${action}. Revisá el contexto antes de reintentar.`;
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
        if (initialHash && saved.datasetSha256 !== initialHash) setAlert("El enlace apunta a otro historial; se conservó el borrador y sus referencias congeladas. Elegí explícitamente el dataset nuevo para cambiar de contexto.");
      } else if (raw) { setStorageWarning(true); setAlert("El borrador guardado no coincide con el esquema vigente y no se restauró."); }
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
    }).catch((cause: unknown) => { if (mounted.current && catalogGeneration.current === ticket) setErrors((old) => ({ ...old, catalogs: errorText(cause, "cargar catálogos") })); });
  }, [profileOffset, datasetOffset, strategyOffset]);
  useEffect(() => { refreshCatalogs(); }, [refreshCatalogs]);
  function retryCatalogs() {
    refreshCatalogs();
    if (!initialHash) return;
    void apiClient.getDataset(initialHash).then((item) => { if (mounted.current) setDeepDataset(item); })
      .catch((cause: unknown) => { if (mounted.current) setErrors((old) => ({ ...old, deepDataset: errorText(cause, "abrir el dataset enlazado") })); });
  }
  useEffect(() => {
    if (!initialHash || datasets?.items.some((item) => item.dataset_sha256 === initialHash)) return;
    let live = true;
    void apiClient.getDataset(initialHash).then((item) => { if (live && mounted.current) setDeepDataset(item); })
      .catch((cause: unknown) => { if (live && mounted.current) setErrors((old) => ({ ...old, deepDataset: errorText(cause, "abrir el dataset enlazado") })); });
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
    if (strategy.execution_available !== true || strategy.profile_compatible !== true) { setAlert("Esta composición no es compatible con el perfil actual; la compatibilidad de biblioteca no garantiza admisión."); return; }
    const key = (ref: StrategyReference) => `${ref.id}@${ref.revision}`;
    mutate((current) => {
      const has = current.strategyRefs.some((ref) => key(ref) === `${strategy.id}@${strategy.revision}`);
      if (has) return { ...current, strategyRefs: current.strategyRefs.filter((ref) => key(ref) !== `${strategy.id}@${strategy.revision}`) };
      const maximum = Math.min(3, policy?.policy.max_strategies_per_batch ?? 3);
      if (current.strategyRefs.length >= maximum) { setAlert(`La política actual admite como máximo ${maximum} estrategias por lote.`); return current; }
      return { ...current, strategyRefs: [...current.strategyRefs, { id: strategy.id, revision: strategy.revision, definition_sha256: strategy.definition_sha256 }] };
    });
  }
  function loadEditor(strategy?: ProfileBatchStrategy, makeCopy = false) {
    const d = strategy?.definition;
    const supported = !d || ((d.selector === "static-numbers/v1" || d.selector === "seeded-random/hash-sha256-v1") && d.staking === "flat-per-number/v1");
    setEditorAvailable(supported);
    setEditTarget(makeCopy ? null : strategy ?? null);
    setEditDefinition(d ? { ...d, selector_parameters: { ...d.selector_parameters }, staking_parameters: { ...d.staking_parameters }, closing_defaults: { ...d.closing_defaults } } : null);
    if (!supported) { setAlert("Esta definición cerrada usa operaciones que el editor no soporta; no se puede editar ni copiar fielmente desde este editor."); return; }
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
      if (selector === "static-numbers/v1" && (nums.length !== count || nums.some((n) => !Number.isSafeInteger(n) || n < 0 || n >= selectedProfile.profile.universe_size) || new Set(nums).size !== nums.length)) throw new Error("Ingresá números distintos dentro del universo y en cantidad igual a la cobertura.");
      const seedNumber = selector === "static-numbers/v1" ? 0 : wholeNumber(seed, "Semilla", 0n, BigInt(Number.MAX_SAFE_INTEGER));
      const stakeNumber = moneyUnits(stake, selectedProfile.profile.scale, "Apuesta por número");
      if (stakeNumber < selectedProfile.profile.minimum_stake || stakeNumber > selectedProfile.profile.maximum_stake || stakeNumber % selectedProfile.profile.stake_increment) throw new Error("La apuesta debe respetar mínimo, máximo e incremento del perfil.");
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
      if (mounted.current) { setStrategies((page) => page ? { ...page, items: [saved, ...page.items.filter((item) => item.id !== saved.id)] } : page); setEditTarget(null); setAlert("Estrategia guardada. Elegí la revisión exacta para el lote."); }
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
    } catch (cause) { if (mounted.current) setAlert(errorText(cause, "cargar revisiones exactas")); }
  }
  function chooseExactRevision(strategy: ProfileBatchStrategy) {
    if (!draft.profile || !strategy.definition_sha256 || !hashPattern.test(strategy.definition_sha256)) return;
    if (strategy.definition_valid !== true) { setAlert("La revisión guardada no tiene una definición válida."); return; }
    if (draft.strategyRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision)) return;
    if (draft.strategyRefs.length >= Math.min(3, policy?.policy.max_strategies_per_batch ?? 3)) { setAlert("Se alcanzó el límite de estrategias vigente."); return; }
    mutate((current) => ({ ...current, strategyRefs: [...current.strategyRefs, { id: strategy.id, revision: strategy.revision, definition_sha256: strategy.definition_sha256 }] }));
    setAlert("Referencia exacta agregada. La validación del lote verificará compatibilidad con el perfil, archivo y condiciones.");
  }
  async function exactStrategy(strategy: ProfileBatchStrategy) {
    if (!draft.profile) return;
    const ticket = generation.current;
    try {
      const exact = await apiClient.getProfileBatchStrategy(strategy.id, draft.profile);
      if (!mounted.current || generation.current !== ticket) return;
      if (exact.revision !== strategy.revision || exact.definition_sha256 !== strategy.definition_sha256) throw new Error("La estrategia cambió; actualizá la biblioteca y elegí una revisión.");
      if (!exact.profile_compatible) throw new Error(exact.incompatibilities.join("; ") || "La estrategia no es compatible con este perfil.");
      toggleStrategy(exact);
    } catch (cause) { setAlert(cause instanceof Error ? cause.message : errorText(cause, "leer estrategia")); }
  }
  function makeBody() {
    if (!selectedProfile) throw new Error("Elegí una revisión de perfil compatible con los datos.");
    if (!draft.selectedDraw || draft.selectedDraw.datasetSha256 !== draft.datasetSha256 || draft.selectedDraw.draw !== draft.conditions.start_draw) {
      throw new Error("Elegí un sorteo canónico cargado para estos datos. El servidor verificará la referencia contra el archivo.");
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
      if (!response.id) throw new Error("La respuesta no incluyó ID de experimento.");
      retirePending(pending.clientRequestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? `No llegó confirmación; la creación pudo haberse recibido. Se conserva la identidad ${pending.clientRequestId}; al reintentar primero se consultará ese mismo ID y solo un 404 permitirá reenviar el cuerpo congelado.`
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
      if (!response.id) throw new Error("La respuesta no incluyó ID de experimento.");
      retirePending(requestId, operation);
      navigate(`/experimentos/${encodeURIComponent(response.id)}`, { replace: true });
    } catch (cause) {
      if (mounted.current && pendingOperation.current === operation) setAlert(cause instanceof NetworkError
        ? `No llegó confirmación; la creación pudo haberse recibido. Se conserva la identidad ${requestId}; recuperala o reintentala con el mismo cuerpo congelado.`
        : errorText(cause, "confirmar la creación"));
    } finally { if (pendingOperation.current === operation) { inFlight.current = false; if (mounted.current) setLoading(false); } }
  }

  const currentStep = draft.step;
  const setStep = (step: number) => mutate((current) => ({ ...current, step }));
  const page = <div className="max-w-4xl space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-2xl">Crear lote de sesiones</h2><p className="field-help max-w-prose">Elegí historial y perfil exactos, ordená hasta tres estrategias, fijá condiciones compartidas y validá la admisión antes de simular. La validación no reserva capacidad ni promete rendimiento.</p></div><Link className="text-accent underline" to="/experimentos/nuevo/perfil">Asistente de perfil v1–4</Link></div>
    {requestedHash && !hashPattern.test(requestedHash) && <p role="alert">La referencia de historial del enlace no es válida.</p>}
    {storageWarning && <p role="status" className="field-help">No se pudo guardar el borrador en esta pestaña. No incluye filas de historial ni credenciales.</p>}
    {draft.pending && <div role="status" className="field-help">Hay una creación con identidad pendiente {draft.pending.clientRequestId}. Se conserva el cuerpo congelado, independiente de los campos editados actualmente. <button type="button" className="text-accent underline" disabled={loading} onClick={() => void resolvePending()}>{loading ? "Consultando identidad…" : "Recuperar creación pendiente"}</button></div>}
    {(errors.catalogs || errors.deepDataset) && <p role="alert">{errors.catalogs || errors.deepDataset} <button className="text-accent underline" onClick={retryCatalogs}>Reintentar</button></p>}
    {alert && <p role="alert" tabIndex={-1}>{alert}</p>}
    <nav aria-label="Pasos del lote" className="flex flex-wrap gap-2">{["Historial y perfil", "Estrategias", "Condiciones", "Validación", "Simulación"].map((label, index) => <button key={label} type="button" className={`${control} ${index === currentStep ? "border-accent" : ""}`} aria-current={index === currentStep ? "step" : undefined} onClick={() => setStep(index)}>{label}</button>)}</nav>
    {currentStep === 0 && <section aria-labelledby="context-title" className="space-y-4"><h3 id="context-title" className="section-header">Referencia exacta de datos y perfil</h3>
      <label className="field"><span className="field-label">Dataset local</span><select className={control} value={draft.datasetSha256 === "0".repeat(64) ? "" : draft.datasetSha256} onChange={(e) => { const item = datasets?.items.find((candidate) => candidate.dataset_sha256 === e.target.value); if (item) chooseDataset(item); }}><option value="">Elegí un dataset de esta página</option>{datasets?.items.map((item) => <option key={item.dataset_sha256} value={item.dataset_sha256}>{item.source_id} · {item.records_total} sorteos · {item.dataset_sha256.slice(0, 12)}</option>)}</select></label>
      <p className="field-help">{selectedDataset ? `Fuente ${selectedDataset.source_id} (${selectedDataset.source_kind ?? "tipo no declarado"}), ${selectedDataset.records_total} filas; ${selectedDataset.first_draw}–${selectedDataset.last_draw}. La proyección no es prueba de archivo verificado.` : "Los datos guardados son referencias inertes hasta la admisión del servidor."}</p>
      <Pager label="datasets" page={datasets} offset={datasetOffset} setOffset={setDatasetOffset} />
      <label className="field"><span className="field-label">Perfil y revisión</span><select className={control} value={draft.profile ? `${draft.profile.id}@${draft.profile.revision}` : ""} onChange={(e) => { const p = profiles?.items.find((candidate) => `${candidate.profile.profile_id}@${candidate.profile.revision}` === e.target.value); if (p) chooseProfile(p); }}><option value="">Elegí un perfil registrado</option>{profiles?.items.map((p) => <option key={`${p.profile.profile_id}@${p.profile.revision}`} value={`${p.profile.profile_id}@${p.profile.revision}`}>{p.profile.profile_id} · rev {p.profile.revision} · {p.profile.currency}, escala {p.profile.scale}, universo {p.profile.universe_size}, posiciones {p.profile.positions}</option>)}</select></label>
      <Pager label="perfiles" page={profiles} offset={profileOffset} setOffset={setProfileOffset} />
      {selectedProfile && selectedDataset && <p className={selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "field-help" : "text-danger"}>{selectedDataset.profile_sha256 === selectedProfile.profile_sha256 && selectedDataset.profile_revision === selectedProfile.profile.revision ? "El dataset declara el mismo perfil y revisión." : "Perfil y dataset no coinciden; la validación del servidor también lo comprueba."}</p>}
    </section>}
    {currentStep === 1 && <section aria-labelledby="strategies-title" className="space-y-4"><h3 id="strategies-title" className="section-header">Estrategias guardadas · {selectedRefs.length}/3</h3>{selectedRefs.length > 0 && <ol aria-label="Orden del lote" className="list-decimal space-y-2 pl-5">{selectedRefs.map((reference, index) => <li key={`${reference.id}@${reference.revision}`}>{index + 1}. {reference.id} · revisión {reference.revision} · <code>{reference.definition_sha256.slice(0, 12)}</code> <button type="button" className="text-accent underline" onClick={() => mutate((current) => ({ ...current, strategyRefs: current.strategyRefs.filter((item) => item.id !== reference.id || item.revision !== reference.revision) }))}>Quitar</button></li>)}</ol>}<p className="field-help">Las referencias conservan su revisión y digest exactos. Recomendaciones de cierre se muestran, nunca sustituyen las condiciones comunes. Las tres estrategias de referencia son copias protegidas.</p>
      {!draft.profile && <p>Elegí primero perfil y dataset.</p>}
      {strategies?.items.map((strategy) => <article key={`${strategy.id}@${strategy.revision}`} className="space-y-2 border-b border-border py-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><h4 className="font-medium">{strategy.name} · revisión {strategy.revision}{strategy.protected ? " · referencia protegida" : ""}</h4><p className="field-help">{strategy.preset_explanation ?? `${strategy.definition.selector}; cobertura ${strategy.definition.coverage}; ${strategy.definition.staking}`}</p><p className="field-help">{strategy.execution_available ? "Proyección compatible; la admisión vuelve a validar fuente y estrategia." : strategy.execution_unavailable_reason ?? strategy.incompatibilities.join("; ")}</p></div><button type="button" className="btn btn-secondary" disabled={!draft.profile} aria-pressed={selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision)} onClick={() => void exactStrategy(strategy)}>{selectedRefs.some((ref) => ref.id === strategy.id && ref.revision === strategy.revision) ? "Quitar" : "Agregar en orden"}</button></div>
        <button type="button" className="text-accent underline" onClick={() => loadEditor(strategy, strategy.protected)}>{strategy.protected ? "Crear copia editable" : "Editar y guardar nueva revisión"}</button> <button type="button" className="text-accent underline" onClick={() => void loadStrategyRevisions(strategy)}>Ver revisiones exactas</button>{strategyRevisions[strategy.id] && <ul aria-label={`Revisiones de ${strategy.name}`} className="list-disc pl-5">{strategyRevisions[strategy.id].map((revision) => <li key={revision.revision}>Revisión {revision.revision} · <code>{revision.definition_sha256.slice(0, 12)}</code> · {revision.definition.name} <button type="button" className="text-accent underline" onClick={() => chooseExactRevision(revision)}>Agregar revisión exacta</button></li>)}</ul>}</article>)}
      <Pager label="estrategias" page={strategies} offset={strategyOffset} setOffset={setStrategyOffset} />
      {editorAvailable ? <form className="space-y-3 border-t border-border pt-4" onSubmit={(event) => void saveStrategy(event)}><h4 className="font-medium">Composición soportada</h4><p className="field-help">Editor cerrado: selección fija o azar reproducible con apuesta plana. No se acepta JSON, DSL ni código arbitrario. Para staking avanzado, elegí una definición guardada compatible.</p>
        <label className="field"><span className="field-label">Nombre</span><input className={control} value={definitionName} onChange={(e) => setDefinitionName(e.target.value)} maxLength={80} required /></label>
        <label className="field"><span className="field-label">Selector</span><select className={control} value={selector} onChange={(e) => setSelector(e.target.value as typeof selector)}><option value="static-numbers/v1">Números fijos</option><option value="seeded-random/hash-sha256-v1">Azar reproducible SHA-256</option></select></label>
        <label className="field"><span className="field-label">Cobertura</span><input className={control} inputMode="numeric" value={coverage} onChange={(e) => setCoverage(e.target.value)} /></label>
        {selector === "static-numbers/v1" ? <label className="field"><span className="field-label">Números distintos, separados por comas</span><input className={control} value={numbers} onChange={(e) => setNumbers(e.target.value)} /></label> : <label className="field"><span className="field-label">Semilla</span><input className={control} inputMode="numeric" value={seed} onChange={(e) => setSeed(e.target.value)} /></label>}
        <label className="field"><span className="field-label">Apuesta por número ({selectedProfile?.profile.currency ?? "moneda"})</span><input className={control} inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} /></label>
        <button className="btn btn-secondary" type="submit">{editTarget && !editTarget.protected ? "Guardar revisión nueva (CAS)" : "Guardar como estrategia nueva"}</button>
      </form> : <p className="field-help border-t border-border pt-4">Esta estrategia cerrada no se puede editar ni copiar fielmente con el editor disponible. No se cambiará su definición ni sus valores predeterminados.</p>}
    </section>}
    {currentStep === 2 && <section aria-labelledby="conditions-title" className="space-y-4"><h3 id="conditions-title" className="section-header">Condiciones comunes y presupuesto</h3>
      <p className="field-help">Importes expresados en {selectedProfile?.profile.currency ?? "la moneda del perfil"}; escala {selectedProfile?.profile.scale ?? "—"}. El cliente valida formato y escala; únicamente el servidor calcula admisión y resultados.</p>
      <div className="grid gap-4 sm:grid-cols-2">{([ ["capital", `Capital inicial (${selectedProfile?.profile.currency ?? "moneda"})`], ["goal", `Meta de saldo (${selectedProfile?.profile.currency ?? "moneda"})`], ["max_elapsed_draws", "Máximo sorteos transcurridos"], ["max_bet_draws", "Máximo sorteos apostados (opcional)"], ["max_draws", "Presupuesto operativo solicitado"] ] as const).map(([key, label]) => <label className="field" key={key}><span className="field-label">{label}</span><input className={control} inputMode="decimal" value={draft.conditions[key]} onChange={(e) => updateCondition(key, e.target.value)} /></label>)}
        <label className="field"><span className="field-label">Sorteo inicial canónico</span><select className={control} value={draft.conditions.start_draw} onChange={(e) => chooseStartDraw(e.target.value)}><option value="">Elegí explícitamente</option>{draft.selectedDraw?.datasetSha256 === draft.datasetSha256 && !draws?.items.includes(draft.selectedDraw.draw) && <option value={draft.selectedDraw.draw}>{draft.selectedDraw.draw} · referencia guardada; el servidor verificará el archivo</option>}{draws?.items.map((draw) => <option key={draw} value={draw}>{draw}</option>)}</select>{errors.draws && <span role="alert">{errors.draws} <button type="button" className="text-accent underline" onClick={() => void loadDraws()}>Reintentar sorteos</button></span>}</label>
        <label className="field"><span className="field-label">Liquidación común</span><select className={control} value={draft.conditions.settlement} onChange={(e) => updateCondition("settlement", e.target.value)}><option value="">Elegí regla</option>{selectedProfile?.profile_execution.settlements.map((settlement) => <option key={settlement} value={settlement}>{settlement === "all" ? "Sumar todas las posiciones" : "Mayor premio"}</option>)}</select></label></div>
      <Pager label="sorteos" page={draws} offset={drawOffset} setOffset={setDrawOffset} />
      {policy && <p className="field-help">Política operativa rev. {policy.revision}: {policy.explanation} Límite actual de estrategias {policy.policy.max_strategies_per_batch}; sorteos apostados {policy.policy.max_bet_draws}, transcurridos {policy.policy.max_elapsed_draws}; workers {policy.policy.worker_count}.</p>}
      {selectedRefs.map((ref, index) => { const item = strategies?.items.find((strategy) => strategy.id === ref.id && strategy.revision === ref.revision); const recommendation = item?.definition.closing_defaults; return <p key={`${ref.id}@${ref.revision}`} className="field-help">Estrategia {index + 1}: {item?.name ?? ref.id}. Recomendación de liquidación: {String(recommendation?.settlement ?? "ninguna")}; la condición compartida actual sigue siendo {draft.conditions.settlement || "sin elegir"}.</p>; })}
    </section>}
    {currentStep === 3 && <section aria-labelledby="validation-title" className="space-y-4"><h3 id="validation-title" className="section-header">Validación de solo lectura</h3><p>Esta comprobación no reserva espacio ni cupo. Cualquier cambio en contexto, estrategia o condición invalida su resultado.</p><button type="button" className="btn btn-primary" disabled={loading || !selectedProfile || !selectedDataset || selectedRefs.length < 1 || !policy} onClick={() => void validateBatch()}>Validar lote con el servidor</button>
      {currentValidation && <div role="status" className="space-y-2 border-y border-border py-3"><h4 className="font-medium">{currentValidation.valid ? "Validación aceptada" : "Validación rechazada"}</h4><p>Perfil {currentValidation.profile.id} rev. {currentValidation.profile.revision} · {selectedProfile?.profile.currency}, escala {selectedProfile?.profile.scale} · universo {selectedProfile?.profile.universe_size}, posiciones {selectedProfile?.profile.positions}</p><p>Dataset {String(currentValidation.dataset.dataset_sha256)} · fuente {selectedDataset?.source_id ?? String(currentValidation.dataset.source_sha256)} · {selectedDataset?.first_draw}–{selectedDataset?.last_draw} · inicio {draft.conditions.start_draw} · filas fuente {String(currentValidation.dataset.row_count)} · archivo autenticado: {String(currentValidation.dataset.archive_bound)}</p><p>Estrategias en orden: {draft.strategyRefs.map((ref) => `${ref.id}@${ref.revision}`).join(" → ")}</p><p>Solicitado: {JSON.stringify(currentValidation.requested_constraints)}</p><p>Efectivo tras política: {JSON.stringify(currentValidation.effective_constraints)}</p><p className="field-help">No se creó reserva. Los límites reflejan política del operador, no garantía de rendimiento.</p>{currentValidation.reasons.map((reason) => <p role="alert" key={reason}>{reason}</p>)}</div>}
    </section>}
    {currentStep === 4 && <section aria-labelledby="simulate-title" className="space-y-4"><h3 id="simulate-title" className="section-header">Simular lote</h3><p>Se enviará la misma composición y las mismas condiciones que se validaron. Cada estrategia usa la misma ventana y límites.</p>
      {currentValidation && <div role="status" className="space-y-2 border-y border-border py-3"><h4 className="font-medium">{currentValidation.valid ? "Validación aceptada" : "Validación rechazada"}</h4><p>Perfil {currentValidation.profile.id} rev. {currentValidation.profile.revision} · {selectedProfile?.profile.currency}, escala {selectedProfile?.profile.scale} · universo {selectedProfile?.profile.universe_size}, posiciones {selectedProfile?.profile.positions}</p><p>Dataset {String(currentValidation.dataset.dataset_sha256)} · fuente {selectedDataset?.source_id ?? String(currentValidation.dataset.source_sha256)} · {selectedDataset?.first_draw}–{selectedDataset?.last_draw} · inicio {draft.conditions.start_draw} · filas fuente {String(currentValidation.dataset.row_count)} · archivo autenticado: {String(currentValidation.dataset.archive_bound)}</p><p>Estrategias en orden: {draft.strategyRefs.map((ref) => `${ref.id}@${ref.revision}`).join(" → ")}</p><p>Solicitado: {JSON.stringify(currentValidation.requested_constraints)}</p><p>Efectivo tras política: {JSON.stringify(currentValidation.effective_constraints)}</p><p className="field-help">La validación no creó reserva. Los límites no son garantía de rendimiento.</p>{currentValidation.reasons.map((reason) => <p role="alert" key={reason}>{reason}</p>)}</div>}
      <button type="button" className="btn btn-primary" disabled={loading || !currentValidation?.valid || !draft.pending && !policy} onClick={() => void submit()}>{loading ? "Procesando…" : "Crear lote y simular"}</button><p className="field-help">La respuesta se identifica por un ID de experimento. Los detalles v5 corresponden al recorrido de visualización siguiente.</p></section>}
    <div className="flex justify-between border-t border-border pt-4"><button type="button" className="btn btn-secondary" disabled={currentStep === 0} onClick={() => setStep(currentStep - 1)}>Atrás</button><button type="button" className="btn btn-secondary" disabled={currentStep >= 4} onClick={() => setStep(currentStep + 1)}>Continuar</button></div>
    <p><Link className="text-accent underline" to="/experimentos/nuevo">Ir al creador clásico</Link> · <Link className="text-accent underline" to="/experimentos/nuevo/perfil">Creador de perfil v1–4</Link></p>
  </div>;
  return page;
}

function Pager({ label, page, offset, setOffset }: { label: string; page: Page<unknown> | null; offset: number; setOffset: (offset: number) => void }) {
  if (!page || page.total <= page.limit) return null;
  return <nav aria-label={`Páginas de ${label}`} className="flex items-center gap-3"><button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - page.limit))}>Anterior</button><span>{offset + 1}–{Math.min(offset + page.limit, page.total)} de {page.total}</span><button type="button" className="btn btn-secondary" disabled={offset + page.limit >= page.total} onClick={() => setOffset(offset + page.limit)}>Siguiente</button></nav>;
}
