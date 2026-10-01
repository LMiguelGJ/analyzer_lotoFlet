import { useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { SettingsView } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";

const MAX_QUOTA = 9223372036854775807n;
const GIB = 1073741824n;
const action = "btn btn-secondary disabled:cursor-not-allowed disabled:opacity-50";
const metric = "metric-item";

function grouped(value: bigint): string {
  try { return new Intl.NumberFormat("es-DO", { useGrouping: true }).format(value); }
  catch { return value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
}
function bytes(value: string): string {
  // Exact string/BigInt path: do not round an int64 quota through Number.
  return `${grouped(BigInt(value))} bytes`;
}
function budget(value: string): string {
  const exact = BigInt(value);
  return exact >= GIB && exact % GIB === 0n
    ? `${grouped(exact / GIB)} GiB (${bytes(value)})`
    : bytes(value);
}
function measured(value: number): string {
  // Physical and free-disk fields are legacy JSON numbers; unlike quota they
  // have no exact string representation from this API.
  try { return `${new Intl.NumberFormat("es-DO").format(value)} bytes`; }
  catch { return `${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",")} bytes`; }
}
function validate(value: string): string | null {
  if (!/^[1-9][0-9]*$/.test(value) || value.length > 19 || BigInt(value) > MAX_QUOTA) {
    return "Ingresá un entero decimal ASCII en bytes, entre 1 y 9,223,372,036,854,775,807, sin separadores, espacios ni ceros iniciales.";
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
  const inputRef = useRef<HTMLInputElement>(null);
  const dirtyRef = useRef(false);
  const saveRef = useRef(false);
  const requestRef = useRef(0);
  const dirty = !!view && draft !== null && draft !== view.quota.effective_bytes;
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
        ? "No se pudo contactar al servidor local. La desconexión no demuestra que el servidor se haya detenido."
        : "No se pudieron cargar los ajustes. Reintentá.");
      setLoading(false);
    });
    return () => { live = false; };
    // Refresh is explicit; a draft never triggers a new GET.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refresh]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!view?.quota.writable || draft === null || saveRef.current) return;
    const error = validate(draft);
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
        setFieldError("El servidor rechazó el presupuesto en bytes. Revisá el valor e intentá de nuevo.");
      } else if (failure instanceof ApiError && failure.status === 409) {
        setSaveError(failure.detail === "environment quota is read-only"
          ? "La variable de entorno tiene prioridad y bloquea cambios desde la web. Actualizá el estado antes de editar."
          : "El presupuesto no puede ser menor que el uso lógico actual. No se liberó capacidad; actualizá el estado e ingresá un valor mayor.");
      } else if (failure instanceof NetworkError) {
        setSaveError("No se pudo contactar al servidor local. La solicitud podría haber llegado; actualizá el estado antes de reintentar.");
      } else if (failure instanceof ApiError && failure.status === 403) {
        setSaveError("El servidor rechazó el origen de la solicitud. Abrí la aplicación desde su origen local autorizado.");
      } else {
        setSaveError("No se pudo guardar el presupuesto. Tus cambios siguen en el campo; reintentá.");
      }
    } finally { saveRef.current = false; setSaving(false); }
  }

  return <div className="max-w-5xl space-y-8">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <p className="max-w-prose text-text-secondary">Límite y uso de las simulaciones, separados del tamaño de archivos y del espacio libre en disco.</p>
      {view && <button type="button" className={action} disabled={saving} onClick={() => setRefresh((previous) => previous + 1)}>Actualizar estado</button>}
    </div>
    {loading && <p role="status" className="border-y border-border py-5 text-text-secondary">Cargando ajustes…</p>}
    {loadError && <p role="alert" className="text-red-300">{loadError} <button type="button" className="text-accent underline" onClick={() => setRefresh((previous) => previous + 1)}>Reintentar</button></p>}
    {view && <>
      <section aria-labelledby="storage-heading" className="border-t border-border pt-5">
        <h2 id="storage-heading" className="section-header">Límite y uso lógico</h2>
        <div className="metric-grid">
          <div className={metric}><h3 className="field-label">Límite lógico efectivo</h3><p className="metric-value">{budget(view.quota.effective_bytes)}</p><p className="field-help">{view.quota.source === "environment" ? "Variable de entorno (prioridad máxima)" : view.quota.source === "persisted" ? "Preferencia guardada" : "Por defecto: 5 GiB"}</p></div>
          <div className={metric}><h3 className="field-label">Uso lógico</h3><p className="metric-value">{bytes(view.storage.logical_used_bytes_exact)}</p><p className="field-help">Experimentos y ejecuciones contabilizados por el servidor; no equivale al tamaño de los archivos.</p></div>
        </div>
        <p className="mt-4 text-sm text-text-secondary">Preferencia persistida: {view.quota.persisted_bytes === null ? "ninguna" : bytes(view.quota.persisted_bytes)}. {view.quota.source === "environment" ? "La variable de entorno prevalece sobre la preferencia persistida." : "Se conserva entre reinicios del servidor."}</p>
        {view.storage.warning && <p role="alert" className="mt-4 border border-border-control bg-field p-3 text-sm">Advertencia: el servidor señala proximidad al límite o falta de disco para nuevas escrituras. No se borra nada automáticamente.</p>}
        <p className="mt-4 max-w-prose text-sm text-text-secondary">El cambio se aplica en la próxima admisión o escritura; no cancela retroactivamente una ejecución activa. La cuota usa un margen para escrituras y metadatos. El servidor decide si hay capacidad suficiente; no se aumenta sola.</p>
        {view.quota.writable ? <form onSubmit={(event) => { void save(event); }} noValidate className="mt-6 max-w-xl">
          <label htmlFor="quota-bytes" className="field-label">Límite lógico en bytes</label>
          <input ref={inputRef} id="quota-bytes" type="text" inputMode="numeric" autoComplete="off" spellCheck={false} value={draft ?? ""} disabled={saving} aria-invalid={!!fieldError} aria-describedby={fieldError ? "quota-help quota-error" : "quota-help"} onChange={(event) => { setDraft(event.target.value); setFieldError(""); setSaveError(""); setSaved(false); }} className="control font-mono tabular-nums" />
          <p id="quota-help" className="field-help">Ingresá un entero decimal ASCII positivo en bytes (1 a 9,223,372,036,854,775,807), sin separadores, espacios ni ceros iniciales. 1 GiB = 1,073,741,824 bytes; 5 GiB = 5,368,709,120 bytes.</p>
          {fieldError && <p id="quota-error" className="mt-2 text-sm text-red-300">{fieldError}</p>}
          {saveError && <p role="alert" className="mt-2 text-sm text-red-300">{saveError}</p>}
          {saved && <p role="status" className="mt-2 text-sm text-accent">Guardado. El presupuesto efectivo se actualizó con la respuesta del servidor.</p>}
          <button type="submit" className="btn btn-primary mt-4 disabled:opacity-50" disabled={saving}>{saving ? "Guardando…" : "Guardar presupuesto"}</button>
        </form> : <div className="mt-6 max-w-prose text-text-secondary"><p>La cuota está fijada por LABORATORIO_QUOTA_BYTES en el entorno del proceso. Esta pantalla es de solo lectura mientras esa variable tenga prioridad; cambiar la preferencia guardada aquí no tendría efecto.</p>{dirty && <p className="mt-2 break-words">Borrador no guardado: <span className="font-mono">{draft}</span> bytes. Copialo antes de salir si lo necesitás; no se envió al servidor.</p>}</div>}
      </section>
      <section aria-labelledby="physical-heading" className="border-t border-border pt-5">
        <h2 id="physical-heading" className="section-header">Archivos físicos y disco</h2>
        <p className="mb-4 max-w-prose text-sm text-text-secondary">Estos tamaños son distintos del uso lógico. El disco libre corresponde al volumen de la base, no a espacio recuperable al borrar registros. Borrar registros no garantiza reducir inmediatamente el archivo SQLite. Los JSON y rankings originales no se incluyen.</p>
        <dl className="metric-grid">
          <div className={metric}><dt>SQLite y archivos locales (total informado)</dt><dd className="break-words font-mono">{measured(view.storage.sqlite_bytes)}</dd></div>
          <div className={metric}><dt>Espacio en disco libre</dt><dd className="break-words font-mono">{measured(view.storage.free_disk_bytes)}</dd></div>
          <div className={metric}><dt>Base SQLite</dt><dd className="break-words font-mono">{measured(view.storage.database_bytes)}</dd></div>
          <div className={metric}><dt>WAL</dt><dd className="break-words font-mono">{measured(view.storage.wal_bytes)}</dd></div>
          <div className={metric}><dt>SHM</dt><dd className="break-words font-mono">{measured(view.storage.shm_bytes)}</dd></div>
          <div className={metric}><dt>Temporales locales</dt><dd className="break-words font-mono">{measured(view.storage.temp_bytes)}</dd></div>
        </dl>
        <p className="mt-3 max-w-prose text-sm text-text-secondary">El total físico informado incluye los archivos locales conocidos; no mide temporales de SQLite administrados por el sistema operativo. No se estima espacio recuperable ni se compacta la base desde esta pantalla.</p>
      </section>
      <section aria-labelledby="sources-heading" className="border-t border-border pt-5">
        <h2 id="sources-heading" className="section-header">Datos de origen</h2>
        <p className="max-w-prose text-sm text-text-secondary">Fuentes congeladas de solo lectura. La API no informa un período de cobertura; no se infiere a partir de los nombres. No se pueden importar datos ni agregar juegos aquí.</p>
        <details className="mt-4 border-y border-border py-3"><summary className="cursor-pointer text-sm text-accent">Ver identificadores, huellas y versión</summary>
          <dl className="mt-4 space-y-3 text-sm">
            <div><dt className="text-text-secondary">Historial · identificador</dt><dd className="break-all font-mono">{view.sources.history_id}</dd></div>
            <div><dt className="text-text-secondary">Historial · SHA-256</dt><dd className="break-all font-mono">{view.sources.history_sha256}</dd></div>
            <div><dt className="text-text-secondary">Rankings · identificador</dt><dd className="break-all font-mono">{view.sources.rankings_id}</dd></div>
            <div><dt className="text-text-secondary">Rankings · SHA-256</dt><dd className="break-all font-mono">{view.sources.rankings_sha256}</dd></div>
            <div><dt className="text-text-secondary">Versión de código</dt><dd className="break-all font-mono">{view.sources.code_version}</dd></div>
          </dl>
        </details>
      </section>
      <section aria-labelledby="connection-heading" className="border-t border-border pt-5">
        <h2 id="connection-heading" className="section-header">Conexión local</h2>
        <p className="text-sm">Respuesta del servidor local: <span className="font-mono">{view.connection.host}:{view.connection.port}</span> · versión <span className="font-mono">{view.connection.version}</span>.</p>
        <p className="mt-3 max-w-prose text-sm text-text-secondary">Para detener la aplicación, cerrá el proceso del servidor con el que la iniciaste. El lanzador de Windows está pendiente (LW16); todavía no hay un control de detención desde esta web. Cerrar el navegador no detiene la cola.</p>
      </section>
    </>}
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás los cambios del presupuesto que aún no guardaste." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onCancel={() => blocker.reset?.()} onConfirm={() => blocker.proceed?.()} />
  </div>;
}
