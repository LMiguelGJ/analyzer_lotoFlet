import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiClient, NetworkError } from "../api/client";
import type { BacktestMoney, BacktestReport, BacktestSessionSummary, BacktestTraceMetadata } from "../api/types";

const PAGE_SIZE = 20;
const outcomes: Record<BacktestSessionSummary["outcome"], string> = {
  reached_goal: "Meta alcanzada", quiebre: "Quiebre", incomplete: "Inconclusa al final de los datos",
};
type MoneyFormat = (value: BacktestMoney) => string;
type LoadState<T> = { key: string; status: "loading" } | { key: string; status: "error"; error: string }
  | { key: string; status: "ready"; page: T };

function readError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 404) return "El informe o la sesión ya no existe. No se recuperó el detalle.";
  if (cause instanceof ApiError && cause.status === 409) return "El detalle guardado no está disponible o está dañado. No se reconstruye desde el historial actual.";
  if (cause instanceof NetworkError) return "No se pudo contactar al servidor local. El detalle todavía no se cargó.";
  return "No se pudo cargar el detalle guardado. Podés reintentar sin modificar el informe.";
}

/** One bounded request per page or explicit retry. Cleanup ignores obsolete responses. */
function usePage<T>(key: string, load: () => Promise<T>) {
  const [state, setState] = useState<LoadState<T>>({ key, status: "loading" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    setState({ key, status: "loading" });
    load().then((page) => { if (live) setState({ key, status: "ready", page }); })
      .catch((cause: unknown) => { if (live) setState({ key, status: "error", error: readError(cause) }); });
    return () => { live = false; };
  }, [key, load, retry]);
  // Hide old data in the render that precedes effect cleanup on a page change.
  return { state: state.key === key ? state : { key, status: "loading" } as LoadState<T>,
    retry: () => setRetry((value) => value + 1) };
}

/** Move focus before controls unmount; async responses never move it again. */
function focusPage(heading: HTMLHeadingElement | null) {
  if (heading?.parentElement?.contains(document.activeElement)) heading.focus();
}

function PageControls({ kind, offset, total, count, onChange }: {
  kind: "sesiones" | "apuestas"; offset: number; total: number; count: number;
  onChange: (offset: number) => void;
}) {
  return <nav aria-label={`Paginación de ${kind}`} className="flex flex-wrap items-center justify-between gap-3">
    <p>{total === 0 ? "0" : `${offset + 1}–${Math.min(offset + count, total)}`} de {total} {kind} almacenadas</p>
    <div className="flex flex-wrap gap-2">
      <button type="button" className="btn btn-secondary" aria-label={`Anteriores ${kind}`} disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
      <button type="button" className="btn btn-secondary" aria-label={`Siguientes ${kind}`} disabled={offset + PAGE_SIZE >= total} onClick={() => onChange(offset + PAGE_SIZE)}>Siguiente</button>
    </div>
  </nav>;
}

function Availability({ trace }: { trace: BacktestTraceMetadata | undefined }) {
  if (!trace || trace.status === "not_stored") return <p>Detalle no almacenado</p>;
  return <div className="space-y-2">
    {trace.status === "truncated" ? <>
      <p>Detalle limitado: se almacenaron {trace.stored_sessions} de {trace.total_sessions} sesiones y {trace.stored_bets} de {trace.total_bets} apuestas. Solo se conserva un prefijo de sesiones completas; el resto no está disponible.</p>
      <p className="field-help">Límites de captura: {trace.limits.sessions} sesiones, {trace.limits.bets} apuestas y {trace.limits.bytes} bytes. Los totales del informe incluyen toda la ejecución.</p>
      {trace.stored_sessions === 0 && <p>Ninguna sesión completa cupo en los límites de captura; no significa que la ejecución estuviera vacía.</p>}
    </> : trace.status === "empty" ? <p>La ejecución no inició sesiones ni registró apuestas.</p>
      : <p>Detalle completo almacenado: {trace.total_sessions} sesiones y {trace.total_bets} apuestas.</p>}
    {trace.source_window && <>
      <p>Límite inicial de la ventana reproducida: {trace.source_window.first.label}</p>
      <p>Límite final de la ventana reproducida: {trace.source_window.last.label}</p>
    </>}
    <p className="field-help">Los saldos y apuestas están en pesos RD$ nativos. Las posiciones en fuente son índices desde 0, no identificadores oficiales de sorteo. La fecha de la primera apuesta no es un inicio solicitado.</p>
  </div>;
}

export function BacktestSessions({ report, formatMoney }: { report: BacktestReport; formatMoney: MoneyFormat }) {
  const trace = report.trace;
  const available = trace && trace.status !== "not_stored" && trace.stored_sessions > 0;
  return <section aria-label="Sesiones y apuestas" className="backtest-window space-y-4">
    <h3>Sesiones y apuestas</h3>
    <Availability trace={trace} />
    {available && !report.id && <p>Sin identificador guardado: no se puede consultar el detalle.</p>}
    {available && report.id && <SessionsBrowser key={JSON.stringify(report)} report={report} formatMoney={formatMoney} />}
  </section>;
}

function SessionsBrowser({ report, formatMoney }: { report: BacktestReport; formatMoney: MoneyFormat }) {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const load = useCallback(() => apiClient.getBacktestSessions(report.id, offset, PAGE_SIZE), [report.id, offset]);
  const { state, retry } = usePage(`${report.id}:${offset}`, load);
  const changePage = (next: number) => { focusPage(heading.current); setSelected(null); setOffset(next); };
  const page = state.status === "ready" ? state.page : null;
  return <div className="space-y-4">
    <h4 ref={heading} tabIndex={-1}>Sesiones almacenadas · página {Math.floor(offset / PAGE_SIZE) + 1}</h4>
    {state.status === "loading" && <p role="status">Cargando sesiones…</p>}
    {state.status === "error" && <div className="space-y-2"><p role="alert">{state.error}</p><button type="button" className="btn btn-secondary" onClick={() => { focusPage(heading.current); retry(); }}>Reintentar sesiones</button></div>}
    {page?.trace.status === "not_stored" && <p>Detalle no almacenado</p>}
    {page && page.trace.status !== "not_stored" && <>
      {page.items.length === 0 && <p>No hay sesiones almacenadas en esta página.</p>}
      <ul aria-label="Sesiones almacenadas" className="backtest-session-list">
        {page.items.map((session) => <li key={session.ordinal} className="backtest-session">
          <h4>Sesión {session.ordinal + 1}</h4>
          <p className="field-help">Ordinal original: {session.ordinal} (desde 0)</p>
          <p>Primera apuesta registrada: {session.first_bet?.label ?? "ninguna"}{session.first_bet?.source_index != null && ` · posición en fuente ${session.first_bet.source_index}`}</p>
          <p>{outcomes[session.outcome]} · saldo final {formatMoney(session.final_balance)} · {session.bets_count} apuestas</p>
          {session.last_bet && <p>Última apuesta registrada: {session.last_bet.label}. El resultado de cierre es el guardado; no se almacenó una fecha de cierre separada.</p>}
          <button type="button" className="btn btn-secondary" aria-label={`Ver apuestas de la sesión ${session.ordinal + 1}`} aria-pressed={selected === session.ordinal} onClick={() => setSelected(session.ordinal)}>Ver apuestas</button>
        </li>)}
      </ul>
      <PageControls kind="sesiones" offset={offset} total={page.total} count={page.items.length} onChange={changePage} />
      {selected !== null && <SessionBets key={selected} id={report.id} ordinal={selected} formatMoney={formatMoney} />}
    </>}
  </div>;
}

function SessionBets({ id, ordinal, formatMoney }: { id: string; ordinal: number; formatMoney: MoneyFormat }) {
  const [offset, setOffset] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const load = useCallback(() => apiClient.getBacktestSessionBets(id, ordinal, offset, PAGE_SIZE), [id, ordinal, offset]);
  const { state, retry } = usePage(`${id}:${ordinal}:${offset}`, load);
  return <section aria-label={`Detalle de la sesión ${ordinal + 1}`} className="backtest-session-bets space-y-3">
    <h4 ref={heading} tabIndex={-1}>Apuestas de la sesión {ordinal + 1} · página {Math.floor(offset / PAGE_SIZE) + 1}</h4>
    {state.status === "loading" && <p role="status">Cargando apuestas…</p>}
    {state.status === "error" && <><p role="alert">{state.error}</p><button type="button" className="btn btn-secondary" onClick={() => { focusPage(heading.current); retry(); }}>Reintentar apuestas</button></>}
    {state.status === "ready" && <>
      {state.page.total === 0 ? <p>Esta sesión se cerró sin apuestas registradas.</p> : <div className="backtest-bets-ledger" role="region" aria-label="Tabla de apuestas; desplazamiento horizontal" tabIndex={0}>
        <table>
          <caption>Apuestas registradas de la sesión {ordinal + 1}</caption>
          <thead><tr><th scope="col">Apuesta</th><th scope="col">Fecha registrada</th><th scope="col">Posición en fuente (desde 0)</th><th scope="col">Números seleccionados</th><th scope="col">Por número</th><th scope="col">Apostado</th><th scope="col">Resultados</th><th scope="col">Pagado</th><th scope="col">Saldo</th></tr></thead>
          <tbody>{state.page.items.map((bet) => <tr key={bet.bet_index}>
            <th scope="row">{bet.bet_index + 1}</th><td className="whitespace-nowrap">{bet.label}</td><td>{bet.source_index ?? "No almacenada"}</td>
            <td className="max-w-xs break-words">{bet.numbers.join(" / ")}</td><td>{formatMoney(bet.per_number)}</td><td>{formatMoney(bet.wagered)}</td>
            <td>{bet.results.join(" / ")}</td><td>{formatMoney(bet.paid)}</td><td>{formatMoney(bet.balance)}</td>
          </tr>)}</tbody>
        </table>
      </div>}
      <PageControls kind="apuestas" offset={offset} total={state.page.total} count={state.page.items.length} onChange={(next) => { focusPage(heading.current); setOffset(next); }} />
    </>}
  </section>;
}
