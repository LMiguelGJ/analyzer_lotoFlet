import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { listRunSessions } from "../../api/runs";
import type { Page, RunOutcome, RunSession } from "../../api/types";
import { formatNumber, formatOutcome, formatSignedDOP } from "../../lib/format";
import { Button } from "../../components/ui/Controls";
import { Loading } from "../../components/ui/Feedback";
import { outcomeLabel } from "./result-model";
import { RunBets } from "./RunBets";

const SESSION_PAGE_SIZE = 50;
function message(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
}

export function RunSessions({ runId }: { runId: string }) {
  const [outcome, setOutcome] = useState<RunOutcome | "">("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page<RunSession> | null>(null);
  const [selected, setSelected] = useState<RunSession | null>(null);
  const [selectionRevision, setSelectionRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setLoading(true); setFailure(null); setPage(null); setSelected(null);
    listRunSessions(runId, { offset, limit: SESSION_PAGE_SIZE, ...(outcome ? { outcome } : {}) }, { signal: controller.signal }).then((loaded) => {
      if (current) setPage(loaded);
    }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setFailure(message(error));
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [runId, outcome, offset, revision]);

  function changeOutcome(value: RunOutcome | "") { setOutcome(value); setOffset(0); setSelected(null); }
  const headingId = "result-sessions-title";
  return <section className="result-sessions" aria-labelledby={headingId}>
    <div className="result-section-heading"><div><h3 id={headingId}>Sesiones guardadas</h3><p>El orden y los ordinales corresponden a las sesiones conservadas.</p></div><label className="result-filter"><span>Filtrar sesiones</span><select value={outcome} onChange={(event) => changeOutcome(event.target.value as RunOutcome | "")}><option value="">Todos los resultados</option><option value="goal">Meta</option><option value="ruin">Quiebra</option><option value="limit">Límite</option><option value="incomplete">Incompleta</option></select></label></div>
    {loading ? <Loading label="Cargando sesiones guardadas…" rows={3} /> : failure ? <div className="runs-inline-error" role="alert"><p>No se pudieron cargar las sesiones.</p><p>{failure}</p><Button onClick={() => setRevision((value) => value + 1)}>Reintentar sesiones</Button></div> : !page?.items.length ? <p className="result-empty">{outcome ? `No hay sesiones guardadas con resultado “${outcomeLabel(outcome)}”.` : "No hay sesiones guardadas para mostrar."}</p> : <>
      <div className="runs-table-wrap result-table-wrap" role="region" aria-label="Sesiones de la corrida" tabIndex={0}><table className="runs-table result-session-table"><thead><tr><th scope="col">Sesión</th><th scope="col">Inicio – fin</th><th scope="col">Sorteos · apuestas</th><th scope="col">Apostado</th><th scope="col">Pagado</th><th scope="col">Saldo final</th><th scope="col">Neto</th><th scope="col">Resultado</th><th scope="col">Detalle</th></tr></thead><tbody>{page.items.map((session) => <tr key={session.ordinal}>
        <th scope="row">Sesión {formatNumber(session.ordinal)}</th><td>{session.start_label} – {session.end_label}</td><td>{formatNumber(session.draws)} · {formatNumber(session.bets)}</td><td className="runs-money">{formatSignedDOP(session.wagered)}</td><td className="runs-money">{formatSignedDOP(session.paid)}</td><td className="runs-money">{formatSignedDOP(session.final_balance)}</td><td className={`runs-money ${session.net < 0 ? "is-negative" : ""}`}>{session.net < 0 && <span className="result-word">Pérdida · </span>}{formatSignedDOP(session.net)}{session.net > 0 && <span className="result-word"> · ganancia</span>}</td><td>{formatOutcome(session.outcome)}</td><td><Button className="result-select-session" variant="secondary" aria-pressed={selected?.ordinal === session.ordinal} aria-label={`Ver apuestas de sesión ${formatNumber(session.ordinal)}`} onClick={() => { setSelected(session); setSelectionRevision((value) => value + 1); }}>{selected?.ordinal === session.ordinal ? "Seleccionada" : "Ver apuestas"}</Button></td>
      </tr>)}</tbody></table></div>
      <nav className="runs-pagination result-pagination" aria-label="Paginación de sesiones"><span>Sesiones: {formatNumber(page.offset + 1)}–{formatNumber(Math.min(page.offset + page.items.length, page.total))} de {formatNumber(page.total)} guardadas</span><div><Button variant="secondary" disabled={page.offset === 0} onClick={() => { setSelected(null); setOffset(Math.max(0, page.offset - page.limit)); }}>Anterior sesiones</Button><Button variant="secondary" disabled={page.offset + page.items.length >= page.total} onClick={() => { setSelected(null); setOffset(page.offset + page.limit); }}>Siguiente sesiones</Button></div></nav>
    </>}
    {selected && <section className="result-selected-session" aria-label={`Detalle de sesión ${formatNumber(selected.ordinal)}`}>
      <h4>Sesión {formatNumber(selected.ordinal)} · {outcomeLabel(selected.outcome)}</h4>
      {!selected.detail_available ? <p className="result-empty">Detalle de apuestas no almacenado para esta sesión</p> : <RunBets key={`${runId}-${selected.ordinal}-${selectionRevision}`} runId={runId} ordinal={selected.ordinal} />}
    </section>}
  </section>;
}
