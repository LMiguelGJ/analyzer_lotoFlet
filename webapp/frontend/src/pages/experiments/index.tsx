import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useSearchParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { ExperimentListParams } from "../../api/client";
import { isProfileBatchExperiment, isProfileExperiment } from "../../api/types";
import type { ExperimentStatus, ExperimentSummary } from "../../api/types";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { useQueue } from "../../components/QueueProvider";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { profileMoney } from "../../lib/profile-display";

const PAGE_SIZE = 20;
const secondary = "btn btn-secondary disabled:opacity-50";
const statuses: ExperimentStatus[] = ["pending", "held", "running", "completed", "cancelled", "interrupted", "failed"];
const statusNames: Record<ExperimentStatus, string> = { pending: "Pendiente", held: "Retenido", running: "En curso", completed: "Ejecución completada", cancelled: "Cancelado", interrupted: "Interrumpido", failed: "Error" };
type Sort = "created_at" | "name" | "status";
type Order = "asc" | "desc";
type ListState = "loading" | "network-error" | "server-error" | "ready";

function parseQuery(params: URLSearchParams) {
  const name = (params.get("name") ?? "").slice(0, 80);
  const rawStatus = params.get("status");
  const status = statuses.find((value) => value === rawStatus);
  const rawSort = params.get("sort");
  const sort: Sort = rawSort === "name" || rawSort === "status" ? rawSort : "created_at";
  const order: Order = params.get("order") === "asc" ? "asc" : "desc";
  const rawPage = params.get("page") ?? "1";
  const page = /^[1-9]\d{0,6}$/.test(rawPage) ? Number(rawPage) : 1;
  return { name, status, sort, order, page };
}
type Query = ReturnType<typeof parseQuery>;
function queryParams(query: Query) {
  const params = new URLSearchParams();
  if (query.name) params.set("name", query.name);
  if (query.status) params.set("status", query.status);
  if (query.sort !== "created_at") params.set("sort", query.sort);
  if (query.order !== "desc") params.set("order", query.order);
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}
function experimentName(row: ExperimentSummary): string {
  return isProfileBatchExperiment(row) ? row.display.name : row.request.name;
}

function createdAt(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-DO", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(date);
}

function RowActions({ row, onDelete }: { row: ExperimentSummary; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const trigger = useRef<HTMLButtonElement>(null);
  const first = useRef<HTMLAnchorElement>(null);
  const firstProfile = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    (isProfileExperiment(row) ? firstProfile.current : first.current)?.focus();
    function dismiss(event: KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    }
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !trigger.current?.contains(event.target) && !document.getElementById(`actions-${row.id}`)?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("keydown", dismiss);
    document.addEventListener("pointerdown", outside);
    return () => { document.removeEventListener("keydown", dismiss); document.removeEventListener("pointerdown", outside); };
  }, [open, row.id]);
  return <>
    <button ref={trigger} type="button" className={secondary} aria-label={`Acciones de ${experimentName(row)}`} aria-expanded={open} aria-controls={`actions-${row.id}`} onClick={() => {
      if (!open) { const rect = trigger.current!.getBoundingClientRect(); setPosition({ top: Math.min(rect.bottom, window.innerHeight - 100), left: Math.max(0, rect.right - 180) }); }
      setOpen(!open);
    }}>Acciones</button>
    {open && createPortal(<div id={`actions-${row.id}`} role="menu" aria-label={`Acciones de ${experimentName(row)}`} style={{ position: "fixed", zIndex: 50, ...position }} className="min-w-[180px] border border-border-control bg-surface p-1 text-sm">
      {!isProfileExperiment(row) && <Link ref={first} role="menuitem" className="block px-3 py-2 text-accent hover:bg-field" to={`/experimentos/nuevo?base=${encodeURIComponent(row.id)}`} onClick={() => setOpen(false)}>Usar como base</Link>}
      {isProfileExperiment(row) && <span className="block px-3 py-2 text-text-secondary">Usar como base no disponible para perfiles</span>}
      <button ref={firstProfile} role="menuitem" type="button" className="block w-full px-3 py-2 text-left hover:bg-field" onClick={() => { trigger.current?.focus(); setOpen(false); onDelete(); }}>Eliminar</button>
    </div>, document.body)}
  </>;
}

export function ExperimentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = parseQuery(searchParams);
  const [text, setText] = useState(query.name);
  const [items, setItems] = useState<ExperimentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [state, setState] = useState<ListState>("loading");
  const { status: queue, error: queueError } = useQueue();
  const [deleteTarget, setDeleteTarget] = useState<ExperimentSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [rowError, setRowError] = useState("");
  const [notice, setNotice] = useState("");
  const noticeRef = useRef<HTMLParagraphElement>(null);
  const sequence = useRef(0);
  const alive = useRef(true);
  const queryRef = useRef(query);
  queryRef.current = query;
  const offset = (query.page - 1) * PAGE_SIZE;
  const key = searchParams.toString();

  const update = (changes: Partial<Query>) => {
    const next = { ...queryRef.current, ...changes };
    setSearchParams(queryParams(next));
  };
  useEffect(() => { setText(query.name); }, [query.name]);
  useEffect(() => {
    if (text === query.name) return;
    const timer = setTimeout(() => update({ name: text.slice(0, 80), page: 1 }), 300);
    return () => clearTimeout(timer);
  // The URL is the committed search; changing it cancels the pending debounce.
  }, [text, query.name]);

  const load = useCallback(async (criteria: Query, current: number) => {
    const ticket = ++sequence.current;
    setState("loading");
    const params: ExperimentListParams = { offset: current, limit: PAGE_SIZE, sort: criteria.sort, order: criteria.order };
    if (criteria.name) params.name_contains = criteria.name;
    if (criteria.status) params.status = criteria.status;
    try {
      const page = await apiClient.listExperiments(params);
      if (!alive.current || ticket !== sequence.current) return;
      if (page.items.length === 0 && current > 0) {
        const lastPage = Math.max(1, Math.ceil(page.total / PAGE_SIZE));
        setSearchParams(queryParams({ ...criteria, page: lastPage }), { replace: true });
        return;
      }
      setItems(page.items); setTotal(page.total); setState("ready");
    } catch (error) {
      if (!alive.current || ticket !== sequence.current) return;
      setState(error instanceof NetworkError ? "network-error" : "server-error");
    }
  }, [setSearchParams]);

  useEffect(() => {
    alive.current = true;
    const parsed = parseQuery(new URLSearchParams(key));
    const canonical = queryParams(parsed).toString();
    if (canonical !== key) setSearchParams(queryParams(parsed), { replace: true });
    else void load(parsed, (parsed.page - 1) * PAGE_SIZE);
    return () => { alive.current = false; ++sequence.current; };
  }, [key, load, setSearchParams]);

  useEffect(() => {
    if (!notice) return;
    noticeRef.current?.focus();
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  async function confirmDelete() {
    if (!deleteTarget || deleting) return;
    setDeleting(true); setRowError("");
    const target = deleteTarget;
    try {
      await apiClient.deleteExperiment(target.id, target.id);
      setDeleteTarget(null);
      await load(queryRef.current, (queryRef.current.page - 1) * PAGE_SIZE);
      setNotice(`Se eliminó "${experimentName(target)}".`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setRowError("No se puede eliminar un experimento activo o en cola.");
      else if (error instanceof ApiError && error.status === 404) {
        setDeleteTarget(null);
        await load(queryRef.current, (queryRef.current.page - 1) * PAGE_SIZE);
        setRowError("Ese experimento ya no existía; el listado se actualizó.");
      } else if (error instanceof NetworkError) setRowError("No se pudo contactar al servidor local. El experimento podría no haberse eliminado.");
      else setRowError("No se pudo eliminar el experimento. Probá de nuevo.");
    } finally { setDeleting(false); }
  }

  function sortable(sort: Sort, header: string): DataTableColumn<ExperimentSummary> {
    return { key: sort, header, headerClassName: `table-${sort === "created_at" ? "date" : sort}`, cellClassName: `table-${sort === "created_at" ? "date" : sort}`,
      sort: query.sort === sort ? query.order === "asc" ? "ascending" : "descending" : "none",
      onSort: () => update({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc", page: 1 }),
      render: (row) => sort === "name" ? <><Link to={`/experimentos/${encodeURIComponent(row.id)}`} className="text-accent underline">{isProfileExperiment(row) ? row.display.name : row.request.name}</Link>{isProfileExperiment(row) && <span className="block text-sm text-text-secondary">Perfil {row.profile.profile_id} · {row.profile.positions} posiciones · Capital {profileMoney(row, row.display.capital)} · Meta {profileMoney(row, row.display.goal)} · Perfil v{row.request.schema_version} · {row.display.staking_label}</span>}</>
        : sort === "status" ? <StatusLabel kind="execution" value={row.status} /> : <span title={row.created_at ?? "Fecha no registrada"}>{createdAt(row.created_at)}</span> };
  }
  const columns: DataTableColumn<ExperimentSummary>[] = [
    sortable("name", "Nombre"),
    { key: "count", header: "Corridas", headerClassName: "table-numeric", cellClassName: "table-numeric", render: (row) => row.runs.length },
    sortable("created_at", "Creado"),
    sortable("status", "Estado"),
    { key: "actions", header: "Acciones", headerClassName: "table-actions", cellClassName: "table-actions", render: (row) => <RowActions row={row} onDelete={() => { setRowError(""); setDeleteTarget(row); }} /> },
  ];
  const hasFilters = !!(query.name || query.status);
  return <div>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <p className="max-w-prose text-text-secondary">Simulaciones sobre datos congelados del conjunto seleccionado.</p>
      <Link to="/experimentos/nuevo" className="btn btn-primary">Nuevo experimento</Link>
    </div>
    {queue?.active_id && <p className="mb-4 text-sm text-text-secondary">Activo en la última consulta{queueError ? " (estado no actualizado; puede haber cambiado)" : ""}: <Link className="text-accent underline" to={`/experimentos/${encodeURIComponent(queue.active_id)}`}>{items.find((item) => item.id === queue.active_id) ? experimentName(items.find((item) => item.id === queue.active_id)!) : queue.active_id}</Link></p>}
    {notice && <p ref={noticeRef} tabIndex={-1} role="status" className="mb-4 border border-border-control p-3 text-sm text-accent focus:outline-none">{notice}</p>}
    {rowError && <p role="alert" className="mb-4 border border-border-control p-3 text-sm text-text">{rowError}</p>}
    <div className="mb-5 flex flex-wrap items-end gap-4" role="group" aria-label="Filtros de experimentos">
      <div className="min-w-[220px] flex-1 sm:max-w-sm"><label htmlFor="experiment-name" className="field-label">Buscar por nombre</label><input id="experiment-name" type="search" maxLength={80} className="control" value={text} onChange={(event) => setText(event.target.value)} /></div>
      <div className="min-w-[180px]"><label htmlFor="experiment-status" className="field-label">Estado de ejecución</label><select id="experiment-status" className="control" value={query.status ?? ""} onChange={(event) => update({ status: statuses.find((value) => value === event.target.value), page: 1 })}><option value="">Todos</option>{statuses.map((status) => <option key={status} value={status}>{statusNames[status]}</option>)}</select></div>
    </div>
    {state === "loading" && <p role="status" className="text-text-secondary">Cargando experimentos…</p>}
    {state === "network-error" && <p role="alert">No se pudo contactar al servidor local. <button type="button" className="text-accent underline" onClick={() => load(query, offset)}>Reintentar</button></p>}
    {state === "server-error" && <p role="alert">No se pudo cargar el listado de experimentos. <button type="button" className="text-accent underline" onClick={() => load(query, offset)}>Reintentar</button></p>}
    {state === "ready" && total === 0 && (hasFilters ? <p role="status">Sin coincidencias para los filtros actuales. Cambiá el nombre o el estado para buscar de nuevo.</p> : <p role="status">Todavía no hay experimentos. <Link to="/experimentos/nuevo" className="text-accent underline">Creá el primero</Link>.</p>)}
    {state === "ready" && total > 0 && <>
      <DataTable caption="Experimentos" columns={columns} rows={items} getRowKey={(row) => row.id} />
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-text-secondary">Mostrando {offset + 1}–{offset + items.length} de {total}</p>
        <div className="flex gap-3"><button type="button" className={secondary} disabled={offset === 0} onClick={() => update({ page: query.page - 1 })}>Anterior</button><button type="button" className={secondary} disabled={offset + PAGE_SIZE >= total} onClick={() => update({ page: query.page + 1 })}>Siguiente</button></div>
      </div>
    </>}
    <ConfirmDialog open={!!deleteTarget} title={deleteTarget ? `¿Eliminar el experimento «${experimentName(deleteTarget)}»?` : "¿Eliminar experimento?"} description={deleteTarget ? `Se eliminará «${experimentName(deleteTarget)}» de forma permanente. Esta acción no se puede deshacer.` : ""} confirmLabel={deleting ? "Eliminando…" : "Eliminar experimento"} onConfirm={confirmDelete} onCancel={() => { setDeleteTarget(null); setRowError(""); }} />
  </div>;
}
