import { useEffect, useRef, useState } from "react";
import { Link, useBlocker } from "react-router-dom";
import { ApiError, apiClient, NetworkError } from "../../api/client";
import type { Catalog, ConfigurationSummary, Page } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { StrategyEditor } from "../../components/StrategyEditor";
import { buildStrategy, diffStrategyKey, draftFromStrategy, errorDetail, errorMessage, newStrategy, trimName, validateStrategies } from "../new-experiment/model";
import type { Errors, StrategyDraft } from "../new-experiment/model";

const control = "h-control w-full rounded-control border border-border-control bg-field px-3 font-mono text-sm text-text";
const action = "min-h-control rounded-control border border-border-control px-4 font-mono text-sm hover:bg-field disabled:opacity-50";
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
    mapped[key] = { message: key === "libraryName" ? "El servidor rechazó el nombre de la biblioteca." : key === "form" ? "El servidor rechazó la solicitud." : "El servidor rechazó este valor de la configuración.", detail: entry.msg };
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
      if (live) setCatalogError(error instanceof NetworkError ? "No se pudo contactar al servidor local para cargar el catálogo." : "No se pudo cargar el catálogo.");
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
      if (live) setListError(error instanceof NetworkError ? "No se pudo contactar al servidor local. Reintentá cargar la biblioteca." : "No se pudo cargar el listado de configuraciones.");
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
    if (editor?.dirty && !window.confirm("¿Descartar los cambios de la configuración?")) return false;
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
        setMessage(error instanceof ApiError && error.status === 404 ? "La configuración ya no existe. Actualizá el listado." : error instanceof NetworkError ? "No se pudo contactar al servidor local para editar la configuración." : "No se pudo cargar la configuración. Reintentá.");
        if (error instanceof ApiError && error.status === 404) setRetry((value) => value + 1);
      }
    } finally { if (request === editorRequest.current) setEditorLoading(false); }
  }
  async function save() {
    if (!editor || !catalog || saveRef.current) return;
    const found = validateStrategies([editor.strategy], catalog);
    if (!trimName(editor.name) || trimName(editor.name).length > 80) found.libraryName = "Ingresá un nombre de biblioteca de 1 a 80 caracteres.";
    setErrors(found); setMessage("");
    if (Object.keys(found).length) return;
    saveRef.current = true; setEditorLoading(true);
    try {
      const strategy = buildStrategy(editor.strategy, catalog);
      if (editor.id) await apiClient.updateConfiguration(editor.id, trimName(editor.name), strategy);
      else await apiClient.createConfiguration(trimName(editor.name), strategy);
      editorRequest.current += 1;
      setEditor(null); setSuccess(editor.id ? "Configuración actualizada." : "Configuración guardada.");
      setRetry((value) => value + 1);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const mapped = validationErrors(error); setErrors(mapped);
        setMessage("El servidor encontró errores. Revisá los campos señalados.");
      } else setMessage(error instanceof ApiError && error.status === 404 ? "La configuración ya no existe. Tus cambios siguen aquí." : error instanceof NetworkError ? "No se pudo contactar al servidor local. La solicitud podría haber llegado; comprobá el listado antes de reintentar." : "No se pudo guardar la configuración. Tus cambios siguen aquí.");
    } finally { saveRef.current = false; setEditorLoading(false); }
  }
  async function remove() {
    if (!deleting || deleteRef.current) return;
    deleteRef.current = true; setDeletingBusy(true);
    const target = deleting;
    try {
      await apiClient.deleteConfiguration(target.id, target.id);
      if (!mountedRef.current) return;
      setDeleting(null); setSuccess("Configuración eliminada. Los resultados históricos se conservan.");
      setDeleteFocus((value) => value + 1);
      setRetry((value) => value + 1);
    } catch (error) {
      if (!mountedRef.current) return;
      setDeleting(null);
      setMessage(error instanceof ApiError && error.status === 404 ? "La configuración ya no existe; se actualizó el listado." : error instanceof ApiError && error.status === 400 ? "La confirmación no coincidió; no se eliminó la configuración." : error instanceof NetworkError ? "No se pudo contactar al servidor local. Comprobá el listado antes de reintentar." : "No se pudo eliminar la configuración.");
      if (error instanceof ApiError && error.status === 404) setRetry((value) => value + 1);
    } finally { deleteRef.current = false; if (mountedRef.current) setDeletingBusy(false); }
  }
  const visible = page?.items.filter((item) => item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
  return <>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <p className="max-w-prose text-sm text-text-secondary">Guardá una estrategia para reutilizarla. El nombre de la biblioteca y el de la estrategia pueden ser distintos. Borrar una plantilla no elimina los resultados de experimentos anteriores.</p>
      <button type="button" className={action} onClick={create}>Nueva configuración</button>
    </div>
    {success && <p ref={successRef} tabIndex={-1} role="status" className="mb-4 text-sm text-accent focus:outline-none" onBlur={() => setSuccess("")}>{success}</p>}
    {message && <p role="alert" className="mb-4 text-sm text-red-300">{message}</p>}
    {catalogError && <p role="alert" className="mb-4 text-sm text-red-300">{catalogError} <button type="button" className="text-accent underline" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
    {editorLoading && !editor && <p role="status">Cargando configuración…</p>}
    {editor && <section aria-label="Editor de configuración" className="mb-8 max-w-2xl border-y border-border py-5">
      <h2 className="mb-4 text-xl">{editor.id ? "Editar configuración" : "Nueva configuración"}</h2>
      <fieldset disabled={editorLoading}>
      <label htmlFor="libraryName" className="mb-1 block font-mono text-sm">Nombre de la biblioteca</label>
      <input id="libraryName" className={control} value={editor.name} maxLength={81} aria-invalid={!!errors.libraryName} aria-describedby={errors.libraryName ? "libraryName-error" : undefined} onChange={(event) => { setEditor({ ...editor, name: event.target.value, dirty: true }); setErrors((previous) => { const next = { ...previous }; delete next.libraryName; return next; }); setMessage(""); }} />
      {errors.libraryName && <p id="libraryName-error" className="mt-1 text-sm text-red-300">{errorMessage(errors.libraryName)} <span className="text-xs text-text-secondary">{errorDetail(errors.libraryName)}</span></p>}
      <div className="mt-5 border-t border-border pt-5">
        {errors["strategies.0"] && <p className="mb-3 text-sm text-red-300">{errorMessage(errors["strategies.0"])} <span className="text-xs text-text-secondary">{errorDetail(errors["strategies.0"])}</span></p>}
        {catalog && <StrategyEditor value={editor.strategy} index={0} catalog={catalog} errors={errors} onChange={(value) => {
          const changed = diffStrategyKey(editor.strategy, value);
          setEditor({ ...editor, strategy: value, dirty: true }); setMessage("");
          setErrors((previous) => { const next = { ...previous }; delete next["strategies.0"]; if (changed) { delete next[`strategies.0.${changed}`]; if (changed.startsWith("components")) { delete next["strategies.0.components"]; for (const key of Object.keys(next)) if (key.startsWith("strategies.0.components.")) delete next[key]; } } return next; });
        }} />}
      </div>
      </fieldset>
      <div className="flex flex-wrap gap-3"><button type="button" className={action} disabled={!catalog || editorLoading} onClick={save}>{editor.id ? "Guardar cambios" : "Guardar configuración"}</button><button type="button" className={action} disabled={editorLoading} onClick={() => { discard(); }}>Cancelar edición</button></div>
    </section>}
    <label htmlFor="configSearch" className="mb-1 block font-mono text-sm">Buscar por nombre en esta página</label>
    <input id="configSearch" className={`${control} mb-4 max-w-md`} value={search} onChange={(event) => setSearch(event.target.value)} />
    {!page && !listError && <p role="status">Cargando configuraciones…</p>}
    {listError && <p role="alert" className="text-red-300">{listError} <button type="button" className="text-accent underline" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
    {page && <>
      {page.total === 0 ? <p>Todavía no hay configuraciones guardadas. Creá la primera para reutilizar una estrategia.</p> : visible.length === 0 ? <p>Sin coincidencias en esta página. Probá otra página o cambiá la búsqueda.</p> : <ul className="divide-y divide-border border-y border-border">{visible.map((item) => <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div><strong className="block">{item.name}</strong><span className="text-sm text-text-secondary">Estrategia: {item.strategy.name} · {item.strategy.selector}</span></div>
        <div className="flex flex-wrap gap-3"><Link className={`${action} inline-flex items-center text-accent`} to={`/experimentos/nuevo?configuration=${encodeURIComponent(item.id)}`}>Usar {item.name}</Link><button type="button" className={action} onClick={() => { void edit(item.id); }}>Editar {item.name}</button><button type="button" className={action} disabled={deletingBusy} onClick={() => { setMessage(""); setDeleting(item); }}>Eliminar {item.name}</button></div>
      </li>)}</ul>}
      <nav aria-label="Páginas de configuraciones" className="mt-4 flex items-center gap-4 font-mono text-sm"><button type="button" className={action} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Anterior</button><span>Página {Math.floor(offset / pageSize) + 1} · {page.total} en total</span><button type="button" className={action} disabled={offset + pageSize >= page.total} onClick={() => setOffset(offset + pageSize)}>Siguiente</button></nav>
    </>}
    <ConfirmDialog open={!!deleting && !deletingBusy} title="¿Eliminar configuración?" description={`Eliminar ${deleting?.name ?? "esta configuración"} no elimina los resultados de experimentos anteriores. Esta acción no se puede deshacer.`} confirmLabel="Eliminar configuración" onCancel={() => setDeleting(null)} onConfirm={() => { void remove(); }} />
    <ConfirmDialog open={blocker.state === "blocked"} title="¿Salir sin guardar?" description="Perderás los cambios de la configuración." confirmLabel="Salir sin guardar" cancelLabel="Seguir editando" onCancel={() => blocker.reset?.()} onConfirm={() => blocker.proceed?.()} />
  </>;
}
