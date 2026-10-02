import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { DatasetListing, Page, ProfileListing } from "../../api/types";
import { buildProfileRequest, initialProfileDraft, matchingDataset } from "./profile-model";
import type { ProfileDraft, ProfilePolicy } from "./profile-model";

const control = "control";
const secondary = "btn btn-secondary disabled:opacity-50";
const pageSize = 20;

type Choice<T> = { item: T; offset: number };

export function ProfileExperimentPage() {
  const navigate = useNavigate();
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
    }).catch(() => { if (live) setDatasetError("No se pudieron cargar los datos locales. Reintentá."); });
    return () => { live = false; };
  }, [datasetOffset, datasetRetry]);
  useEffect(() => {
    if (!datasetChoice) { setDraws(null); return; }
    let live = true;
    setDraws(null); setDrawError("");
    apiClient.getDatasetDraws(datasetChoice.item.dataset_sha256, drawOffset, 100, drawDate || undefined)
      .then((page) => { if (live) setDraws(page); })
      .catch(() => { if (live) setDrawError("No se pudieron cargar los sorteos de estos datos. Reintentá."); });
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
        setError("El perfil, los datos o el sorteo cambiaron. Actualizá las listas y elegí de nuevo; no se envió la solicitud.");
        return;
      }
      submitted = true;
      const created = await apiClient.createProfileExperiment(body);
      if (!created || typeof created.id !== "string" || !/^[a-f0-9]{32}$/.test(created.id)) {
        setUncertain(true);
        setError("No se pudo confirmar el ID de la sesión. Consultá Experimentos antes de iniciar una solicitud nueva.");
        return;
      }
      navigate(`/experimentos/${encodeURIComponent(created.id)}`, { replace: true });
    } catch (cause) {
      if (submitted && (cause instanceof NetworkError || cause instanceof ApiError && cause.status >= 200 && cause.status < 300)) {
        // No safe idempotency key exists for this POST: never automatically retry.
        setUncertain(true);
        setError("No llegó una confirmación de la sesión. Podría estar en la cola; consultá Experimentos antes de crear otra.");
      } else if (!submitted && cause instanceof NetworkError) {
        setError("No se pudo verificar el perfil o los datos. No se envió la sesión; reintentá cuando vuelva el servidor.");
      } else if (cause instanceof ApiError && cause.status === 409) {
        setError("El perfil, los datos o la apuesta no pasaron la admisión, o la cola no está disponible. Revisá el catálogo y los importes antes de volver a intentar.");
      } else if (cause instanceof ApiError && cause.status === 507) {
        setError("No hay capacidad disponible. Revisá el almacenamiento antes de intentar de nuevo.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setError("El servidor rechazó el documento de sesión. Revisá los campos y las capacidades disponibles.");
      } else {
        if (submitted) setUncertain(true);
        setError(submitted ? "No se pudo confirmar la creación. Consultá Experimentos antes de iniciar otra solicitud." :
          "No se pudieron verificar las opciones. No se envió la sesión; actualizá las listas y reintentá.");
      }
    } finally { inFlight.current = false; setPosting(false); }
  }

  const profile = profileChoice?.item.profile;
  const compatible = datasets?.items.filter((item) => profileChoice && matchingDataset(profileChoice.item, item)) ?? [];
  const disabled = posting || uncertain || !profiles || !datasets || !draws || !!profileError || !!datasetError || !!drawError;
  return <div className="max-w-prose space-y-7">
    <Link to="/experimentos/nuevo" className="text-accent underline">Volver al asistente clásico</Link>
    <div><h2 className="text-2xl">Sesión con perfil registrado</h2><p className="field-help">Usá un perfil inmutable y datos locales ya importados. Elegí una política de apuesta ofrecida por el servidor para este perfil. Los rankings y otras familias todavía no están disponibles para perfiles.</p></div>
    <form onSubmit={(event) => { void submit(event); }} noValidate className="space-y-6">
      <section aria-labelledby="profile-choice-title"><h3 id="profile-choice-title" className="section-header">Perfil registrado</h3>
        {!profiles && !profileError && <p role="status">Cargando perfiles…</p>}
        {profileError && <p role="alert">{profileError} <button type="button" className="text-accent underline" onClick={() => setProfileRetry((n) => n + 1)}>Reintentar perfiles</button></p>}
        {profiles && <><div className="field"><label htmlFor="profile-choice" className="field-label">Perfil y revisión</label><select id="profile-choice" className={control} value={profileChoice && profileChoice.offset === profileOffset ? `${profileChoice.item.profile.profile_id}@${profileChoice.item.profile.revision}` : ""} onChange={(event) => { const item = profiles.items.find((entry) => `${entry.profile.profile_id}@${entry.profile.revision}` === event.target.value); if (item) chooseProfile(item); }}><option value="">Elegí un perfil de esta página</option>{profiles.items.map((item) => <option key={`${item.profile.profile_id}@${item.profile.revision}`} value={`${item.profile.profile_id}@${item.profile.revision}`} disabled={!item.profile_execution.ready}>{item.profile.profile_id} · revisión {item.profile.revision}{!item.profile_execution.ready ? " (no disponible)" : ""}</option>)}</select></div>
          {profiles.total === 0 && <p>No hay perfiles registrados. <Link to="/datos" className="text-accent underline">Registrá uno en Datos</Link>.</p>}
          <Pager label="perfiles" offset={profileOffset} total={profiles.total} step={pageSize} onChange={setProfileOffset} /></>}
        {profile && <p role="status" className="field-help">Seleccionado: {profile.profile_id} · {profile.currency}, escala {profile.scale}; universo {profile.universe_size}, cobertura máxima {profile.max_coverage}. Los importes se ingresan en {profile.currency}; el servidor conserva unidades enteras.</p>}
      </section>
      <section aria-labelledby="dataset-choice-title"><h3 id="dataset-choice-title" className="section-header">Datos locales verificados</h3>
        {!datasets && !datasetError && <p role="status">Cargando datos…</p>}
        {datasetError && <p role="alert">{datasetError} <button type="button" className="text-accent underline" onClick={() => setDatasetRetry((n) => n + 1)}>Reintentar datos</button></p>}
        {datasets && <><div className="field"><label htmlFor="dataset-choice" className="field-label">Versión de datos compatible</label><select id="dataset-choice" className={control} disabled={!profileChoice} value={datasetChoice?.offset === datasetOffset ? datasetChoice.item.dataset_sha256 : ""} onChange={(event) => { const item = datasets.items.find((entry) => entry.dataset_sha256 === event.target.value); if (item) chooseDataset(item); }}><option value="">Elegí datos de esta página</option>{compatible.map((item) => <option key={item.dataset_sha256} value={item.dataset_sha256}>{item.source_id} · {item.source_revision} · {item.records_total} sorteos · {item.dataset_sha256.slice(0, 12)}</option>)}</select></div>
          {profileChoice && !compatible.length && <p className="field-help">No hay datos compatibles en esta página. Recorré las páginas o <Link to="/datos" className="text-accent underline">importá JSON local en Datos</Link>.</p>}
          <Pager label="datos" offset={datasetOffset} total={datasets.total} step={pageSize} onChange={setDatasetOffset} /></>}
      </section>
      {datasetChoice && <section aria-labelledby="draw-choice-title"><h3 id="draw-choice-title" className="section-header">Inicio de la sesión</h3>
        <div className="field"><label htmlFor="profile-draw-date" className="field-label">Filtrar sorteos por fecha</label><input id="profile-draw-date" type="date" className={control} value={drawDate} onChange={(event) => { setDrawDate(event.target.value); setDrawOffset(0); edit("start_draw", ""); }} /><p className="field-help">Buscá una fecha directa sin cargar el histórico anterior.</p></div>
        {!draws && !drawError && <p role="status">Cargando sorteos…</p>}
        {drawError && <p role="alert">{drawError} <button type="button" className="text-accent underline" onClick={() => setDrawRetry((n) => n + 1)}>Reintentar sorteos</button></p>}
        {draws && <><div className="field"><label htmlFor="profile-start-draw" className="field-label">Sorteo inicial</label><select id="profile-start-draw" className={control} value={draws.items.includes(draft.start_draw) ? draft.start_draw : ""} onChange={(event) => edit("start_draw", event.target.value)}><option value="">Elegí un sorteo de esta página</option>{draws.items.map((draw) => <option value={draw} key={draw}>{draw}</option>)}</select></div>
          {draws.total === 0 && <p>No hay sorteos para esta fecha.</p>}
          <Pager label="sorteos" offset={drawOffset} total={draws.total} step={100} onChange={(offset) => { setDrawOffset(offset); edit("start_draw", ""); }} /></>}
      </section>}
      <section aria-labelledby="profile-conditions-title"><h3 id="profile-conditions-title" className="section-header">Condiciones y selección</h3>
        <div className="grid gap-x-5 sm:grid-cols-2">
          <Field label="Nombre de la sesión" id="name" value={draft.name} onChange={(value) => edit("name", value)} />
          <Field label={`Capital inicial (${profile?.currency ?? "moneda"})`} id="capital" value={draft.capital} onChange={(value) => edit("capital", value)} numeric />
          <Field label={`Meta de saldo final (${profile?.currency ?? "moneda"})`} id="goal" value={draft.goal} onChange={(value) => edit("goal", value)} numeric />
          <Field label="Límite de sorteos transcurridos (1–10.000)" id="elapsed" value={draft.max_elapsed_draws} onChange={(value) => edit("max_elapsed_draws", value)} numeric />
          <Field label="Límite de sorteos apostados (opcional)" id="bet-draws" value={draft.max_bet_draws} onChange={(value) => edit("max_bet_draws", value)} numeric />
          <div className="field"><label htmlFor="settlement" className="field-label">Liquidación explícita</label><select id="settlement" className={control} value={draft.settlement} onChange={(event) => edit("settlement", event.target.value)}><option value="">Elegí una regla</option>{profileChoice?.item.profile_execution.settlements.filter((mode) => mode === "all" || mode === "best").map((mode) => <option key={mode} value={mode}>{mode === "all" ? "Sumar premios de todas las posiciones" : "Mayor premio por número repetido"}</option>)}</select></div>
          <div className="field"><label htmlFor="selector" className="field-label">Selección</label><select id="selector" className={control} value={draft.selector} onChange={(event) => edit("selector", event.target.value)}><option value="static">Números fijos</option><option value="random" disabled={!!profileChoice && !profileChoice.item.profile_execution.selector_capabilities.includes("seeded-random/hash-sha256-v1")}>Azar reproducible</option></select></div>
          <Field label="Cobertura (números por sorteo)" id="coverage" value={draft.coverage} onChange={(value) => edit("coverage", value)} numeric />
          {draft.selector === "static" ? <Field label="Números distintos, separados por comas" id="numbers" value={draft.numbers} onChange={(value) => edit("numbers", value)} /> :
            <Field label="Semilla de azar (entero no negativo)" id="seed" value={draft.seed} onChange={(value) => edit("seed", value)} numeric />}
          <div className="field"><label htmlFor="staking-policy" className="field-label">Política de apuesta</label><select id="staking-policy" className={control} value={policy} onChange={(event) => { setPolicy(event.target.value as ProfilePolicy); setError(""); }}><option value="fixed">Apuesta fija por número (v1)</option>{profileChoice?.item.profile_execution.staking_capabilities.includes("q80-first-prize-cycling/v1") && <option value="cycling">Q80 CYCLING · escalera cíclica de 10 rondas (v2)</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-audaz/v1") && profileChoice.item.profile_execution.audaz_compatibility?.available && <option value="audaz">Audaz · apuesta dinámica por objetivo (v3)</option>}{profileChoice?.item.profile_execution.staking_capabilities.includes("profile-recovery-ladder/v1") && profileChoice.item.profile_execution.recovery_compatibility?.available && <option value="recovery">Escalera de recuperación por perfil (v4)</option>}</select></div>
          {policy === "fixed" && <Field label={`Apuesta fija por número (${profile?.currency ?? "moneda"})`} id="stake" value={draft.per_number_stake} onChange={(value) => edit("per_number_stake", value)} numeric />}
          {policy === "audaz" && profileChoice && <p className="field-help">Audaz dinámico: el servidor ofrece esta política hasta cobertura {profileChoice.item.profile_execution.audaz_compatibility?.maximum_compatible_coverage ?? "no disponible"} para el perfil seleccionado. La cobertura concreta debe seguir siendo compatible; el servidor valida la apuesta inicial y la financiación.</p>}
          {policy === "recovery" && <><Field label={`Margen objetivo (${profile?.currency ?? "moneda"})`} id="target-margin" value={draft.target_margin} onChange={(value) => edit("target_margin", value)} numeric /><Field label="Rondas de recuperación (1–10.000)" id="recovery-rounds" value={draft.rounds} onChange={(value) => edit("rounds", value)} numeric /><div className="field"><label htmlFor="recovery-end-mode" className="field-label">Al completar las rondas</label><select id="recovery-end-mode" className={control} value={draft.end_mode} onChange={(event) => edit("end_mode", event.target.value)}><option value="">Elegí un comportamiento</option><option value="cycle">Reiniciar la escalera</option><option value="stop">Detener la sesión</option></select></div>{profileChoice && <p className="field-help">La compatibilidad de cobertura se deriva del multiplicador de primera posición y los límites del perfil; máximo {profileChoice.item.profile_execution.recovery_compatibility?.maximum_compatible_coverage ?? "no disponible"}. El servidor valida la escalera completa, incrementos, apuesta máxima, exposición y capital inicial.</p>}</>}
        </div><p className="field-help">Entrada: todos los sorteos desde el inicio. Los topes se aplican al primero alcanzado. {policy === "cycling" ? "Q80 CYCLING: escalera completa de 10 rondas, ciclo tras diez fallos y reinicio al acertar el primer premio. La apuesta es dinámica; no ingreses un importe fijo. El servidor valida todas las rondas y que el capital alcance la primera apuesta antes de crear la sesión." : policy === "audaz" ? "Audaz ajusta dinámicamente la apuesta durante la sesión. No ingreses un importe fijo; el servidor valida la apuesta inicial y la financiación antes de crear la sesión." : policy === "recovery" ? "La escalera de recuperación calcula sus rondas en unidades exactas del perfil. Al agotarlas, el comportamiento elegido determina si reinicia o detiene. El servidor valida admisión, financiación y límites." : "El costo inicial y la exposición se validan al admitir la sesión; el servidor confirma la admisión."}</p>
      </section>
      {error && <p ref={alertRef} tabIndex={-1} role="alert" className="border-y border-border py-3 text-red-300">{error}</p>}
      {uncertain && <p role="status">El envío está bloqueado para evitar duplicados. <Link className="text-accent underline" to="/experimentos">Comprobá Experimentos</Link>; para una nueva solicitud volvé a entrar al creador.</p>}
      <button type="submit" className="btn btn-primary disabled:opacity-50" disabled={disabled}>{posting ? "Enviando sesión…" : "Crear sesión y agregar a la cola"}</button>
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
