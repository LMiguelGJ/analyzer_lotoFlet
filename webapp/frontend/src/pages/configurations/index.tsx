import { useEffect, useRef, useState } from "react";
import { Link, useBlocker } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { Catalog, ConfigurationSummary, Page } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StrategyEditor } from "../../components/StrategyEditor";
import { SELECTOR_LABELS, STAKING_LABELS } from "../../lib/ui-labels";
import { buildStrategy, diffStrategyKey, draftFromStrategy, errorDetail, errorMessage, newStrategy, trimName, validateStrategies } from "../new-experiment/model";
import type { Errors, StrategyDraft } from "../new-experiment/model";

const control = "control";
const action = "btn btn-secondary";
const pageSize = 20;
type Editor = { id: string | null; name: string; strategy: StrategyDraft; dirty: boolean };

function validationErrors(error: ApiError): Errors {
  const mapped: Errors = {};
  for (const entry of error.fieldErrors ?? []) {
    const loc = entry.loc.map(String);
    const body = loc.indexOf("body");
    const path = body < 0 ? loc : loc.slice(body + 1);
    const key = path[0] === "name" && path.length === 1 ? "libraryName"
      : path[0] === "strategy" ? path.length === 1 ? "strategies.0" : `strategies.0.${path.slice(1).join(".")}` : "form";
    mapped[key] = { message: key === "libraryName" ? "Nombre rechazado." : key === "form" ? "Solicitud rechazada." : "Valor rechazado; revisá este campo.", detail: entry.msg };
  }
  return mapped;
}

export function ConfigurationsPage() {
  const [page, setPage] = useState<Page<ConfigurationSummary> | null>(null);
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [listError, setListError] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [editorLoading, setEditorLoading] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState("");
  const [deleteFocus, setDeleteFocus] = useState(0);
  const [deleting, setDeleting] = useState<ConfigurationSummary | null>(null);
  const [deletingBusy, setDeletingBusy] = useState(false);
  const successRef = useRef<HTMLParagraphElement>(null);
  const mountedRef = useRef(true);
  const saveRef = useRef(false);
  const deleteRef = useRef(false);
  const editorRequest = useRef(0);
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    !!editor?.dirty && currentLocation.pathname !== nextLocation.pathname);

  useEffect(() => {
    let live = true;
    apiClient.getCatalog().then((value) => { if (live) { setCatalog(value); setCatalogError(""); } }).catch((error: unknown) => {
      if (live) setCatalogError(error instanceof NetworkError ? "No se pudo contactar al servidor para cargar el catálogo." : "No se pudo cargar el catálogo.");
    });
    return () => { live = false; };
  }, [retry]);
  useEffect(() => {
    let live = true;
    setPage(null); setListError("");
    apiClient.listConfigurations(offset, pageSize).then((value) => {
      if (!live) return;
      if (offset > 0 && value.items.length === 0 && value.total <= offset) { setOffset(Math.max(0, Math.ceil(value.total / pageSize) - 1) * pageSize); return; }
      setPage(value);
    }).catch((error: unknown) => {
      if (live) setListError(error instanceof NetworkError ? "No se pudo contactar al servidor. Reintentá." : "No se pudo cargar las estrategias guardadas.");
    });
    return () => { live = false; };
  }, [offset, retry]);
  useEffect(() => {
    if (!editor?.dirty) return;
    function beforeUnload(event: BeforeUnloadEvent) { event.preventDefault(); event.returnValue = ""; }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [editor?.dirty]);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);
  useEffect(() => {
    if (!success) return;
    const timer = window.setTimeout(() => {
      if (document.activeElement !== successRef.current) setSuccess("");
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [success, deleteFocus]);
  useEffect(() => {
    if (deleteFocus > 0) successRef.current?.focus();
  }, [deleteFocus]);

  function discard(): boolean {
    if (editor?.dirty && !window.confirm("¿Descartar los cambios de la estrategia guardada?")) return false;
    editorRequest.current += 1;
    setEditor(null); setErrors({}); setMessage("");
    return true;
  }
  function create() {
    if (!discard()) return;
    setEditor({ id: null, name: "", strategy: newStrategy(1), dirty: false });
  }
  async function edit(id: string) {
    if (!discard()) return;
    const request = ++editorRequest.current;
    setEditorLoading(true);
    try {
      const saved = await apiClient.getConfiguration(id);
      if (request !== editorRequest.current) return;
      setEditor({ id: saved.id, name: saved.name, strategy: draftFromStrategy(saved.strategy, 1), dirty: false });
    } catch (error) {
      if (request === editorRequest.current) {
        setMessage(error instanceof ApiError && error.status === 404 ? "La estrategia ya no existe. Actualizá la lista." : error instanceof NetworkError ? "No se pudo contactar al servidor." : "No se pudo cargar la estrategia. Reintentá.");
        if (error instanceof ApiError && error.status === 404) setRetry((value) => value + 1);
      }
    } finally { if (request === editorRequest.current) setEditorLoading(false); }
  }
  async function save() {
    if (!editor || !catalog || saveRef.current) return;
    const found = validateStrategies([editor.strategy], catalog);
    if (!trimName(editor.name) || trimName(editor.name).length > 80) found.libraryName = "Ingresá un nombre guardado de 1 a 80 caracteres.";
    setErrors(found); setMessage("");
    if (Object.keys(found).length) return;
    saveRef.current = true; setEditorLoading(true);
    try {
      const strategy = buildStrategy(editor.strategy, catalog);
      if (editor.id) await apiClient.updateConfiguration(editor.id, trimName(editor.name), strategy);
      else await apiClient.createConfiguration(trimName(editor.name), strategy);
      editorRequest.current += 1;
      setEditor(null); setSuccess(editor.id ? "Estrategia guardada actualizada." : "Estrategia guardada.");
      setRetry((value) => value + 1);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const mapped = validationErrors(error); setErrors(mapped);
        setMessage("Revisá los campos señalados.");
      } else setMessage(error instanceof ApiError && error.status === 404 ? "La estrategia ya no existe. Tus cambios siguen aquí." : error instanceof NetworkError ? "Sin respuesta del servidor. Puede que se haya guardado; revisá la lista antes de reintentar." : "No se pudo guardar la estrategia. Tus cambios siguen aquí.");
    } finally { saveRef.current = false; setEditorLoading(false); }
  }
  async function remove() {
    if (!deleting || deleteRef.current) return;
    deleteRef.current = true; setDeletingBusy(true);
    const target = deleting;
    try {
      await apiClient.deleteConfiguration(target.id, target.id);
      if (!mountedRef.current) return;
      setDeleting(null); setSuccess("Estrategia eliminada. Los resultados se conservan.");
      setDeleteFocus((value) => value + 1);
      setRetry((value) => value + 1);
    } catch (error) {
      if (!mountedRef.current) return;
      setDeleting(null);
      setMessage(error instanceof ApiError && error.status === 404 ? "La estrategia ya no existe; se actualizó la lista." : error instanceof ApiError && error.status === 400 ? "No se eliminó: la confirmación no coincidió." : error instanceof NetworkError ? "Sin respuesta del servidor. Revisá la lista antes de reintentar." : "No se pudo eliminar la estrategia.");
      if (error instanceof ApiError && error.status === 404) setRetry((value) => value + 1);
    } finally { deleteRef.current = false; if (mountedRef.current) setDeletingBusy(false); }
  }
  const visible = page?.items.filter((item) => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
  return <>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <p className="text-sm text-text-secondary">Guardá un método para reutilizarlo.</p>
      <button type="button" className="btn btn-primary" onClick={create}>{page?.total === 0 ? "Crear estrategia guardada" : "Nueva estrategia guardada"}</button>
    </div>
    {success && <p ref={successRef} tabIndex={-1} role="status" className="mb-4 text-sm text-accent focus:outline-none" onBlur={() => setSuccess("")}>{success}</p>}
    {message && <p role="alert" className="mb-4 text-sm text-red-300">{message}</p>}
    {catalogError && <p role="alert" className="mb-4 text-sm text-red-300">{catalogError} <button type="button" className="btn btn-tertiary" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
    {editorLoading && !editor && <p role="status">Cargando estrategia…</p>}
    {editor && <section aria-label="Editor de estrategia guardada" className="mb-8 max-w-2xl border-t border-border pt-5">
      <h2 className="section-header">{editor.id ? "Editar estrategia guardada" : "Nueva estrategia guardada"}</h2>
      <fieldset disabled={editorLoading}>
      <label htmlFor="libraryName" className="field-label">Nombre guardado</label>
      <input id="libraryName" className={control} value={editor.name} maxLength={81} aria-invalid={!!errors.libraryName} aria-describedby={errors.libraryName ? "libraryName-error" : undefined} onChange={(event) => { setEditor({ ...editor, name: event.target.value, dirty: true }); setErrors((previous) => { const next = { ...previous }; delete next.libraryName; return next; }); setMessage(""); }} />
      {errors.libraryName && <div id="libraryName-error" className="mt-1 text-sm text-red-300"><p>{errorMessage(errors.libraryName)}</p>{errorDetail(errors.libraryName) && <details className="mt-1 text-xs text-text-secondary"><summary className="disclosure-summary">Detalles técnicos</summary><p className="mt-1">{errorDetail(errors.libraryName)}</p></details>}</div>}
      <div className="mt-5 pt-5">
        {errors["strategies.0"] && <div className="mb-3 text-sm text-red-300"><p>{errorMessage(errors["strategies.0"])}</p>{errorDetail(errors["strategies.0"]) && <details className="mt-1 text-xs text-text-secondary"><summary className="disclosure-summary">Detalles técnicos</summary><p className="mt-1">{errorDetail(errors["strategies.0"])}</p></details>}</div>}
        {catalog && <StrategyEditor value={editor.strategy} index={0} catalog={catalog} errors={errors} onChange={(value) => {
          const changed = diffStrategyKey(editor.strategy, value);
          setEditor({ ...editor, strategy: value, dirty: true }); setMessage("");
          setErrors((previous) => { const next = { ...previous }; delete next["strategies.0"]; if (changed) { delete next[`strategies.0.${changed}`]; if (changed.startsWith("components")) { delete next["strategies.0.components"]; for (const key of Object.keys(next)) if (key.startsWith("strategies.0.components.")) delete next[key]; } } return next; });
        }} />}
      </div>
      </fieldset>
      <div className="flex flex-wrap gap-3"><button type="button" className="btn btn-primary" disabled={!catalog || editorLoading} onClick={save}>{editor.id ? "Guardar cambios" : "Guardar estrategia"}</button><button type="button" className={action} disabled={editorLoading} onClick={() => { discard(); }}>Cancelar edición</button></div>
    </section>}
    {page && page.total > 0 && <>
      <label htmlFor="configSearch" className="field-label">Buscar estrategia guardada</label>
      <input id="configSearch" className={`${control} mb-4 max-w-md`} value={search} onChange={(event) => setSearch(event.target.value)} />
    </>}
    {!page && !listError && <p role="status">Cargando estrategias guardadas…</p>}
    {listError && <p role="alert" className="text-red-300">{listError} <button type="button" className="btn btn-tertiary" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
    {page && <>
      {page.total === 0 ? <p role="status">La biblioteca es opcional; guardá un método para reutilizarlo.</p> : visible.length === 0 ? <div className="flex flex-wrap items-center gap-3"><p role="status">Sin coincidencias en esta página.</p><button type="button" className="btn btn-tertiary" onClick={() => setSearch("")}>Limpiar búsqueda</button></div> : <ul className="divide-y divide-border border-t border-border">{visible.map((item) => <li key={item.id} className="saved-strategy-row border-b border-border py-4">
        <div className="min-w-0"><strong className="block break-words">{item.name}</strong><dl className="mt-2 data-list"><dt>Estrategia</dt><dd>{item.strategy.name}</dd><dt>Selección</dt><dd>{SELECTOR_LABELS[item.strategy.selector]}</dd><dt>Forma de ajustar la apuesta</dt><dd>{STAKING_LABELS[item.strategy.staking]}</dd></dl></div>
        <div className="flex flex-wrap gap-2"><Link className="btn btn-secondary" to={`/experimentos/nuevo?configuration=${encodeURIComponent(item.id)}`}>Usar {item.name}</Link><button type="button" className="btn btn-tertiary" onClick={() => { void edit(item.id); }}>Editar {item.name}</button><button type="button" className="btn btn-destructive" disabled={deletingBusy} onClick={() => { setMessage(""); setDeleting(item); }}>Eliminar {item.name}</button></div>
      </li>)}</ul>}
      {page.total > 0 && <nav aria-label="Páginas de estrategias guardadas" className="mt-4 flex flex-wrap items-center gap-3 text-sm"><button type="button" className={action} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Anterior</button><span>Página {Math.floor(offset / pageSize) + 1} · {page.total} en total</span><button type="button" className={action} disabled={offset + pageSize >= page.total} onClick={() => setOffset(offset + pageSize)}>Siguiente</button></nav>}
    </>}
    <ConfirmDialog open={!!deleting && !deletingBusy} title={deleting ? `¿Eliminar la estrategia guardada «${deleting.name}»?` : "¿Eliminar estrategia guardada?"} description={`Los resultados de experimentos anteriores se conservan. Esta acción no se puede deshacer.`} confirmLabel="Eliminar estrategia guardada" onCancel={() => setDeleting(null)} onConfirm={() => { void remove(); }} />
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás los cambios de la estrategia guardada que aún no guardaste." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onCancel={() => blocker.reset?.()} onConfirm={() => blocker.proceed?.()} />
  </>;
}
