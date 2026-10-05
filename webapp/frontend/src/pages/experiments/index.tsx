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
import { Button, Disclosure, ErrorBanner, Field, Figure, Loading, Stat } from "../../components/ui";
import type { ChipVariant, FigureVariant } from "../../components/ui";
import { formatDOP } from "../../lib/format";
import { profileMoney } from "../../lib/profile-display";

const PAGE_SIZE = 20;
const statuses: ExperimentStatus[] = ["pending", "held", "running", "completed", "cancelled", "interrupted", "failed"];
const statusNames: Record<ExperimentStatus, string> = { pending: "Pendiente", held: "Retenido", running: "En curso", completed: "Ejecución completada", cancelled: "Cancelado", interrupted: "Interrumpido", failed: "Error" };
const sortNames: Record<Sort, string> = { created_at: "Fecha de creación", name: "Nombre", status: "Estado" };
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

interface StatusChipData { label: string; variant: ChipVariant; kind: "execution" | "outcome"; value: string }
const EXECUTION_CHIPS: Record<ExperimentStatus, StatusChipData> = {
  pending: { label: "Pendiente", variant: "neutral", kind: "execution", value: "pending" },
  held: { label: "Retenido", variant: "warning", kind: "execution", value: "held" },
  running: { label: "En curso", variant: "info", kind: "execution", value: "running" },
  completed: { label: "Ejecución completada", variant: "neutral", kind: "execution", value: "completed" },
  cancelled: { label: "Cancelado", variant: "warning", kind: "execution", value: "cancelled" },
  interrupted: { label: "Interrumpido", variant: "warning", kind: "execution", value: "interrupted" },
  failed: { label: "Con error", variant: "danger", kind: "execution", value: "failed" },
};

/**
 * A completed simulation only claims a financial outcome when every run
 * closed with the same one; mixed or unknown results stay a plain execution state.
 */
function statusChip(row: ExperimentSummary): StatusChipData {
  if (row.status === "completed") {
    const outcomes = row.runs.map((run) => run.result?.outcome);
    if (outcomes.length > 0 && outcomes.every((outcome) => outcome === "goal")) return { label: "Meta alcanzada", variant: "success", kind: "outcome", value: "goal" };
    if (outcomes.length > 0 && outcomes.every((outcome) => outcome === "ruin")) return { label: "Se agotó el capital", variant: "danger", kind: "outcome", value: "ruin" };
  }
  return EXECUTION_CHIPS[row.status];
}

function StatusChip({ row }: { row: ExperimentSummary }) {
  const chip = statusChip(row);
  return <span className={`ledger-chip ledger-chip-${chip.variant}`} data-status-kind={chip.kind} data-status-value={chip.value}>{chip.label}</span>;
}

/** Net result of a single completed run; multi-run comparisons have no single figure to show. */
function netResult(row: ExperimentSummary): { text: string; variant: FigureVariant } | null {
  if (row.runs.length !== 1) return null;
  const result = row.runs[0].result;
  if (!result) return null;
  const delta = result.delta;
  const money = isProfileExperiment(row) ? profileMoney(row, Math.abs(delta)) : formatDOP(Math.abs(delta));
  if (delta === 0) return { text: money, variant: "neutral" };
  return { text: `${delta > 0 ? "+" : "−"}${money}`, variant: delta > 0 ? "positive" : "negative" };
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
    <button ref={trigger} type="button" className="ledger-button ledger-button-ghost" aria-label={`Acciones de ${experimentName(row)}`} aria-expanded={open} aria-controls={`actions-${row.id}`} onClick={() => {
      if (!open) { const rect = trigger.current!.getBoundingClientRect(); setPosition({ top: Math.min(rect.bottom, window.innerHeight - 100), left: Math.max(0, rect.right - 180) }); }
      setOpen(!open);
    }}>Acciones</button>
    {open && createPortal(<div id={`actions-${row.id}`} role="menu" aria-label={`Acciones de ${experimentName(row)}`} style={{ position: "fixed", zIndex: 50, ...position }} className="min-w-[180px] border border-border-control bg-surface p-1 text-sm">
      {!isProfileExperiment(row) && <Link ref={first} role="menuitem" className="ledger-button ledger-button-ghost w-full justify-start" to={`/experimentos/nuevo?base=${encodeURIComponent(row.id)}`} onClick={() => setOpen(false)}>Usar como base</Link>}
      {isProfileExperiment(row) && <span className="block px-3 py-2 text-text-secondary">No disponible como base</span>}
      <button ref={firstProfile} role="menuitem" type="button" className="ledger-button ledger-button-ghost w-full justify-start" onClick={() => { trigger.current?.focus(); setOpen(false); onDelete(); }}>Eliminar</button>
    </div>, document.body)}
  </>;
}

export function ExperimentsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = parseQuery(searchParams);
  const [text, setText] = useState(query.name);
  const [items, setItems] = useState<ExperimentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [mobileLayout, setMobileLayout] = useState(() => window.innerWidth < 900);
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

  useEffect(() => {
    const updateLayout = () => setMobileLayout(window.innerWidth < 900);
    window.addEventListener("resize", updateLayout);
    return () => window.removeEventListener("resize", updateLayout);
  }, []);

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
      if (error instanceof ApiError && error.status === 409) setRowError("No se puede eliminar una simulación activa o en cola.");
      else if (error instanceof ApiError && error.status === 404) {
        setDeleteTarget(null);
        await load(queryRef.current, (queryRef.current.page - 1) * PAGE_SIZE);
        setRowError("Esa simulación ya no existía; el listado se actualizó.");
      } else if (error instanceof NetworkError) setRowError("Sin respuesta del servidor. Puede que no se haya eliminado.");
      else setRowError("No se pudo eliminar la simulación. Probá de nuevo.");
    } finally { setDeleting(false); }
  }

  function sortable(sort: Sort, header: string): DataTableColumn<ExperimentSummary> {
    return { key: sort, header, headerClassName: `table-${sort === "created_at" ? "date" : sort}`, cellClassName: `table-${sort === "created_at" ? "date" : sort}`,
      sort: query.sort === sort ? query.order === "asc" ? "ascending" : "descending" : "none",
      onSort: () => update({ sort, order: query.sort === sort && query.order === "asc" ? "desc" : "asc", page: 1 }),
      render: (row) => sort === "name" ? <><span className="table-name-text font-semibold">{isProfileExperiment(row) ? row.display.name : row.request.name}</span>{isProfileExperiment(row) && <span className="block text-sm text-text-secondary">Perfil {row.profile.profile_id} · {row.profile.positions} posiciones · Capital {profileMoney(row, row.display.capital)} · Meta {profileMoney(row, row.display.goal)} · {row.display.staking_label}</span>}</>
        : sort === "status" ? <StatusChip row={row} /> : <span title={row.created_at ?? "Fecha no registrada"}>{createdAt(row.created_at)}</span> };
  }
  const columns: DataTableColumn<ExperimentSummary>[] = [
    sortable("name", "Nombre"),
    { key: "count", header: "Corridas", headerClassName: "table-numeric", cellClassName: "table-numeric", render: (row) => row.runs.length },
    sortable("created_at", "Creado"),
    sortable("status", "Estado"),
    { key: "net", header: "Resultado neto", headerClassName: "table-numeric", cellClassName: "table-numeric", render: (row) => { const net = netResult(row); return net ? <Figure value={net.text} variant={net.variant} /> : "—"; } },
    { key: "actions", header: "Acciones", headerClassName: "table-actions", cellClassName: "table-actions", render: (row) => <div className="flex items-center gap-2"><Link to={`/experimentos/${encodeURIComponent(row.id)}`} className="ledger-button ledger-button-primary" aria-label={`Abrir resultado de ${experimentName(row)}`}>Abrir resultado</Link><RowActions row={row} onDelete={() => { setRowError(""); setDeleteTarget(row); }} /></div> },
  ];
  const hasFilters = !!(query.name || query.status);
  const goalCount = items.filter((item) => statusChip(item).value === "goal").length;
  const runningCount = items.filter((item) => item.status === "running").length;
  const activeQueueItem = items.find((item) => item.id === queue?.active_id);
  const shown = `de las ${items.length} mostradas`;
  const clearFilters = () => update({ name: "", status: undefined, page: 1 });
  return <div>
    <header className="mb-6 flex flex-wrap items-end justify-between gap-6 border-b border-border pb-5">
      {state === "ready" && total > 0 ? <div className="grid grid-cols-3 gap-6" aria-label="Resumen de simulaciones" role="group">
        <Stat label="Simulaciones" value={total} />
        <Stat label="Con meta alcanzada" value={goalCount} variant={goalCount > 0 ? "positive" : "neutral"} delta={shown} />
        <Stat label="En curso" value={runningCount} delta={shown} />
      </div> : <span />}
    </header>
    {queue?.active_id && <p className="mb-4 text-sm text-text-secondary">En curso{queueError ? " (puede haber cambiado)" : ""}: {activeQueueItem ? <strong>{experimentName(activeQueueItem)}</strong> : <Link className="link" to={`/experimentos/${encodeURIComponent(queue.active_id)}`}>{queue.active_id}</Link>}</p>}
    {notice && <p ref={noticeRef} tabIndex={-1} role="status" className="mb-4 border border-border-control p-3 text-sm text-accent focus:outline-none">{notice}</p>}
    {rowError && <p role="alert" className="mb-4 border border-border-control p-3 text-sm text-text">{rowError}</p>}
    {(total > 0 || hasFilters) && <div className="mb-5" role="group" aria-label="Filtros de simulaciones">
      <div className="flex flex-wrap items-end gap-4">
        <Field id="experiment-name" label="Buscar por nombre" type="search" maxLength={80} className="min-w-[220px] flex-1 sm:max-w-sm" value={text} onChange={(event) => setText(event.target.value)} />
        <div className="ledger-field min-w-[180px]"><label htmlFor="experiment-status" className="ledger-label">Estado</label><select id="experiment-status" className="ledger-control" value={query.status ?? ""} onChange={(event) => update({ status: statuses.find((value) => value === event.target.value), page: 1 })}><option value="">Todos</option>{statuses.map((status) => <option key={status} value={status}>{statusNames[status]}</option>)}</select></div>
        {hasFilters && total > 0 && <Button variant="ghost" onClick={clearFilters}>Limpiar filtros</Button>}
      </div>
      <Disclosure summary="Filtros" defaultOpen={query.sort !== "created_at" || query.order !== "desc"}>
        <div className="flex flex-wrap items-end gap-4 pb-2">
          <div className="ledger-field min-w-[180px]"><label htmlFor="experiment-sort" className="ledger-label">Ordenar por</label><select id="experiment-sort" className="ledger-control" value={query.sort} onChange={(event) => update({ sort: event.target.value as Sort, page: 1 })}>{(Object.keys(sortNames) as Sort[]).map((sort) => <option key={sort} value={sort}>{sortNames[sort]}</option>)}</select></div>
          <div className="ledger-field min-w-[180px]"><label htmlFor="experiment-order" className="ledger-label">Sentido</label><select id="experiment-order" className="ledger-control" value={query.order} onChange={(event) => update({ order: event.target.value === "asc" ? "asc" : "desc", page: 1 })}><option value="desc">Descendente</option><option value="asc">Ascendente</option></select></div>
        </div>
      </Disclosure>
    </div>}
    <p className="mb-4 text-sm text-text-secondary">Las simulaciones usan datos históricos: no predicen resultados futuros ni garantizan rentabilidad.</p>
    {state === "loading" && <Loading rows={6} label="Cargando simulaciones…" />}
    {state === "network-error" && <ErrorBanner cause="No se pudo contactar al servidor." recovery="Iniciá el laboratorio desde el lanzador y después reintentá." preserved actionLabel="Reintentar" onAction={() => load(query, offset)} />}
    {state === "server-error" && <ErrorBanner cause="No se pudo cargar el listado de simulaciones." recovery="El servidor respondió con un error. Reintentá en unos segundos; si persiste, reiniciá el laboratorio desde el lanzador." preserved actionLabel="Reintentar" onAction={() => load(query, offset)} />}
    {state === "ready" && total === 0 && (hasFilters
      ? <section className="ledger-empty" aria-labelledby="empty-title"><h2 id="empty-title">Sin coincidencias</h2><p>Ninguna simulación cumple la búsqueda o el estado elegidos.</p><Button className="mt-3" onClick={clearFilters}>Limpiar filtros</Button></section>
      : <section className="ledger-empty" aria-labelledby="empty-title"><h2 id="empty-title">Todavía no hay simulaciones</h2><p>Las simulaciones muestran cómo se comportan tus estrategias con datos históricos.</p></section>)}
    {state === "ready" && total > 0 && <>
      {mobileLayout ? <ul className="experiment-card-list" aria-label="Resultados de simulaciones">
        {items.map((row) => {
          const result = netResult(row);
          const name = experimentName(row);
          const strategy = isProfileBatchExperiment(row)
            ? `${row.runs.length} estrategias`
            : isProfileExperiment(row) ? row.display.staking_label
              : row.request.strategies.length === 1 ? "Estrategia guardada" : `${row.request.strategies.length} estrategias`;
          return <li key={row.id} className="experiment-card">
            <div className="experiment-card-heading">
              <span className="experiment-card-title">{name}</span>
              <StatusChip row={row} />
            </div>
            <p className="experiment-card-meta">{createdAt(row.created_at)} · {strategy}</p>
            <p className="experiment-card-outcome">
              <span>{row.runs.length === 1 && row.runs[0].result ? "Cambio respecto del inicio" : "Resultado financiero"}</span>
              {result ? <Figure value={result.text} variant={result.variant} /> : <strong>{row.runs.length === 1 ? "Sin resultado guardado" : "Varias ejecuciones · abrí para revisar"}</strong>}
            </p>
            <div className="experiment-card-actions">
              <Link to={`/experimentos/${encodeURIComponent(row.id)}`} className="btn btn-secondary" aria-label={`Abrir resultado de ${name}`}>Abrir resultado</Link>
              <RowActions row={row} onDelete={() => { setRowError(""); setDeleteTarget(row); }} />
            </div>
          </li>;
        })}
      </ul> : <div className="experiment-wide-table"><DataTable caption="Simulaciones" columns={columns} rows={items} getRowKey={(row) => row.id} /></div>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-text-secondary">Mostrando {offset + 1}–{offset + items.length} de {total}</p>
        <div className="flex gap-3"><Button disabled={offset === 0} onClick={() => update({ page: query.page - 1 })}>Anterior</Button><Button disabled={offset + PAGE_SIZE >= total} onClick={() => update({ page: query.page + 1 })}>Siguiente</Button></div>
      </div>
    </>}
    <ConfirmDialog open={!!deleteTarget} title={deleteTarget ? `¿Eliminar la simulación «${experimentName(deleteTarget)}»?` : "¿Eliminar simulación?"} description={deleteTarget ? "Se elimina de forma permanente." : ""} confirmLabel={deleting ? "Eliminando…" : "Eliminar simulación"} onConfirm={confirmDelete} onCancel={() => { setDeleteTarget(null); setRowError(""); }} />
  </div>;
}
