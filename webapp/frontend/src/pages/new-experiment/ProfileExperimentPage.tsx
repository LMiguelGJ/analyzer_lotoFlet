import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import { FiveStepWizard, useFiveStepWizard } from "../../components/FiveStepWizard";
import { WizardScopeSelector } from "../../components/WizardScopeSelector";
import { GameRulesSummary } from "../../components/GameRulesSummary";
import { profileRulesView, profileSettlementLabel } from "../../lib/game-rules";
import type { DatasetListing, Page, ProfileExperimentRequest, ProfileListing, ProfileCyclingRequest, ProfileAudazRequest, ProfileRecoveryRequest } from "../../api/types";
import { buildProfileRequest, initialProfileDraft, matchingDataset, validateProfileCapital, validateProfileStrategy } from "./profile-model";
import type { ProfileDraft, ProfilePolicy } from "./profile-model";
import { buildSavedProfileRepeatRequest, draftFromSavedProfileRequest } from "./profile-repeat-model";

const control = "control";
const secondary = "btn btn-secondary";
const pageSize = 20;

type Choice<T> = { item: T; offset: number };

export function ProfileExperimentPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const requestedDataset = new URLSearchParams(location.search).get("dataset_sha256");
  const baseId = new URLSearchParams(location.search).get("base");
  const repeatGeneration = useRef(0);
  const activeBaseId = useRef<string | null>(null);
  const [repeatState, setRepeatState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [repeatError, setRepeatError] = useState("");
  const [originalRequest, setOriginalRequest] = useState<ProfileExperimentRequest | ProfileCyclingRequest | ProfileAudazRequest | ProfileRecoveryRequest | null>(null);
  const requestedDatasetHash = requestedDataset && /^[0-9a-f]{64}$/.test(requestedDataset) ? requestedDataset : null;
  const [profiles, setProfiles] = useState<Page<ProfileListing> | null>(null);
  const [datasets, setDatasets] = useState<Page<DatasetListing> | null>(null);
  const [profileOffset, setProfileOffset] = useState(0);
  const [datasetOffset, setDatasetOffset] = useState(0);
  const [profileRetry, setProfileRetry] = useState(0);
  const [datasetRetry, setDatasetRetry] = useState(0);
  const [profileError, setProfileError] = useState("");
  const [datasetError, setDatasetError] = useState("");
  const [profileChoice, setProfileChoice] = useState<Choice<ProfileListing> | null>(null);
  const [datasetChoice, setDatasetChoice] = useState<Choice<DatasetListing> | null>(null);
  const [draws, setDraws] = useState<Page<string> | null>(null);
  const [drawOffset, setDrawOffset] = useState(0);
  const [drawDate, setDrawDate] = useState("");
  const [drawRetry, setDrawRetry] = useState(0);
  const [drawError, setDrawError] = useState("");
  const [draft, setDraft] = useState<ProfileDraft>(initialProfileDraft);
  const [policy, setPolicy] = useState<ProfilePolicy>("fixed");
  const [error, setError] = useState("");
  const [posting, setPosting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const inFlight = useRef(false);
  const wizard = useFiveStepWizard(5, validateWizardStep);
  const alertRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => { if (error) alertRef.current?.focus(); }, [error]);
  useEffect(() => {
    const generation = ++repeatGeneration.current;
    if (activeBaseId.current !== baseId) {
      activeBaseId.current = baseId;
      setOriginalRequest(null); setProfileChoice(null); setDatasetChoice(null); setDraws(null);
      setDraft(initialProfileDraft); setPolicy("fixed"); setError(""); setUncertain(false);
      setProfileOffset(0); setDatasetOffset(0); setDrawOffset(0); setDrawDate("");
    }
    setRepeatError(""); setRepeatState(baseId ? "loading" : "idle");
    if (!baseId) return;
    let live = true;
    const current = () => live && generation === repeatGeneration.current;
    async function loadRepeat() {
      try {
        const saved = await apiClient.getExperiment(baseId!);
        if (!current()) return;
        if (saved.request_kind !== "profile" || ![1, 2, 3, 4].includes(saved.request.schema_version)) throw new Error("Solo se pueden repetir solicitudes de perfil v1–v4.");
        const request = saved.request as ProfileExperimentRequest | ProfileCyclingRequest | ProfileAudazRequest | ProfileRecoveryRequest;
        let profile: ProfileListing | undefined;
        let offset = 0;
        while (offset < 1_000_000) {
          const page = await apiClient.getProfiles(offset, pageSize);
          if (!current()) return;
          profile = page.items.find((item) => item.profile.profile_id === request.profile_id && item.profile.revision === request.profile_revision && item.profile_sha256 === request.profile_sha256);
          if (profile) break;
          offset += page.limit || pageSize;
          if (!page.items.length || offset >= page.total) break;
        }
        if (!profile) throw new Error("No se encontró la revisión inmutable del perfil guardado; no se sustituyó por otra revisión.");
        const dataset = await apiClient.getDataset(request.dataset_sha256);
        if (!current()) return;
        if (dataset.dataset_sha256 !== request.dataset_sha256 || dataset.profile_id !== request.profile_id || dataset.profile_revision !== request.profile_revision || dataset.profile_sha256 !== request.profile_sha256) throw new Error("El historial inmutable guardado no coincide con el perfil original.");
        const draft = draftFromSavedProfileRequest(request, profile, dataset);
        const date = draft.start_draw.slice(0, 10);
        let drawOffsetFound = -1;
        if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
          let drawOffset = 0;
          while (true) {
            const page = await apiClient.getDatasetDraws(dataset.dataset_sha256, drawOffset, 100, date);
            if (!current()) return;
            const index = page.items.indexOf(draft.start_draw);
            if (index >= 0) { drawOffsetFound = drawOffset; break; }
            drawOffset += page.items.length;
            if (!page.items.length || drawOffset >= page.total) break;
          }
        }
        if (drawOffsetFound < 0) throw new Error("El sorteo original no existe en el historial inmutable; no se puede repetir.");
        setProfileOffset(Math.floor(offset / pageSize) * pageSize);
        setDatasetOffset(0); setDrawOffset(drawOffsetFound); setDrawDate(date);
        setProfileChoice({ item: profile, offset: Math.floor(offset / pageSize) * pageSize });
        setDatasetChoice({ item: dataset, offset: 0 }); setDraft(draft);
        setPolicy(request.schema_version === 2 ? "cycling" : request.schema_version === 3 ? "audaz" : request.schema_version === 4 ? "recovery" : "fixed");
        setOriginalRequest(structuredClone(request)); setRepeatState("ready");
      } catch (cause) {
        if (!current()) return;
        setRepeatError(cause instanceof ApiError && cause.status === 404 ? "No se encontró el experimento o su historial inmutable." : cause instanceof ApiError && cause.status === 409 ? "El historial guardado no pasó la verificación de integridad." : cause instanceof NetworkError ? "No se pudo verificar la solicitud guardada. Reintentá." : cause instanceof Error ? cause.message : "No se pudo cargar la plantilla guardada.");
        setRepeatState("error");
      }
    }
    void loadRepeat();
    return () => { live = false; };
  }, [baseId, profileRetry, datasetRetry]);
  useEffect(() => {
    let live = true;
    setProfiles(null); setProfileError("");
    apiClient.getProfiles(profileOffset, pageSize).then((page) => {
      if (!live) return;
      setProfiles(page);
      if (profileChoice?.offset === profileOffset && !page.items.some((item) => item.profile_sha256 === profileChoice.item.profile_sha256 &&
        item.profile.profile_id === profileChoice.item.profile.profile_id && item.profile.revision === profileChoice.item.profile.revision)) {
        setProfileChoice(null); setDatasetChoice(null); setDraws(null); setDraft((current) => ({ ...current, start_draw: "" }));
      }
    }).catch(() => { if (live) setProfileError("No se pudieron cargar los perfiles. Reintentá."); });
    return () => { live = false; };
  // Selection identity is checked again on submit; paging does not reset the selection.
  }, [profileOffset, profileRetry]);
  useEffect(() => {
    let live = true;
    setDatasets(null); setDatasetError("");
    apiClient.getDatasets(datasetOffset, pageSize).then((page) => {
      if (!live) return;
      setDatasets(page);
      if (datasetChoice?.offset === datasetOffset && !page.items.some((item) => item.dataset_sha256 === datasetChoice.item.dataset_sha256 &&
        item.profile_sha256 === datasetChoice.item.profile_sha256)) {
        setDatasetChoice(null); setDraws(null); setDraft((current) => ({ ...current, start_draw: "" }));
      }
    }).catch(() => { if (live) setDatasetError("No se pudieron cargar los datos. Reintentá."); });
    return () => { live = false; };
  }, [datasetOffset, datasetRetry]);
  useEffect(() => {
    if (!datasetChoice) { setDraws(null); return; }
    let live = true;
    setDraws(null); setDrawError("");
    apiClient.getDatasetDraws(datasetChoice.item.dataset_sha256, drawOffset, 100, drawDate || undefined)
      .then((page) => { if (live) setDraws(page); })
      .catch(() => { if (live) setDrawError("No se pudieron cargar los sorteos. Reintentá."); });
    return () => { live = false; };
  }, [datasetChoice, drawOffset, drawDate, drawRetry]);

  function edit(key: keyof ProfileDraft, value: string) {
    setDraft((current) => ({ ...current, [key]: value })); setError("");
  }
  function chooseProfile(item: ProfileListing) {
    setProfileChoice({ item, offset: profileOffset }); setDatasetChoice(null); setDraws(null);
    setDraft((current) => ({ ...current, start_draw: "" })); setPolicy("fixed"); setError("");
  }
  function chooseDataset(item: DatasetListing) {
    if (!profileChoice || !matchingDataset(profileChoice.item, item)) return;
    setDatasetChoice({ item, offset: datasetOffset }); setDrawOffset(0); setDrawDate("");
    setDraft((current) => ({ ...current, start_draw: "" })); setError("");
  }
  function validateWizardStep(step: number): boolean {
    try {
      if (!profileChoice || profileError) throw new Error("Elegí explícitamente un perfil disponible para continuar.");
      if (step === 0) validateProfileStrategy(draft, profileChoice.item, policy);
      if (step === 1 && !profileChoice.item.profile_execution.settlements.includes(draft.settlement as "all" | "best")) {
        throw new Error("Elegí una regla de liquidación disponible para el perfil.");
      }
      if (step === 2 && (!datasetChoice || !matchingDataset(profileChoice.item, datasetChoice.item) ||
          !draws?.items.includes(draft.start_draw) || datasetError || drawError)) {
        throw new Error("Elegí datos compatibles y un sorteo inicial verificado.");
      }
      if (step === 3) validateProfileCapital(draft, profileChoice.item, Boolean(originalRequest));
      setError(""); return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Revisá los parámetros de este paso."); return false;
    }
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (wizard.step !== 4 || inFlight.current || uncertain || !profileChoice || !datasetChoice || !draws ||
        profileError || datasetError || drawError || baseId && (repeatState !== "ready" || !originalRequest)) return;
    let body;
    try {
      const verifiedDraw = draws.items.includes(draft.start_draw) ? draft.start_draw : "";
      body = originalRequest
        ? buildSavedProfileRepeatRequest(draft, originalRequest, profileChoice.item, datasetChoice.item, verifiedDraw)
        : buildProfileRequest(draft, profileChoice.item, datasetChoice.item, verifiedDraw, policy);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Revisá los parámetros."); return; }
    inFlight.current = true; setPosting(true); setError("");
    let submitted = false;
    try {
      // Recheck both server bindings and the draw at admission time. A catalog page
      // is only a discovery snapshot; stale choices cannot silently become another run.
      const [currentProfiles, currentDataset, currentDraws] = await Promise.all([
        apiClient.getProfiles(profileChoice.offset, pageSize),
        apiClient.getDataset(datasetChoice.item.dataset_sha256),
        apiClient.getDatasetDraws(datasetChoice.item.dataset_sha256, 0, 100, draft.start_draw.slice(0, 10)),
      ]);
      const fresh = currentProfiles.items.find((item) => item.profile.profile_id === body.profile_id &&
        item.profile.revision === body.profile_revision && item.profile_sha256 === body.profile_sha256);
      let found = currentDraws.items.includes(body.conditions.start_draw);
      let offset = currentDraws.items.length;
      while (!found && offset < currentDraws.total && currentDraws.items.length > 0) {
        const next = await apiClient.getDatasetDraws(body.dataset_sha256, offset, 100, draft.start_draw.slice(0, 10));
        found = next.items.includes(body.conditions.start_draw);
        if (!next.items.length) break;
        offset += next.items.length;
      }
      const requiredStaking = policy === "cycling" ? "q80-first-prize-cycling/v1" : policy === "audaz" ? "profile-audaz/v1" : policy === "recovery" ? "profile-recovery-ladder/v1" : "flat-per-number/v1";
      if (!fresh || !fresh.profile_execution.staking_capabilities.includes(requiredStaking) ||
          !fresh.profile_execution.selector_capabilities.includes(body.selector.capability) ||
          !fresh.profile_execution.settlements.includes(body.conditions.settlement) ||
          !fresh.profile_execution.entry_policies.includes(body.entry_policy) ||
          policy === "audaz" && (!fresh.profile_execution.audaz_compatibility?.available ||
            body.selector.coverage > fresh.profile_execution.audaz_compatibility.maximum_compatible_coverage) ||
          policy === "recovery" && (!fresh.profile_execution.recovery_compatibility?.available ||
            body.selector.coverage > fresh.profile_execution.recovery_compatibility.maximum_compatible_coverage) ||
          !matchingDataset(fresh, currentDataset) || currentDataset.dataset_sha256 !== body.dataset_sha256 ||
          !found || !matchingDataset(profileChoice.item, currentDataset)) {
        setError("El perfil, los datos o el sorteo cambiaron. Elegí de nuevo; no se envió nada.");
        return;
      }
      submitted = true;
      const created = await apiClient.createProfileExperiment(body);
      if (!created || typeof created.id !== "string" || !/^[a-f0-9]{32}$/.test(created.id)) {
        setUncertain(true);
        setError("No se pudo confirmar la simulación. Revisá Simulaciones antes de crear otra.");
        return;
      }
      navigate(`/simulaciones/${encodeURIComponent(created.id)}`, { replace: true });
    } catch (cause) {
      if (submitted && (cause instanceof NetworkError || cause instanceof ApiError && cause.status >= 200 && cause.status < 300)) {
        // No safe idempotency key exists for this POST: never automatically retry.
        setUncertain(true);
        setError("Sin confirmación de la simulación. Puede estar en la cola; revisá Simulaciones antes de crear otra.");
      } else if (!submitted && cause instanceof NetworkError) {
        setError("No se pudo verificar el perfil o los datos. No se envió la simulación; reintentá más tarde.");
      } else if (cause instanceof ApiError && cause.status === 409) {
        setError("El perfil, los datos o la apuesta no fueron aceptados, o la cola no está disponible. Revisá los importes y reintentá.");
      } else if (cause instanceof ApiError && cause.status === 507) {
        setError("No hay espacio disponible. Liberá almacenamiento y reintentá.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setError("El servidor rechazó la simulación. Revisá los campos.");
      } else {
        if (submitted) setUncertain(true);
        setError(submitted ? "No se pudo confirmar la creación. Revisá Simulaciones antes de crear otra." :
          "No se pudieron verificar las opciones. No se envió la simulación; reintentá.");
      }
    } finally { inFlight.current = false; setPosting(false); }
  }

  const profile = profileChoice?.item.profile;
  const compatible = datasets?.items.filter((item) => profileChoice && matchingDataset(profileChoice.item, item)) ?? [];
  const disabled = posting || uncertain || !profiles || !datasets || !draws || !!profileError || !!datasetError || !!drawError || !!baseId && (repeatState !== "ready" || !originalRequest);
  const policyControls = <details open><summary className="disclosure-summary">Política y parámetros de apuesta</summary>
    <div className="grid gap-x-5 sm:grid-cols-2 pt-3">
      <div className="field"><label htmlFor="staking-policy" className="field-label">Política de apuesta</label><select id="staking-policy" className={control} disabled={!!originalRequest || !profileChoice} value={policy} onChange={(event) => { setPolicy(event.target.value as ProfilePolicy); setError(""); }}><option value="fixed">Apuesta fija por número</option>{profileChoice?.item.profile_execution.staking_capabilities.includes("q80-first-prize-cycling/v1") && <option value="cycling">Escalera cíclica de 10 rondas</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-audaz/v1") && profileChoice.item.profile_execution.audaz_compatibility?.available && <option value="audaz">Audaz · apuesta dinámica por objetivo</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-recovery-ladder/v1") && profileChoice.item.profile_execution.recovery_compatibility?.available && <option value="recovery">Escalera de recuperación</option>}</select></div>
      {originalRequest && <p className="field-help">Se conserva la política y versión de apuesta originales ({originalRequest.schema_version}); no se convierte a otra modalidad.</p>}
      {policy === "fixed" && <Field label={`Apuesta fija por número (${profile?.currency ?? "moneda"})`} id="stake" value={draft.per_number_stake} onChange={(value) => edit("per_number_stake", value)} numeric />}
      {policy === "audaz" && profileChoice && <p className="field-help">Audaz disponible hasta cobertura {profileChoice.item.profile_execution.audaz_compatibility?.maximum_compatible_coverage ?? "no disponible"}.</p>}
      {policy === "recovery" && <><Field label={`Margen objetivo (${profile?.currency ?? "moneda"})`} id="target-margin" value={draft.target_margin} onChange={(value) => edit("target_margin", value)} numeric /><Field label="Rondas de recuperación (1–10.000)" id="recovery-rounds" value={draft.rounds} onChange={(value) => edit("rounds", value)} numeric /><div className="field"><label htmlFor="recovery-end-mode" className="field-label">Al completar las rondas</label><select id="recovery-end-mode" className={control} value={draft.end_mode} onChange={(event) => edit("end_mode", event.target.value)}><option value="">Elegí un comportamiento</option><option value="cycle">Reiniciar la escalera</option><option value="stop">Detener la simulación</option></select></div>{profileChoice && <p className="field-help">Cobertura máxima compatible: {profileChoice.item.profile_execution.recovery_compatibility?.maximum_compatible_coverage ?? "no disponible"}.</p>}</>}
    </div>
    <p className="field-help">{policy === "cycling" ? "La apuesta es dinámica: no hay importe fijo. Reinicia al acertar el primer premio." : policy === "audaz" ? "La apuesta es dinámica: no hay importe fijo." : policy === "recovery" ? "Al agotar las rondas, se reinicia o se detiene según lo elegido." : "El servidor valida el costo inicial al crear la simulación."} Se detiene al primer tope alcanzado.</p>
  </details>;
  return <div className="max-w-prose space-y-7">
    <div><h2 className="text-2xl">Simulación con perfil</h2>
      {requestedDatasetHash && <div role="status" className="field-help"><p>Historial elegido desde la biblioteca. Elegí el perfil y los datos que coincidan.</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all"><code>{requestedDatasetHash}</code></p></details></div>}
      {baseId && repeatState === "loading" && <p role="status">Cargando y verificando la solicitud guardada…</p>}
      {baseId && repeatState === "error" && <p role="alert">{repeatError} <button type="button" className="btn btn-tertiary" onClick={() => setProfileRetry((n) => n + 1)}>Reintentar carga guardada</button></p>}
      {requestedDataset && !requestedDatasetHash && <p role="alert">El enlace del historial no es válido. Elegí los datos manualmente.</p>}</div>
    <form onSubmit={(event) => { void submit(event); }} noValidate className="space-y-8">
      <FiveStepWizard steps={[
        { title: "1 · Estrategia", description: "Elegí el perfil antes de definir selección y política de apuesta." },
        { title: "2 · Reglas", description: "Revisá premios y liquidación compatibles con el perfil." },
        { title: "3 · Alcance", description: "Elegí el historial compatible y el sorteo inicial." },
        { title: "4 · Capital y datos", description: "Definí nombre, capital, meta y límites." },
        { title: "5 · Revisá y creá", description: "Confirmá la solicitud antes de enviarla." },
      ]} activeStep={wizard.step} onNext={wizard.next} onBack={wizard.back} busy={posting || uncertain || repeatState === "loading" || inFlight.current}>
      {error && <p ref={alertRef} tabIndex={-1} role="alert" className="border-y border-border py-3 text-red-300">{error}</p>}
      {wizard.step === 0 && <section aria-labelledby="profile-prerequisite-title" className="space-y-4"><h3 id="profile-prerequisite-title" className="section-header">Perfil de juego requerido</h3>
        {!profiles && !profileError && <p role="status">Cargando perfiles…</p>}{profileError && <p role="alert">{profileError} <button type="button" className="btn btn-tertiary" onClick={() => setProfileRetry((n) => n + 1)}>Reintentar perfiles</button></p>}
        {profiles && <><div className="field"><label htmlFor="profile-choice-prerequisite" className="field-label">Perfil de juego</label><select id="profile-choice-prerequisite" className={control} value={profileChoice && profileChoice.offset === profileOffset ? `${profileChoice.item.profile.profile_id}@${profileChoice.item.profile.revision}` : ""} onChange={(event) => { const item = profiles.items.find((entry) => `${entry.profile.profile_id}@${entry.profile.revision}` === event.target.value); if (item) chooseProfile(item); }}><option value="">Elegí un perfil</option>{profiles.items.map((item, index) => <option key={`${item.profile.profile_id}@${item.profile.revision}`} value={`${item.profile.profile_id}@${item.profile.revision}`} disabled={!item.profile_execution.ready}>Perfil de juego {index + 1}{!item.profile_execution.ready ? " (no disponible)" : ""}</option>)}</select></div><Pager label="perfiles" offset={profileOffset} total={profiles.total} step={pageSize} onChange={setProfileOffset} /></>}
        {profileChoice && <p className="field-help">Perfil seleccionado explícitamente · {profile?.currency} · {profile?.positions} posiciones · {profile?.universe_size} números posibles.</p>}
        <section aria-labelledby="selection-title" className="space-y-4"><h3 id="selection-title" className="section-header">Selección para la simulación</h3><details open><summary className="disclosure-summary">Ajustes avanzados</summary><div className="grid gap-x-5 sm:grid-cols-2"><div className="field"><label htmlFor="selector" className="field-label">Selección</label><select id="selector" className={control} disabled={!profileChoice} value={draft.selector} onChange={(event) => edit("selector", event.target.value)}><option value="static">Números fijos</option><option value="random" disabled={!!profileChoice && !profileChoice.item.profile_execution.selector_capabilities.includes("seeded-random/hash-sha256-v1")}>Azar reproducible</option></select></div><Field label="Cobertura (números por sorteo)" id="coverage" value={draft.coverage} onChange={(value) => edit("coverage", value)} numeric />{draft.selector === "static" ? <Field label="Números distintos, separados por comas" id="numbers" value={draft.numbers} onChange={(value) => edit("numbers", value)} /> : <Field label="Semilla de azar (entero no negativo)" id="seed" value={draft.seed} onChange={(value) => edit("seed", value)} numeric />}</div></details>{policyControls}</section>
      </section>}
      {wizard.step === 1 && <section aria-labelledby="rules-title" className="space-y-4"><h3 id="rules-title" className="section-header">Resumen del perfil de juego</h3>
        {profileChoice ? <GameRulesSummary view={profileRulesView(profileChoice.item, "Catálogo de perfiles /catalog/profiles · revisión seleccionada para esta simulación", draft.settlement || undefined)} /> : <p className="field-help">Elegí un perfil de juego para ver sus reglas.</p>}
        <div className="field"><label htmlFor="settlement" className="field-label">Cómo contar los premios</label><select id="settlement" className={control} disabled={!profileChoice} value={draft.settlement} onChange={(event) => edit("settlement", event.target.value)}><option value="">Elegí una regla</option>{profileChoice?.item.profile_execution.settlements.filter((mode) => mode === "all" || mode === "best").map((mode) => <option key={mode} value={mode}>{profileSettlementLabel(profileChoice.item.profile, mode)}</option>)}</select></div>
      </section>}
      {wizard.step === 2 && <section aria-labelledby="history-title" className="space-y-6"><h3 id="history-title" className="section-header">Datos del historial</h3>
      <section aria-labelledby="profile-choice-title"><h4 id="profile-choice-title" className="font-medium">Perfil seleccionado</h4>
        {!profiles && !profileError && <p role="status">Cargando perfiles…</p>}
        {profileError && <p role="alert">{profileError} <button type="button" className="btn btn-tertiary" onClick={() => setProfileRetry((n) => n + 1)}>Reintentar perfiles</button></p>}
        {profiles && <><div className="field"><label htmlFor="profile-choice" className="field-label">Perfil de juego</label><select id="profile-choice" className={control} value={profileChoice && profileChoice.offset === profileOffset ? `${profileChoice.item.profile.profile_id}@${profileChoice.item.profile.revision}` : ""} onChange={(event) => { const item = profiles.items.find((entry) => `${entry.profile.profile_id}@${entry.profile.revision}` === event.target.value); if (item) chooseProfile(item); }}><option value="">Elegí un perfil</option>{profiles.items.map((item, index) => <option key={`${item.profile.profile_id}@${item.profile.revision}`} value={`${item.profile.profile_id}@${item.profile.revision}`} disabled={!item.profile_execution.ready}>Perfil de juego {index + 1}{!item.profile_execution.ready ? " (no disponible)" : ""}</option>)}</select></div>
          {profiles.total === 0 && <p>No hay perfiles. <Link to="/datos" className="btn btn-tertiary">Creá uno en Datos</Link>.</p>}
          <Pager label="perfiles" offset={profileOffset} total={profiles.total} step={pageSize} onChange={setProfileOffset} /></>}
        {profile && <><p role="status" className="field-help">{profile.currency} · {profile.positions} posiciones · {profile.universe_size} números posibles.</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><dl className="data-list break-all pt-2"><dt>Identidad y revisión</dt><dd>{profile.profile_id} · {profile.revision}</dd><dt>Versión del esquema</dt><dd>{profile.schema_version}</dd><dt>Huella del perfil</dt><dd className="font-mono">{profileChoice?.item.profile_sha256}</dd></dl></details></>}
      </section>
      <section aria-labelledby="dataset-choice-title"><h4 id="dataset-choice-title" className="font-medium">Datos</h4>
        {!datasets && !datasetError && <p role="status">Cargando datos…</p>}
        {datasetError && <p role="alert">{datasetError} <button type="button" className="btn btn-tertiary" onClick={() => setDatasetRetry((n) => n + 1)}>Reintentar datos</button></p>}
        {datasets && <><div className="field"><label htmlFor="dataset-choice" className="field-label">Historial compatible</label><select id="dataset-choice" className={control} disabled={!profileChoice} value={datasetChoice?.offset === datasetOffset ? datasetChoice.item.dataset_sha256 : ""} onChange={(event) => { const item = datasets.items.find((entry) => entry.dataset_sha256 === event.target.value); if (item) chooseDataset(item); }}><option value="">Elegí datos</option>{compatible.map((item, index) => <option key={item.dataset_sha256} value={item.dataset_sha256}>Historial {index + 1} · {item.records_total} sorteos</option>)}</select></div>
          {profileChoice && !compatible.length && <p className="field-help">No hay datos compatibles en esta página. Probá otra o <Link to="/datos" className="btn btn-tertiary">importá un historial en Datos</Link>.</p>}
          <Pager label="datos" offset={datasetOffset} total={datasets.total} step={pageSize} onChange={setDatasetOffset} /></>}
      {datasetChoice && <details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><dl className="data-list break-all pt-2"><dt>Identidad del historial</dt><dd>{datasetChoice.item.source_id} · {datasetChoice.item.source_revision}</dd>{datasetChoice.item.first_draw && datasetChoice.item.last_draw && <><dt>Rango de fechas</dt><dd>{datasetChoice.item.first_draw} – {datasetChoice.item.last_draw}</dd></>}<dt>Huella del historial</dt><dd className="font-mono">{datasetChoice.item.dataset_sha256}</dd></dl></details>}
      </section>
      {datasetChoice && <section aria-labelledby="draw-choice-title"><h4 id="draw-choice-title" className="font-medium">Inicio de la simulación</h4>
        <div className="field"><label htmlFor="profile-draw-date" className="field-label">Filtrar sorteos por fecha</label><input id="profile-draw-date" type="date" className={control} value={drawDate} onChange={(event) => { setDrawDate(event.target.value); setDrawOffset(0); edit("start_draw", ""); }} /></div>
        {!draws && !drawError && <p role="status">Cargando sorteos…</p>}
        {drawError && <p role="alert">{drawError} <button type="button" className="btn btn-tertiary" onClick={() => setDrawRetry((n) => n + 1)}>Reintentar sorteos</button></p>}
        {draws && <><div className="field"><label htmlFor="profile-start-draw" className="field-label">Sorteo inicial</label><select id="profile-start-draw" className={control} value={draws.items.includes(draft.start_draw) ? draft.start_draw : ""} onChange={(event) => edit("start_draw", event.target.value)}><option value="">Elegí un sorteo</option>{draws.items.map((draw) => <option value={draw} key={draw}>{draw}</option>)}</select></div>
          {draws.total === 0 && <p>No hay sorteos para esta fecha.</p>}
          <Pager label="sorteos" offset={drawOffset} total={draws.total} step={100} onChange={(offset) => { setDrawOffset(offset); edit("start_draw", ""); }} /></>}
      </section>}
      <WizardScopeSelector currentMode="profile" busy={posting || uncertain || repeatState === "loading" || inFlight.current} />
      </section>}

      {wizard.step === 3 && <section aria-labelledby="profile-conditions-title" className="space-y-4"><h3 id="profile-conditions-title" className="section-header">Condiciones de la simulación</h3>
        <div className="grid gap-x-5 sm:grid-cols-2">
          <Field label="Nombre de la simulación" id="name" value={draft.name} onChange={(value) => edit("name", value)} />
          <Field label={`Capital inicial (${profile?.currency ?? "moneda"})`} id="capital" value={draft.capital} onChange={(value) => edit("capital", value)} numeric />
          <Field label={`Meta de saldo final (${profile?.currency ?? "moneda"})`} id="goal" value={draft.goal} onChange={(value) => edit("goal", value)} numeric />
          <Field label="Límite de sorteos transcurridos (1–10.000)" id="elapsed" value={draft.max_elapsed_draws} onChange={(value) => edit("max_elapsed_draws", value)} numeric />
          <details><summary className="disclosure-summary">Ajustes avanzados</summary><Field label="Límite de sorteos apostados (opcional)" id="bet-draws" value={draft.max_bet_draws} onChange={(value) => edit("max_bet_draws", value)} numeric /></details>
        </div>
      </section>}
      {wizard.step === 4 && <section aria-labelledby="profile-review-title" className="space-y-4"><h3 id="profile-review-title" className="section-header">Revisá la solicitud</h3><dl className="data-list"><dt>Perfil y revisión</dt><dd>{profileChoice?.item.profile.profile_id} · {profileChoice?.item.profile.revision}</dd><dt>Historial</dt><dd>{datasetChoice?.item.dataset_sha256}</dd><dt>Sorteo inicial</dt><dd>{draft.start_draw}</dd><dt>Selección</dt><dd>{draft.selector} · cobertura {draft.coverage}</dd><dt>Política</dt><dd>{policy}</dd><dt>Nombre y capital</dt><dd>{draft.name} · {draft.capital} → {draft.goal}</dd></dl>
        {uncertain && <p role="status">Envío bloqueado para evitar duplicados. <Link className="btn btn-tertiary" to="/simulaciones">Revisá Simulaciones</Link>.</p>}
        <button type="submit" className="btn btn-primary" disabled={disabled}>{posting ? "Creando simulación…" : "Crear simulación y agregar a la cola"}</button>
      </section>}
      </FiveStepWizard>
    </form>
  </div>;
}

function Field({ label, id, value, onChange, numeric = false }: { label: string; id: string; value: string; onChange: (value: string) => void; numeric?: boolean }) {
  return <div className="field"><label htmlFor={id} className="field-label">{label}</label><input id={id} className={control} inputMode={numeric ? "decimal" : "text"} value={value} onChange={(event) => onChange(event.target.value)} /></div>;
}

function Pager({ label, offset, total, step, onChange }: { label: string; offset: number; total: number; step: number; onChange: (offset: number) => void }) {
  if (total <= step) return null;
  return <nav aria-label={`Páginas de ${label}`} className="mt-3 flex items-center gap-3"><button type="button" className={secondary} disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - step))}>Anterior</button><span>{Math.floor(offset / step) + 1} · {total}</span><button type="button" className={secondary} disabled={offset + step >= total} onClick={() => onChange(offset + step)}>Siguiente</button></nav>;
}
