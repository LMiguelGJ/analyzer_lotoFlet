import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../../api/client";
import {
  createLaboratoryRun, deleteLaboratory, getLaboratory, getLaboratoryOptions, getLaboratoryRun, listLaboratoryRuns, listLaboratorySessions,
} from "../../api/laboratories";
import type { LaboratoryDetail, LaboratoryRun, LaboratoryRunListItem } from "../../api/laboratories";
import { getReferenceLabs } from "../../api/referenceLabs";
import type { ReferencePage, ReferenceSessionPage } from "../../api/referenceLabs";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui/Controls";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { stakeLabel, systemLabel } from "../reference-labs/lab-model";
import { rankingParamsText } from "./form-model";
import { count } from "./count";
import { formatMean } from "./mean";
import { deadlineSummary, expectedReturnPerPeso, formatAbsoluteDOP, formatAverageDays, formatHouseEdge, formatPercentShare, formatReturnOnWagered, formatReturnPerPeso, houseEdgePercent, isValidLaboratoryWallet, returnOnWagered, returnPerPeso, validYearResults, yearRowPresentation } from "./result-model";
import "../reference-labs/reference-labs.css";

const RUN_PAGE = 200;
const SESSION_PAGE = 200;
const money = (value: number) => formatSignedDOP(value);
const outcomeLabel = (outcome: string) => (outcome === "goal" ? "Meta" : outcome === "ruin" ? "Quiebra" : outcome === "timeout" ? "No llegó a tiempo" : "Incompleta");
const isAbort = (error: unknown) => error instanceof Error && error.name === "AbortError";
function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local.";
  return "Ocurrió un error inesperado.";
}

interface Props { labId: string; onDeleted: () => void; /** A run was saved: the parent list refetches its latest-result indicators. */ onRunsChanged?: () => void }

export function LaboratoryPanel({ labId, onDeleted, onRunsChanged }: Props) {
  const [detail, setDetail] = useState<LaboratoryDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailReload, setDetailReload] = useState(0);
  const [historySha, setHistorySha] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ReferencePage<LaboratoryRunListItem> | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [runOffset, setRunOffset] = useState(0);
  const [runReload, setRunReload] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<LaboratoryRun | null>(null);
  const [selectedError, setSelectedError] = useState<string | null>(null);
  const [selectedReload, setSelectedReload] = useState(0);
  const [sessions, setSessions] = useState<ReferenceSessionPage | null>(null);
  const [sessionOffset, setSessionOffset] = useState(0);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionReload, setSessionReload] = useState(0);
  const [running, setRunning] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const reconciliation = useRef<symbol | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const runAbort = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setDetail(null); setDetailError(null);
    getLaboratory(labId, { signal: controller.signal }).then((value) => { if (current) setDetail(value); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setDetailError(errorText(error)); });
    return () => { current = false; controller.abort(); runAbort.current?.abort(); };
  }, [labId, detailReload]);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    // Chance Express runs against the frozen reference; any other list brings its own history fingerprint.
    getLaboratoryOptions({ signal: controller.signal })
      .then((options) => options.list.id === "chance_express"
        ? getReferenceLabs({ signal: controller.signal }).then((catalog) => catalog.reference_history.sha256)
        : options.history_sha256)
      .then((sha) => { if (current) setHistorySha(sha); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setHistoryError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, []);

  const reloadRuns = useCallback(() => setRunReload((value) => value + 1), []);
  useEffect(() => {
    if (!detail) return;
    const controller = new AbortController(); let current = true;
    setRunsError(null);
    const token = reconciliation.current;
    const finishReconciliation = (success: boolean) => {
      if (!current || token === null || reconciliation.current !== token) return;
      reconciliation.current = null;
      setReconciling(false);
      if (success) { setUncertain(false); setActionError(null); }
    };
    listLaboratoryRuns(labId, { offset: runOffset, limit: RUN_PAGE }, { signal: controller.signal }).then((page) => {
      if (!current) return;
      setRuns(page);
      finishReconciliation(true);
    }).catch((error: unknown) => {
      if (!current) return;
      if (!isAbort(error)) setRunsError(errorText(error));
      finishReconciliation(false);
    });
    return () => { current = false; controller.abort(); };
  }, [detail, labId, runOffset, runReload]);

  useEffect(() => {
    setSelected(null); setSelectedError(null);
    if (!selectedId) return;
    const controller = new AbortController(); let current = true;
    getLaboratoryRun(labId, selectedId, { signal: controller.signal })
      .then((run) => { if (current) setSelected(run); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setSelectedError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, [labId, selectedId, selectedReload]);

  useEffect(() => {
    setSessions(null); setSessionError(null);
    if (!selectedId) return;
    const controller = new AbortController(); let current = true;
    listLaboratorySessions(labId, selectedId, { offset: sessionOffset, limit: SESSION_PAGE }, { signal: controller.signal })
      .then((page) => { if (current) setSessions(page); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setSessionError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, [labId, selectedId, sessionOffset, sessionReload]);

  function reconcileRuns() {
    if (!uncertain || reconciliation.current !== null) return;
    reconciliation.current = Symbol("fresh run list");
    setReconciling(true);
    setRunOffset(0);
    reloadRuns();
  }

  async function execute() {
    if (!historySha || running || uncertain || reconciling) return;
    setRunning(true); setActionError(null);
    const controller = new AbortController(); runAbort.current = controller;
    try {
      const run = await createLaboratoryRun(labId, historySha, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setSelectedId(run.id); setSessionOffset(0); setRunOffset(0); reloadRuns(); setDetailReload((value) => value + 1); onRunsChanged?.();
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof NetworkError || isAbort(error) || (error instanceof ApiError && error.uncertainWrite)) {
        setUncertain(true);
        setActionError("No hay confirmación de si el servidor guardó esta ejecución. No la enviaremos de nuevo automáticamente. Actualizá las corridas guardadas para comprobarlo antes de iniciar otra.");
      } else setActionError(errorText(error));
    } finally { if (runAbort.current === controller) { runAbort.current = null; setRunning(false); } }
  }

  async function remove() {
    if (!detail || deleting) return;
    setDeleting(true); setDeleteError(null);
    try {
      await deleteLaboratory(labId, detail.owned_run_count);
      setConfirmDelete(false);
      onDeleted();
    } catch (error) {
      setConfirmDelete(false);
      setDeleteError(errorText(error));
      if (error instanceof ApiError && error.status === 409) setDetailReload((value) => value + 1);
    } finally { setDeleting(false); }
  }

  if (detailError) return <ErrorBanner cause="No pudimos abrir este laboratorio." recovery={detailError} actionLabel="Reintentar" onAction={() => setDetailReload((value) => value + 1)} />;
  if (!detail) return <Loading label="Cargando laboratorio…" rows={4} />;
  const { definition } = detail;
  const config = definition.config;
  const totals = selected?.summary.totals;
  const deadline = totals ? deadlineSummary(totals) : null;
  const years = selected ? validYearResults(selected.summary.by_year) : null;
  const wallet = selected && totals && isValidLaboratoryWallet(selected.summary.wallet, totals.total_net) ? selected.summary.wallet : null;

  return <section className="reference-page" aria-labelledby="lab-title">
    <header className="reference-heading">
      <div><h2 id="lab-title">{definition.name}</h2><p>{systemLabel(config.system)} · {config.coverage} {config.coverage === 1 ? "número" : "números"} · {stakeLabel(config.stake_style)}{rankingParamsText(config.ranking_params)}{config.max_session_draws === undefined ? "" : ` · máx ${config.max_session_draws} ${config.max_session_draws === 1 ? "día" : "días"}`}{config.max_stake_per_number === undefined ? "" : ` · tope ${formatAbsoluteDOP(config.max_stake_per_number)}`}</p></div>
      <Button variant="ghost" onClick={() => { setDeleteError(null); setConfirmDelete(true); }}>Eliminar laboratorio</Button>
    </header>
    {deleteError && <div className="reference-action-error" role="alert"><p>{deleteError}</p><Button onClick={() => setDeleteError(null)}>Cerrar</Button></div>}

    <section className="reference-contract" aria-label="Reglas del laboratorio">
      <h3>Reglas fijadas</h3>
      <dl className="reference-contract-grid">
        <div><dt>Selección</dt><dd>{systemLabel(config.system)}</dd></div>
        <div><dt>Cobertura</dt><dd>{config.coverage} {config.coverage === 1 ? "número seleccionado" : "números seleccionados"}</dd></div>
        {config.ranking_params !== undefined && <div><dt>Parámetros del sistema</dt><dd>{rankingParamsText(config.ranking_params).slice(3)}</dd></div>}
        <div><dt>Estilo de apuesta</dt><dd>{stakeLabel(config.stake_style)}</dd></div>
        <div><dt>Reglas de apuesta</dt><dd>{config.stake_rules === 2 ? "Reglas v2" : "Reglas v1"}</dd></div>
        <div><dt>Capital inicial</dt><dd>{money(config.capital)}</dd></div>
        <div><dt>Meta de saldo</dt><dd>{money(config.goal)}</dd></div>
        {config.max_stake_per_number !== undefined && <div><dt>Apuesta máxima por número</dt><dd>{formatAbsoluteDOP(config.max_stake_per_number)}</dd></div>}
        <div><dt>Premios</dt><dd>{config.prizes.map((prize, index) => `${index + 1}.º ${money(prize)}`).join(" · ")}</dd></div>
        <div><dt>Ventana</dt><dd>{config.window_start} – {config.window_end}</dd></div>
        <div><dt>Corridas guardadas</dt><dd>{formatNumber(detail.owned_run_count)}</dd></div>
      </dl>
    </section>

    <div className="reference-run-action">
      <Button variant="primary" onClick={() => void execute()} loading={running} disabled={!historySha || uncertain || reconciling || !runs || !!runsError}>Ejecutar laboratorio</Button>
      {historyError && <span>{`No se pudo leer la fuente de datos: ${historyError}`}</span>}
    </div>
    {actionError && <div className="reference-action-error" role="alert"><p>{actionError}</p>{uncertain && <Button disabled={reconciling} onClick={reconcileRuns}>Actualizar corridas guardadas</Button>}</div>}

    <section className="reference-runs" aria-labelledby="lab-runs-title">
      <div className="reference-section-heading"><div><h3 id="lab-runs-title">Corridas guardadas</h3></div><Button disabled={reconciling} onClick={reloadRuns}>Actualizar</Button></div>
      {runsError ? <ErrorBanner cause="No pudimos cargar las corridas guardadas." recovery={runsError} actionLabel="Reintentar" onAction={reloadRuns} />
        : !runs ? <Loading label="Cargando corridas guardadas…" rows={3} />
        : runs.items.length === 0 ? <p className="reference-empty">Todavía no hay corridas guardadas para este laboratorio.</p>
        : <>
          <div className="reference-table-wrap" role="region" aria-label="Corridas guardadas" tabIndex={0}><table className="reference-table lab-runs-table"><thead><tr><th scope="col">Creada</th><th scope="col">Sesiones</th><th scope="col">Neto total</th><th scope="col">Acciones</th></tr></thead><tbody>
            {runs.items.map((run) => <tr key={run.id}><td>{new Date(run.created_at).toLocaleString("es-DO")}</td><td>{formatNumber(run.summary.totals.sessions_total)} · {count(run.summary.totals.incomplete, "incompleta", "incompletas")}</td><td>{money(run.summary.totals.total_net)}</td><td><Button aria-pressed={selectedId === run.id} onClick={() => { setSelectedId(run.id); setSessionOffset(0); setSessionReload((value) => value + 1); }}>Ver resultado</Button></td></tr>)}
          </tbody></table></div>
          <nav className="reference-pagination" aria-label="Paginación de corridas"><span>{count(runs.total, "corrida", "corridas")}</span><div><Button disabled={reconciling || runOffset === 0} onClick={() => setRunOffset(Math.max(0, runOffset - RUN_PAGE))}>Anterior</Button><Button disabled={reconciling || runOffset + RUN_PAGE >= runs.total} onClick={() => setRunOffset(runOffset + RUN_PAGE)}>Siguiente</Button></div></nav>
        </>}
    </section>

    {selectedError && <ErrorBanner cause="No pudimos cargar el resultado guardado." recovery={selectedError} actionLabel="Reintentar" onAction={() => setSelectedReload((value) => value + 1)} />}
    {selectedId && !selectedError && !selected && <Loading label="Cargando resultado guardado…" rows={4} />}
    {selected && totals && <section className="reference-result lab-result" aria-labelledby="lab-result-title">
      <h3 id="lab-result-title">Resultado guardado</h3>
      <section className="lab-result-wallet" aria-labelledby="lab-wallet-title">
      <h4 id="lab-wallet-title" className="lab-result-subheading">Tu dinero · Simulación</h4>
      <div className="lab-result-grid lab-result-primary">
        <div><span>Aportado de tu bolsillo</span><strong>{formatAbsoluteDOP(wallet?.out_of_pocket ?? null)}</strong></div>
        <div><span>Patrimonio al final</span><strong>{formatAbsoluteDOP(wallet?.final_wealth ?? null)}</strong></div>
        <div className="lab-net" data-negative={totals.total_net < 0}><span>Ganancia / pérdida</span><strong>{money(totals.total_net)}</strong></div>
      </div>
      <details className="lab-wallet-help">
        <summary>ⓘ Cómo se calcula</summary>
        <p>Los saldos que quedan se conservan para la próxima sesión. Solo se aporta dinero si falta capital para iniciar una sesión existente; no hay retiros y las apuestas no cambian.</p>
      </details>
      </section>
      <section className="lab-result-movement" aria-labelledby="lab-movement-title">
      <h4 id="lab-movement-title" className="lab-result-subheading">Movimiento de apuestas</h4>
      <div className="lab-result-grid lab-result-financial">
        <div><span>Volumen apostado</span><strong>{money(totals.total_wagered)}</strong></div>
        <div><span>Premios recibidos</span><strong>{money(totals.total_paid)}</strong></div>
        <div><span>Retorno sobre apostado</span><strong>{formatReturnOnWagered(returnOnWagered(totals.total_net, totals.total_wagered))}</strong></div>
      </div>
      <dl className="lab-evaluation lab-house-edge" aria-label="Retorno por peso y ventaja de la casa">
        <div><dt>Retorno por peso apostado</dt><dd>{formatReturnPerPeso(returnPerPeso(totals.total_paid, totals.total_wagered))}</dd></div>
        <div><dt>Ventaja de la casa</dt><dd>{formatHouseEdge(houseEdgePercent(config.prizes))}</dd></div>
      </dl>
      <p className="lab-house-edge-hint">Por cada peso apostado, el juego devuelve en promedio {expectedReturnPerPeso(config.prizes)}</p>
      </section>
      <section className="lab-result-summary" aria-label="Resumen de sesiones">
      <div className="lab-result-grid lab-result-counts">
        <div><span>Sesiones cerradas</span><strong>{formatNumber(totals.completed)}</strong></div>
        <div><span>{deadline ? "Metas en tiempo" : "Metas"}</span><strong>{formatNumber(totals.goals)}</strong></div>
        {deadline && <div><span>No llegó a tiempo</span><strong>{formatNumber(deadline.timeouts)}</strong></div>}
        <div><span>Quiebras</span><strong>{formatNumber(totals.ruins)}</strong></div>
        <div><span>Incompletas</span><strong>{formatNumber(totals.incomplete)}</strong></div>
      </div>
      {deadline && <dl className="lab-evaluation lab-deadline" aria-label="Plazo por sesión">
        <div><dt>Sesiones que llegaron a la meta a tiempo</dt><dd>{formatPercentShare(deadline.inTimePercent)}</dd></div>
        <div><dt>Días promedio hasta la meta</dt><dd>{formatAverageDays(deadline.averageDaysToGoal)}</dd></div>
        <div><dt>Perdido en las que no llegaron a tiempo</dt><dd>{deadline.timeoutNet === null ? "No disponible" : money(deadline.timeoutNet)}</dd></div>
      </dl>}
      <dl className="lab-evaluation">
        <div><dt>Sorteos evaluados</dt><dd>{formatNumber(selected.summary.eligible_draws)}</dd></div>
        <div><dt>Sin ranking entre extremos</dt><dd>{formatNumber(selected.summary.gaps)}</dd></div>
      </dl>
      </section>
      {years && <section className="lab-result-years" aria-labelledby="lab-years-title">
        <h4 id="lab-years-title" className="lab-result-subheading">Resultado por año</h4>
        <div className="reference-table-wrap" role="region" aria-label="Resultado por año, tabla" tabIndex={0}><table className="reference-table lab-years-table"><thead><tr><th scope="col">Año</th><th scope="col">Ganancia/pérdida</th><th scope="col">% sobre el capital</th><th scope="col">Metas</th><th scope="col">Quiebras</th></tr></thead><tbody>
          {years.map((row) => { const view = yearRowPresentation(row); return <tr key={row.year}><th scope="row">{row.year}</th><td><span className="lab-year-net" data-state={view.state}>{view.net}</span><span className="lab-sr-only">{view.label}</span></td><td>{view.percent}</td><td>{formatNumber(row.goals)}</td><td>{formatNumber(row.ruins)}</td></tr>; })}
        </tbody></table></div>
        <p className="lab-years-hint">Cada sesión cuenta en el año en que cierra; la sesión abierta, en el año de su último sorteo.</p>
      </section>}
      <div className="lab-result-details">
      <details className="lab-session-detail">
        <summary>Detalle de sesiones</summary>
        <div className="lab-result-grid lab-result-financial">
          <div><span>Media neta de cerradas</span><strong>{totals.mean_net_closed === null ? "No disponible" : formatMean(totals.mean_net_closed)}</strong></div>
        </div>
      </details>
      <details className="lab-provenance">
        <summary>Datos de la reproducción</summary>
        <dl>
          <div><dt>Tramo efectivo</dt><dd>{selected.summary.eligible_draws === 0 ? "Sin sorteos elegibles" : `${selected.summary.first ?? "No disponible"} – ${selected.summary.last ?? "No disponible"}`}</dd></div>
          <div><dt>Ventana configurada</dt><dd>{selected.snapshot.definition.config.window_start} – {selected.snapshot.definition.config.window_end}</dd></div>
          <div><dt>SHA-256 del historial</dt><dd className="reference-sha">{selected.snapshot.provenance.history_sha256}</dd></div>
          <div><dt>SHA-256 de rankings</dt><dd className="reference-sha">{selected.snapshot.provenance.rankings_sha256}</dd></div>
          <div><dt>SHA-256 de sesiones</dt><dd className="reference-sha">{selected.summary.session_sha256}</dd></div>
        </dl>
      </details>
      </div>
      {sessionError ? <ErrorBanner cause="No pudimos cargar las sesiones." recovery={sessionError} actionLabel="Reintentar" onAction={() => setSessionReload((value) => value + 1)} />
        : !sessions ? <Loading label="Cargando sesiones…" rows={4} /> : <>
      <div className="reference-section-heading"><div><h4>{sessions.total === 0 ? "Sesiones 0 de 0" : `Sesiones ${formatNumber(sessions.offset + 1)}–${formatNumber(Math.min(sessions.offset + sessions.items.length, sessions.total))} de ${formatNumber(sessions.total)}`}</h4></div></div>
      {sessions.items.length === 0 ? <p className="reference-empty">Esta corrida no tiene sesiones en esta página.</p> : <div className="reference-table-wrap" role="region" aria-label="Resúmenes de sesiones" tabIndex={0}><table className="reference-table lab-sessions-table"><thead><tr><th scope="col">Sesión</th><th scope="col">Cierre</th><th scope="col">Sorteos</th><th scope="col">Saldo final</th><th scope="col">Apostado</th><th scope="col">Pagado</th></tr></thead><tbody>
        {sessions.items.map(({ ordinal, summary }) => <tr key={ordinal}><th scope="row">{formatNumber(ordinal + 1)}</th><td>{outcomeLabel(summary.outcome)}</td><td>{formatNumber(summary.draws)}</td><td>{money(summary.final_balance)}</td><td>{money(summary.wagered)}</td><td>{money(summary.paid)}</td></tr>)}
      </tbody></table></div>}
      <nav className="reference-pagination" aria-label="Paginación de sesiones"><span>{count(sessions.total, "sesión", "sesiones")} · página de {SESSION_PAGE}</span><div><Button disabled={sessionOffset === 0} onClick={() => setSessionOffset(Math.max(0, sessionOffset - SESSION_PAGE))}>Anterior</Button><Button disabled={sessionOffset + SESSION_PAGE >= sessions.total} onClick={() => setSessionOffset(sessionOffset + SESSION_PAGE)}>Siguiente</Button></div></nav>
      </>}
    </section>}

    <ConfirmDialog
      open={confirmDelete}
      title="Eliminar laboratorio"
      description={`Se eliminará «${definition.name}» junto con ${count(detail.owned_run_count, "corrida guardada", "corridas guardadas")} y ${count(detail.owned_session_count, "sesión", "sesiones")}. No se puede deshacer, y no se vuelve a crear solo al reiniciar.`}
      confirmLabel={deleting ? "Eliminando…" : "Eliminar laboratorio y corridas"}
      onCancel={() => { if (!deleting) setConfirmDelete(false); }}
      onConfirm={() => void remove()}
    />
  </section>;
}
