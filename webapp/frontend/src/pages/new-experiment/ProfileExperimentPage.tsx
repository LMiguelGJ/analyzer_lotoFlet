import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { DatasetListing, Page, ProfileListing } from "../../api/types";
import { buildProfileRequest, initialProfileDraft, matchingDataset } from "./profile-model";
import type { ProfileDraft, ProfilePolicy } from "./profile-model";

const control = "control";
const secondary = "btn btn-secondary";
const pageSize = 20;

type Choice<T> = { item: T; offset: number };

export function ProfileExperimentPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const requestedDataset = new URLSearchParams(location.search).get("dataset_sha256");
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
  const alertRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => { if (error) alertRef.current?.focus(); }, [error]);
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
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || uncertain || !profileChoice || !datasetChoice || !draws ||
        profileError || datasetError || drawError) return;
    let body;
    try {
      body = buildProfileRequest(draft, profileChoice.item, datasetChoice.item,
        draws.items.includes(draft.start_draw) ? draft.start_draw : "", policy);
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
      navigate(`/experimentos/${encodeURIComponent(created.id)}`, { replace: true });
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
  const disabled = posting || uncertain || !profiles || !datasets || !draws || !!profileError || !!datasetError || !!drawError;
  return <div className="max-w-prose space-y-7">
    <div><h2 className="text-2xl">Simulación con perfil</h2><div className="mt-2 flex flex-wrap gap-2"><Link to="/experimentos/nuevo/sesion" className="btn btn-tertiary">Lote de simulaciones</Link><Link to="/experimentos/nuevo" className="btn btn-tertiary">Volver al creador clásico</Link></div>
      {requestedDatasetHash && <div role="status" className="field-help"><p>Historial elegido desde la biblioteca. Elegí el perfil y los datos que coincidan.</p><details><summary className="disclosure-summary text-sm">Detalles técnicos</summary><p className="break-all"><code>{requestedDatasetHash}</code></p></details></div>}
      {requestedDataset && !requestedDatasetHash && <p role="alert">El enlace del historial no es válido. Elegí los datos manualmente.</p>}</div>
    <form onSubmit={(event) => { void submit(event); }} noValidate className="space-y-8">
      <section aria-labelledby="rules-title" className="space-y-4"><h3 id="rules-title" className="section-header">Resumen del perfil de juego</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          <div><h4 className="font-medium">Reglas del sorteo</h4><p className="field-help">{profile ? `${profile.positions} posiciones · ${profile.allows_repeats ? "admite números repetidos" : "sin números repetidos"}` : "Elegí un perfil de juego para ver sus reglas."}</p><p className="field-help">Premios: {profile ? profile.multipliers.map((item) => `${item.numerator}/${item.denominator}`).join(" · ") : "—"}</p></div>
          <div><h4 className="font-medium">Selección</h4><p className="field-help">{profile ? `${profile.universe_size} números posibles · hasta ${profile.max_coverage} por sorteo` : "Se muestra al elegir el perfil."}</p></div>
          <div><h4 className="font-medium">Límites</h4><p className="field-help">{profile ? `${profile.currency} · apuesta de ${profile.minimum_stake} a ${profile.maximum_stake} · incremento ${profile.stake_increment}` : "Se muestra al elegir el perfil."}</p></div>
        </div>
        <details><summary className="disclosure-summary">Ajustes avanzados</summary>
        <div className="grid gap-x-5 sm:grid-cols-2 pt-3">
          <div className="field"><label htmlFor="settlement" className="field-label">Cómo contar los premios</label><select id="settlement" className={control} value={draft.settlement} onChange={(event) => edit("settlement", event.target.value)}><option value="">Elegí una regla</option>{profileChoice?.item.profile_execution.settlements.filter((mode) => mode === "all" || mode === "best").map((mode) => <option key={mode} value={mode}>{mode === "all" ? "Sumar premios de todas las posiciones" : "Mayor premio por número repetido"}</option>)}</select></div>
          <div className="field"><label htmlFor="staking-policy" className="field-label">Política de apuesta</label><select id="staking-policy" className={control} value={policy} onChange={(event) => { setPolicy(event.target.value as ProfilePolicy); setError(""); }}><option value="fixed">Apuesta fija por número</option>{profileChoice?.item.profile_execution.staking_capabilities.includes("q80-first-prize-cycling/v1") && <option value="cycling">Escalera cíclica de 10 rondas</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-audaz/v1") && profileChoice.item.profile_execution.audaz_compatibility?.available && <option value="audaz">Audaz · apuesta dinámica por objetivo</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-recovery-ladder/v1") && profileChoice.item.profile_execution.recovery_compatibility?.available && <option value="recovery">Escalera de recuperación</option>}</select></div>
          {policy === "fixed" && <Field label={`Apuesta fija por número (${profile?.currency ?? "moneda"})`} id="stake" value={draft.per_number_stake} onChange={(value) => edit("per_number_stake", value)} numeric />}
          {policy === "audaz" && profileChoice && <p className="field-help">Audaz disponible hasta cobertura {profileChoice.item.profile_execution.audaz_compatibility?.maximum_compatible_coverage ?? "no disponible"}.</p>}
          {policy === "recovery" && <><Field label={`Margen objetivo (${profile?.currency ?? "moneda"})`} id="target-margin" value={draft.target_margin} onChange={(value) => edit("target_margin", value)} numeric /><Field label="Rondas de recuperación (1–10.000)" id="recovery-rounds" value={draft.rounds} onChange={(value) => edit("rounds", value)} numeric /><div className="field"><label htmlFor="recovery-end-mode" className="field-label">Al completar las rondas</label><select id="recovery-end-mode" className={control} value={draft.end_mode} onChange={(event) => edit("end_mode", event.target.value)}><option value="">Elegí un comportamiento</option><option value="cycle">Reiniciar la escalera</option><option value="stop">Detener la simulación</option></select></div>{profileChoice && <p className="field-help">Cobertura máxima compatible: {profileChoice.item.profile_execution.recovery_compatibility?.maximum_compatible_coverage ?? "no disponible"}.</p>}</>}
        </div>
        <p className="field-help">{policy === "cycling" ? "La apuesta es dinámica: no hay importe fijo. Reinicia al acertar el primer premio." : policy === "audaz" ? "La apuesta es dinámica: no hay importe fijo." : policy === "recovery" ? "Al agotar las rondas, se reinicia o se detiene según lo elegido." : "El servidor valida el costo inicial al crear la simulación."} Se detiene al primer tope alcanzado.</p>
        </details>
      </section>
      <section aria-labelledby="history-title" className="space-y-6"><h3 id="history-title" className="section-header">Datos del historial</h3>
      <section aria-labelledby="profile-choice-title"><h4 id="profile-choice-title" className="font-medium">Perfil</h4>
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
      </section>
      {datasetChoice && <section aria-labelledby="draw-choice-title"><h4 id="draw-choice-title" className="font-medium">Inicio de la simulación</h4>
        <div className="field"><label htmlFor="profile-draw-date" className="field-label">Filtrar sorteos por fecha</label><input id="profile-draw-date" type="date" className={control} value={drawDate} onChange={(event) => { setDrawDate(event.target.value); setDrawOffset(0); edit("start_draw", ""); }} /></div>
        {!draws && !drawError && <p role="status">Cargando sorteos…</p>}
        {drawError && <p role="alert">{drawError} <button type="button" className="btn btn-tertiary" onClick={() => setDrawRetry((n) => n + 1)}>Reintentar sorteos</button></p>}
        {draws && <><div className="field"><label htmlFor="profile-start-draw" className="field-label">Sorteo inicial</label><select id="profile-start-draw" className={control} value={draws.items.includes(draft.start_draw) ? draft.start_draw : ""} onChange={(event) => edit("start_draw", event.target.value)}><option value="">Elegí un sorteo</option>{draws.items.map((draw) => <option value={draw} key={draw}>{draw}</option>)}</select></div>
          {draws.total === 0 && <p>No hay sorteos para esta fecha.</p>}
          <Pager label="sorteos" offset={drawOffset} total={draws.total} step={100} onChange={(offset) => { setDrawOffset(offset); edit("start_draw", ""); }} /></>}
      </section>}
      </section>
      <section aria-labelledby="selection-title" className="space-y-4"><h3 id="selection-title" className="section-header">Selección para la simulación</h3><details><summary className="disclosure-summary">Ajustes avanzados</summary>
        <div className="grid gap-x-5 sm:grid-cols-2">
          <div className="field"><label htmlFor="selector" className="field-label">Selección</label><select id="selector" className={control} value={draft.selector} onChange={(event) => edit("selector", event.target.value)}><option value="static">Números fijos</option><option value="random" disabled={!!profileChoice && !profileChoice.item.profile_execution.selector_capabilities.includes("seeded-random/hash-sha256-v1")}>Azar reproducible</option></select></div>
          <Field label="Cobertura (números por sorteo)" id="coverage" value={draft.coverage} onChange={(value) => edit("coverage", value)} numeric />
          {draft.selector === "static" ? <Field label="Números distintos, separados por comas" id="numbers" value={draft.numbers} onChange={(value) => edit("numbers", value)} /> :
            <Field label="Semilla de azar (entero no negativo)" id="seed" value={draft.seed} onChange={(value) => edit("seed", value)} numeric />}
        </div></details>
      </section>
      <section aria-labelledby="profile-conditions-title" className="space-y-4"><h3 id="profile-conditions-title" className="section-header">Condiciones de la simulación</h3>
        <div className="grid gap-x-5 sm:grid-cols-2">
          <Field label="Nombre de la simulación" id="name" value={draft.name} onChange={(value) => edit("name", value)} />
          <Field label={`Capital inicial (${profile?.currency ?? "moneda"})`} id="capital" value={draft.capital} onChange={(value) => edit("capital", value)} numeric />
          <Field label={`Meta de saldo final (${profile?.currency ?? "moneda"})`} id="goal" value={draft.goal} onChange={(value) => edit("goal", value)} numeric />
          <Field label="Límite de sorteos transcurridos (1–10.000)" id="elapsed" value={draft.max_elapsed_draws} onChange={(value) => edit("max_elapsed_draws", value)} numeric />
          <details><summary className="disclosure-summary">Ajustes avanzados</summary><Field label="Límite de sorteos apostados (opcional)" id="bet-draws" value={draft.max_bet_draws} onChange={(value) => edit("max_bet_draws", value)} numeric /></details>
        </div>
      </section>
      {error && <p ref={alertRef} tabIndex={-1} role="alert" className="border-y border-border py-3 text-red-300">{error}</p>}
      {uncertain && <p role="status">Envío bloqueado para evitar duplicados. <Link className="btn btn-tertiary" to="/experimentos">Revisá Simulaciones</Link>.</p>}
      <button type="submit" className="btn btn-primary" disabled={disabled}>{posting ? "Creando simulación…" : "Crear simulación y agregar a la cola"}</button>
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
