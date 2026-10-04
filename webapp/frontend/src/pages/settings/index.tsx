import { useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { SettingsView } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorBanner, Loading } from "../../components/ui";

const MAX_QUOTA = 9223372036854775807n;
const GIB = 1073741824n;
const action = "btn btn-secondary disabled:cursor-not-allowed";
const metric = "metric-item";

function grouped(value: bigint): string {
  try { return new Intl.NumberFormat("es-DO", { useGrouping: true }).format(value); }
  catch { return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
}
function bytes(value: string): string {
  // Exact string/BigInt path: do not round an int64 quota through Number.
  return `${grouped(BigInt(value))} bytes`;
}
function readableCapacity(value: string): string {
  const exact = BigInt(value);
  const units = [[1099511627776n, "TiB"], [GIB, "GiB"], [1048576n, "MiB"], [1024n, "KiB"]] as const;
  const [divisor, label] = units.find(([size]) => exact >= size) ?? [1n, "bytes"];
  if (divisor === 1n) return `${grouped(exact)} ${label}`;
  const tenths = (exact * 10n + divisor / 2n) / divisor;
  return `${grouped(tenths / 10n)}${tenths % 10n ? `.${tenths % 10n}` : ""} ${label}`;
}
function measured(value: number): string {
  // Physical and free-disk fields are legacy JSON numbers; unlike quota they
  // have no exact string representation from this API.
  try { return `${new Intl.NumberFormat("es-DO").format(value)} bytes`; }
  catch { return `${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",")} bytes`; }
}
function validate(value: string): string | null {
  if (!/^[1-9][0-9]*$/.test(value) || value.length > 19 || BigInt(value) > MAX_QUOTA) {
    return "Ingresá un entero en bytes, entre 1 y 9,223,372,036,854,775,807, sin separadores, espacios ni ceros iniciales.";
  }
  return null;
}

export function SettingsPage() {
  const [view, setView] = useState<SettingsView | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [agentCredential, setAgentCredential] = useState<string | null>(null);
  const [agentCredentialVisible, setAgentCredentialVisible] = useState(false);
  const [agentCredentialLoading, setAgentCredentialLoading] = useState(false);
  const [agentCredentialCopying, setAgentCredentialCopying] = useState(false);
  const [agentCredentialError, setAgentCredentialError] = useState("");
  const [agentCredentialCopied, setAgentCredentialCopied] = useState(false);
  const [manualCopyFallback, setManualCopyFallback] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const agentCredentialInputRef = useRef<HTMLInputElement>(null);
  const agentCredentialTriggerRef = useRef<HTMLButtonElement>(null);
  const restoreAgentCredentialFocusRef = useRef(false);
  const dirtyRef = useRef(false);
  const saveRef = useRef(false);
  const requestRef = useRef(0);
  const agentCredentialSequenceRef = useRef(0);
  const agentCredentialBusyRef = useRef(false);
  const agentCredentialCopyBusyRef = useRef(false);
  const dirty = !!view && draft !== null && draft !== view.quota.effective_bytes;
  // Current servers report the aggregate. Older captured responses may only
  // report historical experiment bytes; make that incomplete fallback visible.
  const hasAdmission = typeof view?.storage.admission_logical_bytes_exact === "string";
  const used = view ? BigInt(hasAdmission ? view.storage.admission_logical_bytes_exact : view.storage.logical_used_bytes_exact) : 0n;
  const limit = view ? BigInt(view.quota.effective_bytes) : 0n;
  const remaining = limit > used ? limit - used : 0n;
  // The conversion is of a bounded 0..100 integer, never of byte counts.
  const progress = limit > 0n ? Number((used < limit ? used : limit) * 100n / limit) : 0;
  dirtyRef.current = dirty;
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    dirty && currentLocation.pathname !== nextLocation.pathname);

  useEffect(() => { if (fieldError && !saving) inputRef.current?.focus(); }, [fieldError, saving]);

  useEffect(() => {
    if (!dirty) return;
    function warnBeforeUnload(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = ""; }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [dirty]);

  useEffect(() => {
    let live = true;
    const sequence = ++requestRef.current;
    if (!view) setLoading(true);
    setLoadError("");
    apiClient.getSettings().then((value) => {
      if (!live || sequence !== requestRef.current) return;
      setView(value);
      if (!dirtyRef.current) setDraft(value.quota.effective_bytes);
      setLoadError(""); setLoading(false);
    }).catch((error: unknown) => {
      if (!live || sequence !== requestRef.current) return;
      setLoadError(error instanceof NetworkError
        ? "No se pudo contactar al servidor."
        : "No se pudieron cargar los ajustes.");
      setLoading(false);
    });
    return () => { live = false; };
    // Refresh is explicit; a draft never triggers a new GET.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  useEffect(() => () => {
    agentCredentialSequenceRef.current += 1;
    agentCredentialBusyRef.current = false;
    agentCredentialCopyBusyRef.current = false;
  }, []);

  useEffect(() => {
    if (!manualCopyFallback || !agentCredential || !agentCredentialVisible) return;
    agentCredentialInputRef.current?.focus();
    agentCredentialInputRef.current?.select();
  }, [agentCredential, agentCredentialVisible, manualCopyFallback]);

  useEffect(() => {
    if (!restoreAgentCredentialFocusRef.current || agentCredential || agentCredentialLoading) return;
    const trigger = agentCredentialTriggerRef.current;
    if (!trigger) return;
    restoreAgentCredentialFocusRef.current = false;
    trigger.focus();
  }, [agentCredential, agentCredentialLoading]);

  async function retrieveAgentCredential() {
    if (agentCredentialBusyRef.current) return;
    const sequence = ++agentCredentialSequenceRef.current;
    agentCredentialBusyRef.current = true;
    setAgentCredentialLoading(true);
    setAgentCredentialError("");
    setAgentCredentialCopied(false);
    setManualCopyFallback(false);
    try {
      const response = await apiClient.getAgentCredential();
      if (sequence !== agentCredentialSequenceRef.current) return;
      if (typeof response?.token !== "string" || response.token.length === 0) {
        throw new Error("invalid credential response");
      }
      setAgentCredential(response.token);
      setAgentCredentialVisible(false);
    } catch (failure) {
      if (sequence !== agentCredentialSequenceRef.current) return;
      if (failure instanceof NetworkError) {
        setAgentCredentialError("No se pudo contactar al servidor. Reintentá.");
      } else if (failure instanceof ApiError && failure.status === 403) {
        setAgentCredentialError("El servidor rechazó el origen. Abrí la aplicación desde la dirección local del servidor.");
      } else if (failure instanceof ApiError && failure.status === 401) {
        setAgentCredentialError("El servidor rechazó la solicitud. Reintentá.");
      } else {
        setAgentCredentialError("No se pudo consultar la credencial. Reintentá.");
      }
    } finally {
      if (sequence === agentCredentialSequenceRef.current) {
        agentCredentialBusyRef.current = false;
        setAgentCredentialLoading(false);
      }
    }
  }

  function hideAgentCredential() {
    restoreAgentCredentialFocusRef.current = true;
    agentCredentialSequenceRef.current += 1;
    agentCredentialBusyRef.current = false;
    agentCredentialCopyBusyRef.current = false;
    setAgentCredential(null);
    setAgentCredentialVisible(false);
    setAgentCredentialLoading(false);
    setAgentCredentialCopying(false);
    setAgentCredentialError("");
    setAgentCredentialCopied(false);
    setManualCopyFallback(false);
  }

  async function copyAgentCredential() {
    if (!agentCredential || agentCredentialCopyBusyRef.current) return;
    const sequence = agentCredentialSequenceRef.current;
    agentCredentialCopyBusyRef.current = true;
    setAgentCredentialCopying(true);
    setAgentCredentialCopied(false);
    setAgentCredentialError("");
    setManualCopyFallback(false);
    try {
      const clipboard = navigator.clipboard;
      if (typeof clipboard?.writeText !== "function") throw new Error("clipboard unavailable");
      await clipboard.writeText(agentCredential);
      if (sequence !== agentCredentialSequenceRef.current) return;
      setAgentCredentialCopied(true);
    } catch {
      if (sequence !== agentCredentialSequenceRef.current) return;
      setAgentCredentialVisible(true);
      setManualCopyFallback(true);
      setAgentCredentialError("No se pudo copiar. Seleccioná y copiá el texto mostrado manualmente.");
    } finally {
      if (sequence === agentCredentialSequenceRef.current) {
        agentCredentialCopyBusyRef.current = false;
        setAgentCredentialCopying(false);
      }
    }
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!view?.quota.writable || draft === null || saveRef.current) return;
    const error = validate(draft) ?? (BigInt(draft) < used
      ? `El límite no puede ser menor que el uso actual (${bytes(used.toString())}).`
      : null);
    setFieldError(error ?? ""); setSaveError(""); setSaved(false);
    if (error) { inputRef.current?.focus(); return; }
    saveRef.current = true; setSaving(true);
    const sequence = ++requestRef.current;
    try {
      const value = await apiClient.updateSettings(draft);
      if (sequence !== requestRef.current) return;
      setView(value);
      setDraft(value.quota.effective_bytes); // PUT returns the full authoritative view.
      dirtyRef.current = false;
      setSaved(true);
    } catch (failure) {
      if (sequence !== requestRef.current) return;
      if (failure instanceof ApiError && failure.status === 422 && failure.fieldErrors?.some((entry) =>
        entry.loc.map(String).join(".") === "body.quota_bytes")) {
        setFieldError("El servidor rechazó el límite. Revisá el valor.");
      } else if (failure instanceof ApiError && failure.status === 409) {
        setSaveError(failure.detail === "environment quota is read-only"
          ? "El entorno fija el límite y no se puede cambiar desde la web. Actualizá el estado."
          : "El límite no puede ser menor que el uso actual. Actualizá el estado e ingresá un valor mayor.");
      } else if (failure instanceof NetworkError) {
        setSaveError("Sin respuesta del servidor. Puede que se haya guardado; actualizá el estado antes de reintentar.");
      } else if (failure instanceof ApiError && failure.status === 403) {
        setSaveError("El servidor rechazó el origen. Abrí la aplicación desde la dirección local del servidor.");
      } else {
        setSaveError("No se pudo guardar el límite. Tus cambios siguen en el campo; reintentá.");
      }
    } finally { saveRef.current = false; setSaving(false); }
  }

  const sourceName = view?.quota.source === "environment" ? "Variable de entorno" : view?.quota.source === "persisted" ? "Preferencia guardada" : "Por defecto";
  return <div className="max-w-5xl space-y-8">
    {view && <div className="flex justify-end">
      <button type="button" className="btn btn-secondary disabled:cursor-not-allowed" disabled={saving} onClick={() => setRefresh((previous) => previous + 1)}>Actualizar estado</button>
    </div>}
    {loading && <Loading rows={3} label="Cargando capacidad y límites…" className="border-y border-border py-5" />}
    {loadError && <ErrorBanner cause={loadError} recovery={view ? "Se muestra la última lectura; reintentá para actualizarla." : "Comprobá que el laboratorio siga abierto y reintentá."} preserved={!!view} actionLabel="Reintentar" onAction={() => setRefresh((previous) => previous + 1)} />}
    {view && <>
      <section aria-labelledby="storage-heading" className="border-t border-border pt-5">
        <h2 id="storage-heading" className="section-header">Capacidad</h2>
        <div className="metric-grid">
          <div className={metric}><h3 className="field-label">Límite de almacenamiento</h3><p className="metric-value">{readableCapacity(view.quota.effective_bytes)}</p></div>
          <div className={metric}><h3 className="field-label">Usado</h3><p className="metric-value">{readableCapacity(used.toString())}</p></div>
          {hasAdmission && <div className={metric}><h3 className="field-label">Disponible</h3><p className="metric-value"><span className="tabular-nums">{readableCapacity(remaining.toString())}</span></p></div>}
        </div>
        {hasAdmission
          ? <progress className="mt-4 w-full accent-accent" aria-label="Cuota lógica utilizada" value={progress} max={100} />
          : <p className="mt-4 text-sm text-text-secondary">Uso incompleto: este servidor no informa el total.</p>}
        {hasAdmission && used > limit && <p className="mt-2 text-sm text-text-secondary">Uso superior al límite por {bytes((used - limit).toString())}.</p>}
        <p className="mt-3 text-sm text-text-secondary">El límite de almacenamiento no es el espacio libre en disco.</p>
        {view.storage.warning && <p role="alert" className="mt-4 border border-border-control bg-field p-3 text-sm">El servidor avisa: cerca del límite o falta de disco.</p>}
      </section>
      <section aria-labelledby="quota-form-heading" className="border-t border-border pt-5">
        <h2 id="quota-form-heading" className="section-header">Cambiar límite</h2>
        {view.quota.writable ? <form onSubmit={(event) => { void save(event); }} noValidate className="max-w-xl">
          <label htmlFor="quota-bytes" className="field-label">Nuevo límite de almacenamiento</label>
          <input ref={inputRef} id="quota-bytes" type="text" inputMode="numeric" autoComplete="off" spellCheck={false} value={draft ?? ""} disabled={saving} aria-invalid={!!fieldError} aria-describedby={fieldError ? "quota-help quota-error" : "quota-help"} onChange={(event) => { setDraft(event.target.value); setFieldError(""); setSaveError(""); setSaved(false); }} className="control font-mono tabular-nums" />
          <p id="quota-help" className="field-help">Entero positivo, sin separadores. Mínimo {readableCapacity(used.toString())} ({bytes(used.toString())}). Ej.: 5368709120 (5 GiB).</p>
          {fieldError && <p id="quota-error" className="mt-2 text-sm text-red-300">{fieldError}</p>}
          {saveError && <p role="alert" className="mt-2 text-sm text-red-300">{saveError}</p>}
          {saved && <p role="status" className="mt-2 text-sm text-accent">Guardado.</p>}
          <button type="submit" className="btn btn-primary mt-4" disabled={saving}>{saving ? "Guardando…" : "Guardar límite"}</button>
        </form> : <div className="max-w-prose text-text-secondary"><p>El entorno del servidor fija el límite; aquí es de solo lectura.</p>{dirty && <p className="mt-2 break-words">Borrador no guardado: <span className="font-mono">{draft}</span> bytes. No se envió.</p>}</div>}
      </section>
      <details className="border-y border-border py-3"><summary className="disclosure-summary">Detalles técnicos</summary>
        <div className="mt-4 space-y-6 text-sm">
          <dl className="metric-grid">
            <div className={metric}><dt>Origen del límite</dt><dd>{sourceName}</dd></div>
            <div className={metric}><dt>Límite efectivo en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(view.quota.effective_bytes)}</dd></div>
            <div className={metric}><dt>Preferencia persistida</dt><dd className="break-words font-mono tabular-nums">{view.quota.persisted_bytes === null ? "ninguna" : bytes(view.quota.persisted_bytes)}</dd></div>
            {hasAdmission && <>
              <div className={metric}><dt>Disponible en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(remaining.toString())}</dd></div>
              <div className={metric}><dt>Uso agregado en bytes</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.admission_logical_bytes_exact!)}</dd></div>
              <div className={metric}><dt>Experimentos y ejecuciones históricos</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.logical_used_bytes_exact)}</dd></div>
              <div className={metric}><dt>Artefactos de perfiles (copias JSON)</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.profile_artifact_bytes_exact)}</dd></div>
              <div className={metric}><dt>Artefactos de datasets</dt><dd className="break-words font-mono tabular-nums">{bytes(view.storage.dataset_artifact_bytes_exact)}</dd></div>
            </>}
          </dl>
          <section aria-labelledby="physical-heading">
            <h3 id="physical-heading" className="field-label">Archivos físicos y disco</h3>
            <dl className="metric-grid">
              <div className={metric}><dt>SQLite y archivos locales (total informado)</dt><dd className="break-words font-mono">{measured(view.storage.sqlite_bytes)}</dd></div>
              <div className={metric}><dt>Espacio en disco libre</dt><dd className="break-words font-mono">{measured(view.storage.free_disk_bytes)}</dd></div>
              <div className={metric}><dt>Base SQLite</dt><dd className="break-words font-mono">{measured(view.storage.database_bytes)}</dd></div>
              <div className={metric}><dt>WAL</dt><dd className="break-words font-mono">{measured(view.storage.wal_bytes)}</dd></div>
              <div className={metric}><dt>SHM</dt><dd className="break-words font-mono">{measured(view.storage.shm_bytes)}</dd></div>
              <div className={metric}><dt>Temporales locales</dt><dd className="break-words font-mono">{measured(view.storage.temp_bytes)}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="sources-heading">
            <h3 id="sources-heading" className="field-label">Datos de origen</h3>
            <dl className="space-y-3">
              <div><dt className="text-text-secondary">Historial · identificador</dt><dd className="break-all font-mono">{view.sources.history_id}</dd></div>
              <div><dt className="text-text-secondary">Historial · SHA-256</dt><dd className="break-all font-mono">{view.sources.history_sha256}</dd></div>
              <div><dt className="text-text-secondary">Rankings · identificador</dt><dd className="break-all font-mono">{view.sources.rankings_id}</dd></div>
              <div><dt className="text-text-secondary">Rankings · SHA-256</dt><dd className="break-all font-mono">{view.sources.rankings_sha256}</dd></div>
              <div><dt className="text-text-secondary">Versión de código</dt><dd className="break-all font-mono">{view.sources.code_version}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="connection-heading">
            <h3 id="connection-heading" className="field-label">Conexión local</h3>
            <dl className="metric-grid">
              <div className={metric}><dt>Servidor</dt><dd className="font-mono">{view.connection.host}:{view.connection.port}</dd></div>
              <div className={metric}><dt>Versión</dt><dd className="font-mono">{view.connection.version}</dd></div>
            </dl>
            <p className="mt-3 text-text-secondary">Iniciar: <code>iniciar-laboratorio.bat</code>. Detener: Ctrl+C en su consola.</p>
          </section>
        </div>
      </details>
      <details className="border-y border-border py-3">
        <summary id="agent-access-heading" className="disclosure-summary">Acceso para agentes</summary>
        <p className="mt-3 max-w-prose text-sm text-text-secondary">No compartas esta credencial de acceso a la API.</p>
        {!agentCredential && !agentCredentialLoading && <button ref={agentCredentialTriggerRef} type="button" className={`${action} mt-4`} onClick={() => { void retrieveAgentCredential(); }}>
          {agentCredentialError ? "Reintentar consulta" : "Consultar credencial de agente"}
        </button>}
        {agentCredentialLoading && <div className="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" className={action} disabled>Consultando credencial…</button>
          <button type="button" className={action} onClick={hideAgentCredential}>Cancelar</button>
        </div>}
        {agentCredentialError && <p role="alert" className="mt-3 max-w-prose text-sm text-red-300">{agentCredentialError}</p>}
        {agentCredential && <div className="mt-4 max-w-2xl">
          <label htmlFor="agent-credential" className="field-label">Credencial de agente</label>
          <input
            ref={agentCredentialInputRef}
            id="agent-credential"
            type={agentCredentialVisible ? "text" : "password"}
            className="control mt-2 w-full font-mono"
            value={agentCredential}
            readOnly
            autoComplete="off"
            spellCheck={false}
            aria-describedby="agent-credential-help"
          />
          <p id="agent-credential-help" className="field-help mt-2">Ocultarla la borra de la pantalla.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" className={action} onClick={() => { setAgentCredentialVisible((value) => !value); setManualCopyFallback(false); }}>
              {agentCredentialVisible ? "Ocultar credencial" : "Mostrar credencial"}
            </button>
            <button type="button" className={action} disabled={agentCredentialCopying} onClick={() => { void copyAgentCredential(); }}>
              {agentCredentialCopying ? "Copiando…" : "Copiar credencial"}
            </button>
            <button type="button" className={action} onClick={hideAgentCredential}>Ocultar y borrar credencial</button>
          </div>
          {agentCredentialCopied && <p role="status" className="mt-3 text-sm text-accent">Credencial copiada al portapapeles.</p>}
        </div>}
      </details>
    </>}
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás el límite sin guardar." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onCancel={() => blocker.reset?.()} onConfirm={() => blocker.proceed?.()} />
  </div>;
}
