import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, NetworkError } from "../../api/client";
import {
  createLaboratoryRun, deleteLaboratory, getLaboratory, getLaboratoryRun, listLaboratoryRuns, listLaboratorySessions,
} from "../../api/laboratories";
import type { LaboratoryDetail, LaboratoryRun, LaboratoryRunListItem } from "../../api/laboratories";
import { getReferenceLabs } from "../../api/referenceLabs";
import type { ReferencePage, ReferenceSessionPage } from "../../api/referenceLabs";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Button } from "../../components/ui/Controls";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { stakeLabel, systemLabel } from "../reference-labs/lab-model";
import { count } from "./count";
import { formatMean } from "./mean";
import "../reference-labs/reference-labs.css";

const RUN_PAGE = 20;
const SESSION_PAGE = 50;
const money = (value: number) => formatSignedDOP(value);
const outcomeLabel = (outcome: string) => (outcome === "goal" ? "Meta" : outcome === "ruin" ? "Quiebra" : "Incompleta");
const isAbort = (error: unknown) => error instanceof Error && error.name === "AbortError";
function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof NetworkError) return "No se pudo contactar al servidor local.";
  return "Ocurrió un error inesperado.";
}

interface Props { labId: string; onDeleted: () => void }

export function LaboratoryPanel({ labId, onDeleted }: Props) {
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
  const [sessions, setSessions] = useState<ReferenceSessionPage | null>(null);
  const [sessionOffset, setSessionOffset] = useState(0);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionReload, setSessionReload] = useState(0);
  const [running, setRunning] = useState(false);
  const [uncertain, setUncertain] = useState(false);
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
    getReferenceLabs({ signal: controller.signal }).then((catalog) => { if (current) setHistorySha(catalog.reference_history.sha256); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setHistoryError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, []);

  const reloadRuns = useCallback(() => setRunReload((value) => value + 1), []);
  useEffect(() => {
    if (!detail) return;
    const controller = new AbortController(); let current = true;
    setRunsError(null);
    listLaboratoryRuns(labId, { offset: runOffset, limit: RUN_PAGE }, { signal: controller.signal }).then((page) => { if (current) setRuns(page); })
      .catch((error: unknown) => { if (current && !isAbort(error)) setRunsError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, [detail, labId, runOffset, runReload]);

  useEffect(() => {
    if (!selectedId) { setSelected(null); setSessions(null); return; }
    const controller = new AbortController(); let current = true;
    setSelected(null); setSessions(null); setSessionError(null);
    Promise.all([
      getLaboratoryRun(labId, selectedId, { signal: controller.signal }),
      listLaboratorySessions(labId, selectedId, { offset: sessionOffset, limit: SESSION_PAGE }, { signal: controller.signal }),
    ]).then(([run, page]) => { if (current) { setSelected(run); setSessions(page); } })
      .catch((error: unknown) => { if (current && !isAbort(error)) setSessionError(errorText(error)); });
    return () => { current = false; controller.abort(); };
  }, [labId, selectedId, sessionOffset, sessionReload]);

  async function execute() {
    if (!historySha || running || uncertain) return;
    setRunning(true); setActionError(null);
    const controller = new AbortController(); runAbort.current = controller;
    try {
      const run = await createLaboratoryRun(labId, historySha, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setSelectedId(run.id); setSessionOffset(0); setRunOffset(0); reloadRuns(); setDetailReload((value) => value + 1);
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

  return <section className="reference-page" aria-labelledby="lab-title">
    <header className="reference-heading">
      <div><h2 id="lab-title">{definition.name}</h2><p>{systemLabel(config.system)} · {config.coverage} {config.coverage === 1 ? "número" : "números"} · {stakeLabel(config.stake_style)}</p></div>
      <Button variant="ghost" onClick={() => { setDeleteError(null); setConfirmDelete(true); }}>Eliminar laboratorio</Button>
    </header>
    {deleteError && <div className="reference-action-error" role="alert"><p>{deleteError}</p><Button onClick={() => setDeleteError(null)}>Cerrar</Button></div>}

    <section className="reference-contract" aria-label="Reglas del laboratorio">
      <h3>Reglas fijadas</h3>
      <dl className="reference-contract-grid">
        <div><dt>Selección</dt><dd>{systemLabel(config.system)}</dd></div>
        <div><dt>Cobertura</dt><dd>{config.coverage} de 50 números</dd></div>
        <div><dt>Estilo de apuesta</dt><dd>{stakeLabel(config.stake_style)}</dd></div>
        <div><dt>Capital inicial</dt><dd>{money(config.capital)}</dd></div>
        <div><dt>Meta de saldo</dt><dd>{money(config.goal)}</dd></div>
        <div><dt>Premios</dt><dd>{config.prizes.map((prize, index) => `${index + 1}.º ${money(prize)}`).join(" · ")}</dd></div>
        <div><dt>Ventana</dt><dd>{config.window_start} – {config.window_end}</dd></div>
        <div><dt>Corridas guardadas</dt><dd>{formatNumber(detail.owned_run_count)}</dd></div>
      </dl>
    </section>

    <div className="reference-run-action">
      <Button variant="primary" onClick={() => void execute()} loading={running} disabled={!historySha || uncertain || !runs || !!runsError}>Ejecutar laboratorio</Button>
      {historyError && <span>{`No se pudo leer la fuente congelada: ${historyError}`}</span>}
    </div>
    {actionError && <div className="reference-action-error" role="alert"><p>{actionError}</p>{uncertain && <Button onClick={() => { setUncertain(false); setActionError(null); setSelectedId(null); setRunOffset(0); reloadRuns(); setDetailReload((value) => value + 1); }}>Actualizar corridas guardadas</Button>}</div>}

    <section className="reference-runs" aria-labelledby="lab-runs-title">
      <div className="reference-section-heading"><div><h3 id="lab-runs-title">Corridas guardadas</h3></div><Button onClick={reloadRuns}>Actualizar</Button></div>
      {runsError ? <ErrorBanner cause="No pudimos cargar las corridas guardadas." recovery={runsError} actionLabel="Reintentar" onAction={reloadRuns} />
        : !runs ? <Loading label="Cargando corridas guardadas…" rows={3} />
        : runs.items.length === 0 ? <p className="reference-empty">Todavía no hay corridas guardadas para este laboratorio.</p>
        : <>
          <div className="reference-table-wrap" role="region" aria-label="Corridas guardadas" tabIndex={0}><table className="reference-table"><thead><tr><th scope="col">Creada</th><th scope="col">Sesiones</th><th scope="col">Neto total</th><th scope="col">Acciones</th></tr></thead><tbody>
            {runs.items.map((run) => <tr key={run.id}><td>{new Date(run.created_at).toLocaleString("es-DO")}</td><td>{formatNumber(run.summary.totals.sessions_total)} · {count(run.summary.totals.incomplete, "incompleta", "incompletas")}</td><td>{money(run.summary.totals.total_net)}</td><td><Button aria-pressed={selectedId === run.id} onClick={() => { setSelectedId(run.id); setSessionOffset(0); setSessionReload((value) => value + 1); }}>Ver resultado</Button></td></tr>)}
          </tbody></table></div>
          <nav className="reference-pagination" aria-label="Paginación de corridas"><span>{count(runs.total, "corrida", "corridas")}</span><div><Button disabled={runOffset === 0} onClick={() => setRunOffset(Math.max(0, runOffset - RUN_PAGE))}>Anterior</Button><Button disabled={runOffset + RUN_PAGE >= runs.total} onClick={() => setRunOffset(runOffset + RUN_PAGE)}>Siguiente</Button></div></nav>
        </>}
    </section>

    {sessionError && <ErrorBanner cause="No pudimos cargar el resultado guardado." recovery={sessionError} actionLabel="Reintentar" onAction={() => setSessionReload((value) => value + 1)} />}
    {selectedId && !sessionError && (!selected || !sessions) && <Loading label="Cargando resultado guardado…" rows={4} />}
    {selected && sessions && totals && <section className="reference-result" aria-labelledby="lab-result-title">
      <h3 id="lab-result-title">Resultado guardado</h3>
      <p>Fuente usada · SHA-256 <span className="reference-sha">{selected.snapshot.provenance.history_sha256}</span></p>
      <div className="reference-result-stats">
        <div><span>Neto total</span><strong>{money(totals.total_net)}</strong></div>
        <div><span>Sesiones cerradas</span><strong>{formatNumber(totals.completed)}</strong></div>
        <div><span>Metas</span><strong>{formatNumber(totals.goals)}</strong></div>
        <div><span>Quiebras</span><strong>{formatNumber(totals.ruins)}</strong></div>
        <div><span>Incompletas</span><strong>{formatNumber(totals.incomplete)}</strong></div>
        <div><span>Media neta de cerradas</span><strong>{totals.mean_net_closed === null ? "No disponible" : formatMean(totals.mean_net_closed)}</strong></div>
        <div><span>Apostado</span><strong>{money(totals.total_wagered)}</strong></div>
        <div><span>Pagado</span><strong>{money(totals.total_paid)}</strong></div>
      </div>
      <div className="reference-section-heading"><div><h4>Sesiones {formatNumber(sessions.offset + 1)}–{formatNumber(Math.min(sessions.offset + sessions.items.length, sessions.total))} de {formatNumber(sessions.total)}</h4></div></div>
      {sessions.items.length === 0 ? <p className="reference-empty">Esta corrida no tiene sesiones en esta página.</p> : <div className="reference-table-wrap" role="region" aria-label="Resúmenes de sesiones" tabIndex={0}><table className="reference-table"><thead><tr><th scope="col">Sesión</th><th scope="col">Cierre</th><th scope="col">Sorteos</th><th scope="col">Saldo final</th><th scope="col">Apostado</th><th scope="col">Pagado</th></tr></thead><tbody>
        {sessions.items.map(({ ordinal, summary }) => <tr key={ordinal}><th scope="row">{formatNumber(ordinal + 1)}</th><td>{outcomeLabel(summary.outcome)}</td><td>{formatNumber(summary.draws)}</td><td>{money(summary.final_balance)}</td><td>{money(summary.wagered)}</td><td>{money(summary.paid)}</td></tr>)}
      </tbody></table></div>}
      <nav className="reference-pagination" aria-label="Paginación de sesiones"><span>{count(sessions.total, "sesión", "sesiones")} · página de {SESSION_PAGE}</span><div><Button disabled={sessionOffset === 0} onClick={() => setSessionOffset(Math.max(0, sessionOffset - SESSION_PAGE))}>Anterior</Button><Button disabled={sessionOffset + SESSION_PAGE >= sessions.total} onClick={() => setSessionOffset(sessionOffset + SESSION_PAGE)}>Siguiente</Button></div></nav>
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
