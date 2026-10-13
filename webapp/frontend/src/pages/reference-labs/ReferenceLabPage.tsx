import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, NetworkError } from "../../api/client";
import { createReferenceRun, deleteReferenceRun, getReferenceLab, getReferenceRun, listReferenceRuns, listReferenceSessions } from "../../api/referenceLabs";
import type { ReferenceLabDetail, ReferencePage, ReferenceRun, ReferenceRunListItem, ReferenceSessionPage } from "../../api/referenceLabs";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui/Controls";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { labTitle, stakeLabel } from "./lab-model";
import "./reference-labs.css";

const RUN_PAGE_SIZE = 20;
const SESSION_PAGE_SIZE = 50;
function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local.";
  return "Ocurrió un error inesperado.";
}
function stakeDescription(style: string): string {
  if (style === "flat") return "Apuesta una unidad por número en cada sorteo.";
  if (style === "ladder") return "Usa una escalera fija de recuperación del primer premio: reinicia al acertar y avanza un paso cuando no lo acierta.";
  return "Ajusta la apuesta por número según la distancia a la meta y el saldo disponible.";
}
function outcomeLabel(outcome: string): string {
  return outcome === "goal" ? "Meta" : outcome === "ruin" ? "Quiebra" : "Incompleta";
}
function money(value: number): string { return formatSignedDOP(value); }

export function ReferenceLabPage() {
  const { labId = "" } = useParams();
  const [detail, setDetail] = useState<ReferenceLabDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [reloadDetail, setReloadDetail] = useState(0);
  const [runs, setRuns] = useState<ReferencePage<ReferenceRunListItem> | null>(null);
  const [runOffset, setRunOffset] = useState(0);
  const [runReload, setRunReload] = useState(0);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<ReferenceRun | null>(null);
  const [sessionPage, setSessionPage] = useState<SessionPage | null>(null);
  const [sessionOffset, setSessionOffset] = useState(0);
  const [sessionReload, setSessionReload] = useState(0);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ReferenceRunListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const runAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController(); let current = true;
    setDetail(null); setDetailError(null); setRuns(null); setSelectedRunId(null); setSelectedRun(null); setSessionPage(null); setActionError(null); setUncertain(false); setReconciling(false);
    getReferenceLab(labId, { signal: controller.signal }).then((value) => { if (current) setDetail(value); }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setDetailError(errorText(error));
    });
    return () => { current = false; controller.abort(); runAbortRef.current?.abort(); };
  }, [labId, reloadDetail]);

  const reloadRuns = useCallback(() => setRunReload((value) => value + 1), []);
  useEffect(() => {
    if (!detail) return;
    const controller = new AbortController(); let current = true;
    setRunsError(null);
    listReferenceRuns(labId, { offset: runOffset, limit: RUN_PAGE_SIZE }, { signal: controller.signal }).then((page) => {
      if (!current) return;
      if (runOffset > 0 && page.items.length === 0 && page.total > 0) { setRunOffset(Math.max(0, Math.ceil(page.total / RUN_PAGE_SIZE - 1) * RUN_PAGE_SIZE)); return; }
      setRuns(page);
      if (reconciling) { setUncertain(false); setReconciling(false); setActionError(null); }
    }).catch((error: unknown) => { if (current && !(error instanceof Error && error.name === "AbortError")) setRunsError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, [detail, labId, runOffset, runReload]);

  useEffect(() => {
    if (!selectedRunId) { setSelectedRun(null); setSessionPage(null); return; }
    const controller = new AbortController(); let current = true;
    setSelectedRun(null); setSessionPage(null); setSessionError(null);
    Promise.all([
      getReferenceRun(labId, selectedRunId, { signal: controller.signal }),
      listReferenceSessions(labId, selectedRunId, { offset: sessionOffset, limit: SESSION_PAGE_SIZE }, { signal: controller.signal }),
    ]).then(([run, page]) => { if (current) { setSelectedRun(run); setSessionPage(page); } }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setSessionError(errorText(error));
    });
    return () => { current = false; controller.abort(); };
  }, [labId, selectedRunId, sessionOffset, sessionReload]);

  async function execute() {
    if (!detail || running || uncertain) return;
    setRunning(true); setActionError(null);
    const controller = new AbortController();
    runAbortRef.current = controller;
    try {
      const run = await createReferenceRun(labId, detail.reference_history.sha256, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setSelectedRunId(run.id); setSessionOffset(0); setRunOffset(0); reloadRuns();
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof NetworkError || (error instanceof Error && error.name === "AbortError")) {
        setUncertain(true);
        setActionError("No hay confirmación de si el servidor guardó esta ejecución. No la enviaremos de nuevo automáticamente. Actualizá las corridas guardadas para reconciliar antes de iniciar otra.");
      } else setActionError(errorText(error));
    } finally { if (runAbortRef.current === controller) { runAbortRef.current = null; setRunning(false); } }
  }

  function refreshAfterUncertain() {
    setSelectedRunId(null); setSelectedRun(null); setSessionPage(null); setRunOffset(0); setReconciling(true); setActionError("Actualizando las corridas guardadas para reconciliar la ejecución…"); reloadRuns();
  }
  async function confirmDelete() {
    if (!deleteTarget || deleteBusy) return;
    setDeleteBusy(true); setDeleteError(null);
    try {
      await deleteReferenceRun(labId, deleteTarget.id);
      const nextTotal = Math.max(0, (runs?.total ?? 1) - 1);
      if (selectedRunId === deleteTarget.id) { setSelectedRunId(null); setSelectedRun(null); setSessionPage(null); }
      setDeleting(false); setDeleteTarget(null);
      setRunOffset(nextTotal === 0 ? 0 : runOffset >= nextTotal ? Math.floor((nextTotal - 1) / RUN_PAGE_SIZE) * RUN_PAGE_SIZE : runOffset);
      reloadRuns();
    } catch (error) { setDeleteError(errorText(error)); setDeleting(false); }
    finally { setDeleteBusy(false); }
  }

  if (detailError) return <section className="reference-page"><ErrorBanner cause="No pudimos abrir este laboratorio." recovery={detailError} actionLabel="Reintentar" onAction={() => setReloadDetail((value) => value + 1)} /></section>;
  if (!detail) return <section className="reference-page"><Loading label="Cargando laboratorio…" rows={4} /></section>;
  const lab = detail.lab;
  const totals = selectedRun?.summary.totals;

  return <section className="reference-page" aria-labelledby="reference-detail-title">
    <p className="reference-back"><Link to="/laboratorios">← Catálogo de laboratorios</Link></p>
    <header className="reference-heading"><div><h2 id="reference-detail-title">{labTitle(lab)}</h2><p>Ficha inmutable · {lab.lab_id}</p></div></header>
    <section className="reference-contract" aria-label="Contrato de laboratorio">
      <h3>Reglas fijadas</h3>
      <dl className="reference-contract-grid">
        <div><dt>Selección</dt><dd>{lab.selection_kind === "parity" ? "Paridad" : `Ranking: ${lab.system === "transition" ? "transición" : lab.system === "cold" ? "fríos" : lab.system === "mix" ? "mezclas" : lab.system}`}</dd></div>
        <div><dt>Cobertura</dt><dd>{lab.coverage} de 50 números</dd></div>
        <div><dt>Estilo de apuesta</dt><dd>{stakeLabel(lab.stake_style)}. {stakeDescription(lab.stake_style)}</dd></div>
        <div><dt>Capital inicial</dt><dd>{money(lab.capital)}</dd></div>
        <div><dt>Meta de saldo</dt><dd>{money(lab.goal)}</dd></div>
        <div><dt>Premios</dt><dd>{lab.prizes.map((prize, index) => `${index + 1}.º ${money(prize)}`).join(" · ")}</dd></div>
        <div><dt>Ventana fija</dt><dd>{lab.window.start} – {lab.window.end}</dd></div>
        <div><dt>Límite de duración</dt><dd>{lab.duration_cap === null ? "Sin límite" : formatNumber(lab.duration_cap)}</dd></div>
      </dl>
      <p className="reference-sha"><strong>Historial congelado · SHA-256</strong> {detail.reference_history.sha256}</p>
      <p className="reference-note">La ejecución usa únicamente la fuente congelada verificada por el servidor. Las reglas no se pueden editar. Es una reproducción histórica, no una predicción.</p>
    </section>

    <div className="reference-run-action">
      <Button variant="primary" onClick={() => void execute()} loading={running} disabled={uncertain || !runs || !!runsError}>Ejecutar laboratorio</Button>
      <span>Se guardará una corrida nueva con estas reglas fijas.</span>
    </div>
    {actionError && <div className="reference-action-error" role="alert"><p>{actionError}</p>{uncertain && <Button onClick={() => void refreshAfterUncertain()}>Actualizar corridas guardadas</Button>}</div>}

    <section className="reference-runs" aria-labelledby="reference-runs-title">
      <div className="reference-section-heading"><div><h3 id="reference-runs-title">Corridas guardadas</h3><p>Seleccioná una corrida para abrir su resultado.</p></div><Button variant="secondary" onClick={reloadRuns}>Actualizar</Button></div>
      {runsError ? <ErrorBanner cause="No pudimos cargar las corridas guardadas." recovery={runsError} actionLabel="Reintentar" onAction={reloadRuns} /> : !runs ? <Loading label="Cargando corridas guardadas…" rows={3} /> : runs.items.length === 0 ? <p className="reference-empty">Todavía no hay corridas guardadas para este laboratorio.</p> : <>
        <div className="reference-table-wrap" role="region" aria-label="Corridas guardadas" tabIndex={0}><table className="reference-table"><thead><tr><th scope="col">Creada</th><th scope="col">Sesiones</th><th scope="col">Neto total</th><th scope="col">Acciones</th></tr></thead><tbody>{runs.items.map((run) => <tr key={run.id}><td>{new Date(run.created_at).toLocaleString("es-DO")}</td><td>{formatNumber(run.summary.totals.sessions_total)} · {formatNumber(run.summary.totals.incomplete)} incompletas</td><td>{money(run.summary.totals.total_net)}</td><td><div className="reference-row-actions"><Button variant="secondary" aria-pressed={selectedRunId === run.id} onClick={() => { setSelectedRunId(run.id); setSessionOffset(0); setSessionReload((value) => value + 1); }}>Ver resultado</Button><Button variant="ghost" onClick={() => { setDeleteTarget(run); setDeleteError(null); setDeleting(true); }}>Borrar</Button></div></td></tr>)}</tbody></table></div>
        <nav className="reference-pagination" aria-label="Paginación de corridas"><span>{formatNumber(runs.total)} corridas</span><div><Button disabled={runOffset === 0} onClick={() => setRunOffset(Math.max(0, runOffset - RUN_PAGE_SIZE))}>Anterior</Button><Button disabled={runOffset + RUN_PAGE_SIZE >= runs.total} onClick={() => setRunOffset(runOffset + RUN_PAGE_SIZE)}>Siguiente</Button></div></nav>
      </>}
    </section>

    {sessionError && <ErrorBanner cause="No pudimos cargar el resultado guardado." recovery={sessionError} actionLabel="Reintentar" onAction={() => setSessionReload((value) => value + 1)} />}
    {selectedRunId && !sessionError && (!selectedRun || !sessionPage) && <Loading label="Cargando resultado guardado…" rows={4} />}
    {selectedRun && sessionPage && totals && <section className="reference-result" aria-labelledby="reference-result-title">
      <h3 id="reference-result-title">Resultado guardado</h3>
      <p>Fuente usada · SHA-256 <span className="reference-sha">{selectedRun.provenance.history_sha256}</span></p>
      <div className="reference-result-stats"><div><span>Neto total</span><strong>{money(totals.total_net)}</strong></div><div><span>Sesiones cerradas</span><strong>{formatNumber(totals.completed)}</strong></div><div><span>Metas</span><strong>{formatNumber(totals.goals)}</strong></div><div><span>Quiebras</span><strong>{formatNumber(totals.ruins)}</strong></div><div><span>Incompletas</span><strong>{formatNumber(totals.incomplete)}</strong></div><div><span>Media neta de cerradas</span><strong>{totals.mean_net_closed === null ? "No disponible" : `${totals.mean_net_closed < 0 ? "−" : "+"}RD$${formatNumber(Math.abs(totals.mean_net_closed))}`}</strong></div><div><span>Apostado</span><strong>{money(totals.total_wagered)}</strong></div><div><span>Pagado</span><strong>{money(totals.total_paid)}</strong></div></div>
      {totals.incomplete > 0 && <p className="reference-note">Las sesiones incompletas aportan a los totales de dinero, pero no al promedio neto de sesiones cerradas.</p>}
      {!selectedRun.capabilities.per_bet_trace && <p className="reference-note">Este contrato guarda resúmenes de sesión; no incluye el detalle de cada apuesta ni una trayectoria gráfica.</p>}
      <div className="reference-section-heading"><div><h4>Sesiones {formatNumber(sessionPage.offset + 1)}–{formatNumber(Math.min(sessionPage.offset + sessionPage.items.length, sessionPage.total))} de {formatNumber(sessionPage.total)}</h4><p>Se consulta solo esta página de resúmenes.</p></div></div>
      {sessionPage.items.length === 0 ? <p className="reference-empty">Esta corrida no tiene sesiones en esta página.</p> : <div className="reference-table-wrap" role="region" aria-label="Resúmenes de sesiones" tabIndex={0}><table className="reference-table"><thead><tr><th scope="col">Sesión</th><th scope="col">Cierre</th><th scope="col">Sorteos</th><th scope="col">Saldo final</th><th scope="col">Apostado</th><th scope="col">Pagado</th></tr></thead><tbody>{sessionPage.items.map(({ ordinal, summary }) => <tr key={ordinal}><th scope="row">{formatNumber(ordinal + 1)}</th><td>{outcomeLabel(summary.outcome)}</td><td>{formatNumber(summary.draws)}</td><td>{money(summary.final_balance)}</td><td>{money(summary.wagered)}</td><td>{money(summary.paid)}</td></tr>)}</tbody></table></div>}
      <nav className="reference-pagination" aria-label="Paginación de sesiones"><span>{formatNumber(sessionPage.total)} sesiones · página de {SESSION_PAGE_SIZE}</span><div><Button disabled={sessionOffset === 0} onClick={() => setSessionOffset(Math.max(0, sessionOffset - SESSION_PAGE_SIZE))}>Anterior</Button><Button disabled={sessionOffset + SESSION_PAGE_SIZE >= sessionPage.total} onClick={() => setSessionOffset(sessionOffset + SESSION_PAGE_SIZE)}>Siguiente</Button></div></nav>
    </section>}
    {deleteError && <div className="reference-action-error" role="alert"><p>{deleteError}</p><Button onClick={() => setDeleteError(null)}>Cerrar</Button></div>}
    <ConfirmDialog open={deleting && !!deleteTarget} title="Borrar corrida guardada" description="Se eliminará esta reproducción del laboratorio. Esta acción no se puede deshacer." confirmLabel={deleteBusy ? "Borrando…" : "Borrar"} onCancel={() => { if (!deleteBusy) { setDeleting(false); setDeleteTarget(null); } }} onConfirm={() => void confirmDelete()} />
  </section>;
}
type SessionPage = ReferenceSessionPage;
