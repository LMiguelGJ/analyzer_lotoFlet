import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, ExperimentSummary, Page, RunSummary } from "../../api/types";
import { BalanceChart } from "../../components/BalanceChart";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { formatDOP, formatTwoDigit } from "../../lib/format";
import { FIELD_HELP_DELTA, FIELD_LABEL_DELTA, HISTORICAL_CAVEAT, SELECTOR_LABELS, SETTLEMENT_LABELS, STAKING_LABELS } from "../../lib/ui-labels";
import { PAGE_SIZE, pageOffset, replayIndex } from "./replay";

const button = "btn btn-secondary hover:bg-field disabled:opacity-50";
const tabs = ["Resultado", "Apuestas", "Parámetros y datos"] as const;
type Tab = typeof tabs[number];
const numberList = (values: number[]) => values.map(formatTwoDigit).join(", ");
function storedDate(label: string) {
  // Display the stored draw label verbatim, merely separating an ISO date/time.
  return label.replace("T", " ");
}
function detailError(error: unknown) {
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. Esto no indica que la ejecución se haya detenido.";
  if (error instanceof ApiError && error.status === 404) return "Este experimento no existe o fue eliminado.";
  return "No se pudo consultar el experimento. Probá de nuevo.";
}
function replayError(error: unknown) {
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local. La reproducción guardada no cambió.";
  if (error instanceof ApiError && error.status === 409) return "La reproducción todavía no está disponible para esta ejecución.";
  if (error instanceof ApiError && error.status === 404) return "La ejecución o el experimento ya no existe.";
  return "No se pudo cargar esta página de apuestas. Probá de nuevo.";
}

function BetDetails({ bet }: { bet: Bet }) {
  const [open, setOpen] = useState(false);
  return <div>
    <button type="button" className="text-accent underline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Ocultar detalle" : "Detalle"}</button>
    {open && <dl className="data-list mt-2 min-w-[220px]">
      <dt>Fecha y hora</dt><dd>{storedDate(bet.label)}</dd>
      <dt>Números elegidos</dt><dd>{numberList(bet.numbers)}</dd>
      <dt>Apuesta por número</dt><dd className="data-list-numeric">{formatDOP(bet.per_number)}</dd>
      <dt>Resultados (posiciones 1 a 5)</dt><dd>{numberList(bet.results)}</dd>
      <dt>Cobro</dt><dd className="data-list-numeric">{formatDOP(bet.paid)}</dd>
      <dt>Saldo resultante</dt><dd className="data-list-numeric">{formatDOP(bet.balance)}</dd>
    </dl>}
  </div>;
}

const columns: DataTableColumn<Bet>[] = [
  { key: "date", header: "Fecha y hora", render: (bet) => storedDate(bet.label) },
  { key: "numbers", header: "Números elegidos", render: (bet) => numberList(bet.numbers) },
  { key: "per", header: "Por número", render: (bet) => formatDOP(bet.per_number) },
  { key: "wagered", header: "Gasto total", render: (bet) => formatDOP(bet.wagered) },
  ...[0, 1, 2, 3, 4].map((position): DataTableColumn<Bet> => ({ key: `result-${position}`, header: `Resultado ${position + 1}`, render: (bet) => formatTwoDigit(bet.results[position]) })),
  { key: "paid", header: "Cobro", render: (bet) => formatDOP(bet.paid) },
  { key: "balance", header: "Saldo", render: (bet) => formatDOP(bet.balance) },
  { key: "detail", header: "Detalle", render: (bet) => <BetDetails bet={bet} /> },
];

function Parameters({ data, run }: { data: ExperimentSummary; run: RunSummary }) {
  const conditions = data.request.conditions;
  const strategy = data.request.strategies[run.ordinal];
  return <div className="space-y-6 text-sm">
    <dl className="data-list">
      <dt>Sorteo inicial</dt><dd>{storedDate(conditions.start_draw)}</dd>
      <dt>Capital</dt><dd className="data-list-numeric">{formatDOP(conditions.capital)}</dd>
      <dt>Meta</dt><dd className="data-list-numeric">{formatDOP(conditions.goal)}</dd>
      <dt>Límite de apuestas</dt><dd>{conditions.max_bets ?? "Sin límite"}</dd>
      <dt>Límite de minutos históricos</dt><dd>{conditions.max_minutes ?? "Sin límite"}</dd>
      <dt>Liquidación</dt><dd>{SETTLEMENT_LABELS[conditions.settlement]}</dd>
      <dt>Semilla guardada</dt><dd>{conditions.seed}</dd>
      <dt>Configuración asociada</dt><dd className={run.configuration_id ? "font-mono" : undefined}>{run.configuration_id ?? "Sin configuración asociada"}</dd>
      <dt>Estrategia</dt><dd>{strategy?.name ?? "No registrada"}</dd>
      {strategy && <><dt>Selector</dt><dd>{SELECTOR_LABELS[strategy.selector]}</dd><dt>Sistema</dt><dd>{strategy.system ?? "—"}</dd><dt>Cobertura</dt><dd>{strategy.coverage}</dd><dt>Apuesta</dt><dd>{STAKING_LABELS[strategy.staking]}</dd>
        {strategy.components && <><dt>Componentes guardados</dt><dd>{strategy.components.map((component) => `${component.system}: ${component.weight}`).join(", ")}</dd></>}</>}
    </dl>
    <div>
      <h3 className="section-header">Datos de origen</h3>
      <dl className="data-list break-all">
        <dt>Historial</dt><dd className="font-mono">{data.sources.history_id}</dd><dt>SHA-256 historial</dt><dd className="font-mono">{data.sources.history_sha256}</dd>
        <dt>Rankings</dt><dd className="font-mono">{data.sources.rankings_id}</dd><dt>SHA-256 rankings</dt><dd className="font-mono">{data.sources.rankings_sha256}</dd>
        <dt>Versión de código</dt><dd className="font-mono">{data.sources.code_version}</dd>
      </dl>
    </div>
    <p className="text-text-secondary">Resultados sobre datos históricos ya investigados: no constituyen una validación independiente de rentabilidad ni una probabilidad de éxito.</p>
  </div>;
}

function RunView({ data, run }: { data: ExperimentSummary; run: RunSummary }) {
  const [tab, setTab] = useState<Tab>("Resultado");
  const [cursor, setCursor] = useState(0);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page<Bet> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const cache = useRef(new Map<number, Page<Bet>>());
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const total = run.result?.bets_count ?? 0;

  useEffect(() => {
    if (!run.result) { setPage(null); setError(""); setLoading(false); return; }
    const cached = cache.current.get(offset);
    if (cached && retry === 0) { setPage(cached); setError(""); setLoading(false); return; }
    let live = true;
    setPage(null); setLoading(true); setError("");
    void apiClient.getReplay(data.id, run.ordinal, offset, PAGE_SIZE).then((result) => {
      if (!live) return;
      // Keep at most three bounded pages per mounted run; never eagerly download history.
      cache.current.delete(offset);
      cache.current.set(offset, result);
      if (cache.current.size > 3) cache.current.delete(cache.current.keys().next().value!);
      setPage(result); setLoading(false);
    }).catch((cause: unknown) => { if (live) { setError(replayError(cause)); setLoading(false); setPlaying(false); } });
    return () => { live = false; };
  }, [data.id, run.ordinal, !!run.result, offset, retry]);

  useEffect(() => {
    if (!playing || !run.result || !page || loading || error || cursor >= total - 1) {
      if (playing && cursor >= total - 1) setPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setCursor((current) => {
        const next = replayIndex(current, 1, total);
        setOffset(pageOffset(next));
        return next;
      });
    }, 1000 / speed);
    return () => clearTimeout(timer);
  }, [playing, !!run.result, page, loading, error, cursor, total, speed]);

  function move(step: number) {
    const next = replayIndex(cursor, step, total);
    setCursor(next); setOffset(pageOffset(next));
  }
  function selectTab(next: Tab) { setTab(next); setPlaying(false); }
  function onTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault(); selectTab(tabs[next]); tabRefs.current[next]?.focus();
  }
  const visiblePage = page?.offset === offset ? page : null;
  const current = visiblePage?.items[cursor - offset];
  return <section className="mt-6" aria-label={`Ejecución ${run.ordinal + 1}`}>
    <div className="flex flex-wrap items-center gap-4"><h2 className="font-heading text-2xl">{data.request.strategies[run.ordinal]?.name ?? `Ejecución ${run.ordinal + 1}`}</h2><StatusLabel kind="execution" value={run.status} /></div>
    <div role="tablist" aria-label="Secciones del detalle" className="mt-6 flex flex-wrap gap-2 border-b border-border">
      {tabs.map((name, index) => <button key={name} ref={(node) => { tabRefs.current[index] = node; }} type="button" role="tab" id={`detail-tab-${index}`} aria-controls={`detail-panel-${index}`} aria-selected={tab === name} tabIndex={tab === name ? 0 : -1} onClick={() => selectTab(name)} onKeyDown={(event) => onTabKey(event, index)} className={`min-h-control px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${tab === name ? "border-b-2 border-accent text-text" : "text-text-secondary hover:text-text"}`}>{name}</button>)}
    </div>
    <div role="tabpanel" id={`detail-panel-${tabs.indexOf(tab)}`} aria-labelledby={`detail-tab-${tabs.indexOf(tab)}`} tabIndex={0} className="pt-5">
      {tab === "Parámetros y datos" ? <Parameters data={data} run={run} /> : !run.result ? <p role="status">Esta ejecución no tiene un resultado completo guardado. No hay desenlace ni reproducción para mostrar.</p> : <>
        {tab === "Resultado" && <>
          <dl className="data-list border-b border-border pb-5">
            <dt>Saldo final</dt><dd className="data-list-numeric">{formatDOP(run.result.final_balance)}</dd>
            <dt>{FIELD_LABEL_DELTA}</dt><dd className="data-list-numeric" aria-describedby="detail-delta-help">{formatDOP(run.result.delta)}</dd>
            <dt>Apuestas realizadas</dt><dd className="data-list-numeric">{run.result.bets_count}</dd>
            <dt>Motivo de cierre</dt><dd><StatusLabel kind="outcome" value={run.result.outcome} /></dd>
          </dl>
          <p id="detail-delta-help" className="field-help mt-2">{FIELD_HELP_DELTA}</p>
          <p className="mt-3 text-sm text-text-secondary">{HISTORICAL_CAVEAT}</p>
          <BalanceChart points={(visiblePage?.items ?? []).map((bet, index) => ({ ordinal: offset + index + 1, balance: bet.balance }))} goal={data.request.conditions.goal} total={total} />
          <div className="border-t border-border pt-5" aria-label="Reproducción visual">
            <h3 className="section-header">Reproducción visual</h3>
            <p className="mb-3 text-sm text-text-secondary">El sorteo mostrado es una posición de lectura; no cambia el resultado final guardado.</p>
            <p aria-live="polite" className="mb-3 text-sm">Sorteo mostrado: {total ? `${cursor + 1} de ${total}` : "sin apuestas"}{current ? ` · ${storedDate(current.label)} · saldo en ese sorteo ${formatDOP(current.balance)}` : ""}</p>
            <div className="flex flex-wrap items-center gap-2">
              <button className={button} type="button" disabled={!total || cursor === 0} onClick={() => move(-1)}>Sorteo anterior</button>
              <button className={button} type="button" disabled={!total || cursor >= total - 1 || (typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches)} onClick={() => setPlaying(!playing)}>{playing ? "Pausar" : "Reproducir"}</button>
              <button className={button} type="button" disabled={!total || cursor >= total - 1} onClick={() => move(1)}>Siguiente sorteo</button>
              <label htmlFor="replay-speed" className="text-sm">Velocidad</label><select id="replay-speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} className="min-h-control rounded-control border border-border-control bg-field px-2 text-sm"><option value={0.5}>0,5×</option><option value={1}>1×</option><option value={2}>2×</option></select>
            </div>
            {typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches && <p className="mt-2 text-sm">Movimiento reducido: usá anterior y siguiente; reproducción automática desactivada.</p>}
          </div>
        </>}
        {tab === "Apuestas" && <>
          <p className="mb-3 text-sm text-text-secondary">Apuestas guardadas, página {Math.floor(offset / PAGE_SIZE) + 1}. Los resultados están ordenados por posición.</p>
          {visiblePage && visiblePage.items.length > 0 && <DataTable caption="Apuestas del experimento" columns={columns} rows={visiblePage.items} getRowKey={(bet) => bet.label} />}
          {visiblePage && visiblePage.items.length === 0 && <p role="status">No hay apuestas registradas en esta página.</p>}
          <div className="mt-4 flex flex-wrap items-center gap-3 text-sm"><span>Mostrando {total ? offset + 1 : 0}–{Math.min(offset + (visiblePage?.items.length ?? 0), total)} de {total}</span><button type="button" className={button} disabled={offset === 0} onClick={() => { const previous = Math.max(0, offset - PAGE_SIZE); setPlaying(false); setOffset(previous); setCursor(previous); }}>Página anterior</button><button type="button" className={button} disabled={offset + PAGE_SIZE >= total} onClick={() => { const next = offset + PAGE_SIZE; setPlaying(false); setOffset(next); setCursor(next); }}>Página siguiente</button></div>
        </>}
        {loading && <p role="status" className="mt-3">Cargando página de apuestas…</p>}
        {error && <p role="alert" className="mt-3">{error} <button type="button" className="text-accent underline" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
      </>}
    </div>
    {tabs.map((name, index) => name !== tab && <div key={name} role="tabpanel" id={`detail-panel-${index}`} aria-labelledby={`detail-tab-${index}`} hidden />)}
  </section>;
}

export function DetailPage() {
  const { id = "" } = useParams();
  const { search } = useLocation();
  const query = new URLSearchParams(search);
  const requestedRun = query.get("run");
  const fromComparison = query.get("from") === "comparison";
  const [snapshot, setSnapshot] = useState<ExperimentSummary | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [ordinal, setOrdinal] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    setSnapshot(null); setError(""); setOrdinal(null);
    async function load() {
      try {
        const next = await apiClient.getExperiment(id);
        if (!live) return;
        setSnapshot(next); setError("");
        if (["pending", "held", "running"].includes(next.status)) timer = setTimeout(load, 5000);
      } catch (cause) {
        if (!live) return;
        setError(detailError(cause));
        // A temporary network failure says nothing about the server's execution state.
        if (!(cause instanceof ApiError && cause.status === 404)) timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { live = false; clearTimeout(timer); };
  }, [id, retry]);
  const data = snapshot?.id === id ? snapshot : null;
  const target = requestedRun !== null && /^(0|[1-9]\d*)$/.test(requestedRun) ? Number(requestedRun) : null;
  const requested = data?.runs.find((run) => run.ordinal === target);
  const selected = data?.runs.find((run) => run.ordinal === ordinal) ?? requested ?? data?.runs[0];
  return <div>
    {!data && !error && <p role="status">Cargando experimento…</p>}
    {error && <p role="alert" className="mb-4">{error} <button type="button" className="text-accent underline" onClick={() => setRetry((value) => value + 1)}>Reintentar</button></p>}
    {data && <>
      <nav aria-label="Navegación del experimento" className="mb-5 flex flex-wrap gap-5 text-sm text-accent underline">
        <Link to="/experimentos">Volver a Experimentos</Link>
        <Link to={`/experimentos/${encodeURIComponent(id)}/comparacion`}>{fromComparison ? "Volver a comparación" : "Ver comparación"}</Link>
      </nav>
      {requestedRun !== null && !requested && <p role="status" className="mb-4">La ejecución solicitada no existe en este experimento; se muestra la primera disponible.</p>}
      <div className="flex flex-wrap items-center gap-4 border-b border-border pb-5"><h2 className="font-heading text-2xl">{data.request.name}</h2><StatusLabel kind="execution" value={data.status} /></div>
      <p className="mt-3 text-sm text-text-secondary">ID: <span className="font-mono">{data.id}</span>. {data.status === "running" || data.status === "pending" || data.status === "held" ? "Consultando el progreso guardado; salir de esta página no cancela la ejecución." : "Estado guardado del experimento."}</p>
      <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Elegir ejecución">
        {data.runs.map((run) => <button key={run.ordinal} type="button" aria-pressed={selected?.ordinal === run.ordinal} className={`${button} ${selected?.ordinal === run.ordinal ? "border-accent text-accent" : ""}`} onClick={() => setOrdinal(run.ordinal)}>{run.ordinal + 1}. {data.request.strategies[run.ordinal]?.name ?? "Estrategia"} · <StatusLabel kind="execution" value={run.status} /></button>)}
      </div>
      {selected && <RunView key={`${id}:${selected.ordinal}`} data={data} run={selected} />}
    </>}
  </div>;
}
