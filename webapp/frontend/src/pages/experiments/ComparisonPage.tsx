import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import { isProfileBatchRun, isProfileExperiment, isProfileRun } from "../../api/types";
import type { AnyRunSummary, CompareResult, ExperimentSummary, Trajectory } from "../../api/types";
import { ComparisonChart } from "../../components/ComparisonChart";
import type { ComparisonSeries } from "../../components/ComparisonChart";
import { RunTrajectory } from "../../components/RunTrajectory";
import { metricRatio } from "../../components/FinancialMetrics";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { formatDOP } from "../../lib/format";
import { profileBatchOutcome, profileMoney, profileOutcome } from "../../lib/profile-display";
import { FIELD_LABEL_DELTA, HISTORICAL_CAVEAT } from "../../lib/ui-labels";

type SavedView = { hidden: number[] };
function storageKey(id: string) { return `comparison-view:${id}`; }
function readView(id: string): SavedView {
  try {
    const raw = sessionStorage.getItem(storageKey(id));
    if (!raw || raw.length > 300000) return { hidden: [] };
    const parsed = JSON.parse(raw);
    return { hidden: Array.isArray(parsed?.hidden) ? parsed.hidden.filter((n: unknown) => typeof n === "number" && Number.isInteger(n) && n >= 0 && n < 5).slice(0, 5) : [] };
  } catch { return { hidden: [] }; }
}
function saveView(id: string, view: SavedView) {
  try { sessionStorage.setItem(storageKey(id), JSON.stringify({ hidden: view.hidden.slice(0, 5) })); } catch { /* View remains available in memory. */ }
}
function errorText(cause: unknown) {
  if (cause instanceof NetworkError) return "No se pudo contactar al servidor. Esto no detiene la ejecución.";
  if (cause instanceof ApiError && cause.status === 404) return "Este experimento no existe o fue eliminado.";
  return "No se pudo consultar la comparación. Reintentá.";
}
function nonterminal(status: string) { return status === "pending" || status === "held" || status === "running"; }
function stopLabel(category: string) {
  return ({ financial_goal: "Meta financiera alcanzada", financial_ruin: "Quiebre financiero", recovery_end: "Fin de escalera de recuperación", interrupted: "Interrumpida", configured_limit: "Límite configurado", operational_budget: "Límite operativo; fuente incompleta", operational_window: "Ventana operativa; fuente incompleta", source_end: "Fin de la fuente guardada", unknown: "Cierre no disponible" } as Record<string, string>)[category] ?? "Cierre no reconocido";
}
function comparisonTitle(detail: ExperimentSummary) {
  if ("request_schema_version" in detail && detail.request_schema_version === 5) return detail.display.name;
  if (isProfileExperiment(detail)) return detail.display.name;
  return detail.request.name;
}
function comparisonName(detail: ExperimentSummary, ordinal: number) {
  if ("request_schema_version" in detail && detail.request_schema_version === 5) return detail.request.strategies[ordinal]?.name ?? `Ejecución ${ordinal + 1}`;
  if (isProfileExperiment(detail)) return detail.display.name;
  return detail.request.strategies[ordinal]?.name ?? `Ejecución ${ordinal + 1}`;
}

interface Paired { detail: ExperimentSummary; comparison: CompareResult }
export function ComparisonPage() {
  const { id = "" } = useParams();
  const [pair, setPair] = useState<Paired | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<SavedView>(() => readView(id));
  const [trajectories, setTrajectories] = useState<{ id: string; runs: Record<number, Trajectory> }>({ id, runs: {} });
  const onTrajectory = useCallback((ordinal: number, trajectory: Trajectory) => {
    setTrajectories((current) => ({ id, runs: { ...(current.id === id ? current.runs : {}), [ordinal]: trajectory } }));
  }, [id]);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    setPair(null); setError(""); setView(readView(id));
    async function load() {
      try {
        const [detail, comparison] = await Promise.all([apiClient.getExperiment(id), apiClient.compareExperiment(id)]);
        if (!live || detail.id !== id || comparison.id !== id) return;
        setPair({ detail, comparison }); setError("");
        if (nonterminal(comparison.status)) timer = setTimeout(load, 5000);
      } catch (cause) {
        if (!live) return;
        setError(errorText(cause));
        if (!(cause instanceof ApiError && cause.status === 404)) timer = setTimeout(load, 5000);
      }
    }
    void load();
    return () => { live = false; clearTimeout(timer); };
  }, [id, retry]);
  const data = pair?.detail.id === id && pair.comparison.id === id ? pair : null;
  function updateView(next: SavedView) { setView(next); saveView(id, next); }
  const runs = data?.comparison.runs.slice().sort((a, b) => a.ordinal - b.ordinal) ?? [];
  const batchDetail = data && "request_schema_version" in data.detail && data.detail.request_schema_version === 5 ? data.detail : null;
  const profileDetail = data && isProfileExperiment(data.detail) && !("request_schema_version" in data.detail) ? data.detail : null;
  const profileContext = profileDetail ?? batchDetail;
  const names = (ordinal: number) => data ? comparisonName(data.detail, ordinal) : `Ejecución ${ordinal + 1}`;
  const money = profileContext ? (amount: number) => profileMoney(profileContext, amount) : formatDOP;
  const missingMetric = () => batchDetail ? "N/A" : "—";
  const columns: DataTableColumn<AnyRunSummary>[] = [
    { key: "strategy", header: "Estrategia", render: (run) => <Link className="btn btn-tertiary" to={`/experimentos/${encodeURIComponent(id)}?run=${run.ordinal}&from=comparison`} aria-label={`Detalle de ${names(run.ordinal)}`}>{names(run.ordinal)}</Link> },
    { key: "status", header: "Estado", render: (run) => <StatusLabel kind="execution" value={run.status} /> },
    { key: "balance", header: "Saldo final", render: (run) => run.result ? money(run.result.final_balance) : missingMetric() },
    { key: "delta", header: FIELD_LABEL_DELTA, render: (run) => run.result ? money(run.result.delta) : missingMetric() },
    { key: "net", header: "Neto", render: (run) => run.result?.net == null ? "N/A" : money(run.result.net) },
    { key: "outcome", header: "Motivo de cierre", render: (run) => run.result ? isProfileRun(run) ? isProfileBatchRun(run) ? profileBatchOutcome(run.result) : profileOutcome(run.result) : <StatusLabel kind="outcome" value={run.result.outcome} /> : missingMetric() },
    { key: "wagered", header: "Total apostado", render: (run) => run.result ? money(run.result.wagered) : missingMetric() },
    { key: "paid", header: "Total pagado", render: (run) => run.result ? money(run.result.paid) : missingMetric() },
    { key: "return", header: "Retorno por peso", render: (run) => metricRatio(run.result?.return_per_wagered) },
    { key: "roi", header: "ROI neto", render: (run) => metricRatio(run.result?.roi) },
    { key: "drawdown", header: "Drawdown absoluto", render: (run) => run.result?.max_drawdown == null ? "N/A" : money(run.result.max_drawdown) },
    { key: "bets", header: profileContext ? "Sorteos apostados" : "Apuestas realizadas", render: (run) => run.result ? isProfileRun(run) ? run.result.bet_draws : run.result.bets_count : missingMetric() },
    ...(profileContext ? [{ key: "elapsed", header: "Sorteos transcurridos", render: (run: AnyRunSummary) => isProfileRun(run) && run.result ? run.result.elapsed_draws : missingMetric() }] : []),
    ...(batchDetail ? [{ key: "stop", header: "Motivo de parada", render: (run: AnyRunSummary) => isProfileBatchRun(run) ? `${stopLabel(run.stop_category)} · ${run.stop_reason}${run.error ? ` · ${run.error}` : ""}` : "N/A" }] : []),
  ];
  const series: ComparisonSeries[] = runs.filter((run) => run.status === "completed" && !!run.result).map((run) => ({ ordinal: run.ordinal, name: names(run.ordinal), visible: !view.hidden.includes(run.ordinal), total: isProfileRun(run) ? run.result!.bet_draws : run.result!.bets_count, points: trajectories.id === id ? (trajectories.runs[run.ordinal]?.points ?? []).map((point) => ({ ordinal: point.bet_index == null ? point.source_index + 1 : point.bet_index + 1, label: point.label, balance: point.balance })) : [], reductionMethod: trajectories.id === id ? trajectories.runs[run.ordinal]?.reduction_method : undefined, initialCapital: data?.detail.request.conditions.capital, startLabel: data?.detail.request.conditions.start_draw }));
  return <div className="min-w-0 space-y-7">
    <Link to="/experimentos" className="btn btn-tertiary">Volver a Experimentos</Link>
    {!data && !error && <p role="status">Cargando comparación…</p>}
    {error && <p role="alert">{error} <button type="button" className="btn btn-tertiary" onClick={() => setRetry((n) => n + 1)}>Reintentar comparación</button></p>}
    {data && <>
      <div className="border-b border-border pb-5"><h2 className="font-heading text-2xl">{comparisonTitle(data.detail)}</h2><p className="mt-2 text-sm">{data.comparison.complete ? "Comparación completa" : "Comparación incompleta"} · {data.comparison.completed}/{data.comparison.requested} terminadas</p>
        <p className="mt-2 text-sm text-text-secondary">Estado: <StatusLabel kind="execution" value={data.comparison.status} />{nonterminal(data.comparison.status) ? " · Se actualiza solo." : ""}</p>
      </div>
      <section aria-label="Desenlaces guardados" className="space-y-3"><h3 className="section-header">Desenlaces</h3>
        {!data.comparison.complete && <p role="status" className="text-sm">Resultado incompleto · {data.comparison.completed}/{data.comparison.requested}</p>}
        {runs.map((run) => <article key={run.ordinal} className="border-b border-border pb-4">
          <h4 className="font-heading text-lg"><Link className="link" to={`/experimentos/${encodeURIComponent(id)}?run=${run.ordinal}&from=comparison`}>{names(run.ordinal)}</Link></h4>
          <dl className="data-list">
            <dt>Saldo final</dt><dd>{run.result ? money(run.result.final_balance) : missingMetric()}</dd>
            <dt>Neto</dt><dd>{run.result?.net == null ? "N/A" : money(run.result.net)}</dd>
            <dt>Motivo de cierre</dt><dd>{run.result ? isProfileRun(run) ? isProfileBatchRun(run) ? profileBatchOutcome(run.result) : profileOutcome(run.result) : <StatusLabel kind="outcome" value={run.result.outcome} /> : missingMetric()}</dd>
          </dl>
        </article>)}
        <details><summary className="disclosure-summary">Comparación detallada</summary><div className="pt-2"><DataTable caption="Comparación de ejecuciones" columns={columns} rows={runs} getRowKey={(run) => String(run.ordinal)} /></div></details>
        <details><summary className="disclosure-summary">Detalles técnicos</summary><div className="space-y-2 pt-2"><p className="field-help">Métricas del backend por corrida guardada; ratios adimensionales, redondeo HALF_UP a seis decimales. Denominador cero: N/A. Drawdown desde el capital inicial. Un resultado guardado no completa un lote con otras corridas pendientes.</p><dl className="data-list break-all"><dt>Versión de solicitud</dt><dd>{profileDetail ? `Perfil v${profileDetail.request.schema_version}` : batchDetail ? `Perfil v${batchDetail.request.schema_version}` : "No disponible"}</dd>{runs.map((run) => <Fragment key={run.ordinal}><dt>Resultado · {names(run.ordinal)}</dt><dd>{isProfileRun(run) && run.result ? `Perfil v${run.result.schema_version}` : "No disponible"}</dd>{batchDetail && isProfileBatchRun(run) && <><dt>Parada · {names(run.ordinal)}</dt><dd>{run.stop_category} · {run.stop_code} · {run.stop_reason}</dd></>}</Fragment>)}</dl></div></details>
        <p className="text-sm text-text-secondary">{profileContext ? "Simulación con datos del conjunto seleccionado: no predice resultados futuros ni garantiza rentabilidad." : HISTORICAL_CAVEAT}</p>
      </section>
      <section className="min-w-0 space-y-4"><ComparisonChart series={series} formatMoney={money} onToggle={(ordinal) => updateView({ ...view, hidden: view.hidden.includes(ordinal) ? view.hidden.filter((n) => n !== ordinal) : [...view.hidden, ordinal] })} />
        {runs.filter((run) => run.status === "completed" && !!run.result).map((run) => <RunTrajectory key={`${id}:${run.ordinal}`} id={id} ordinal={run.ordinal} name={names(run.ordinal)} money={money} goal={data.detail.request.conditions.goal} chart={false} onLoad={onTrajectory} />)}
      </section>
      <details className="space-y-3 text-sm"><summary className="disclosure-summary">Detalles técnicos · condiciones y datos de origen</summary>
        <dl className="data-list break-all">
          <dt>Sorteo inicial</dt><dd>{data.detail.request.conditions.start_draw}</dd>
          <dt>Capital</dt><dd className="data-list-numeric">{money(isProfileExperiment(data.detail) ? data.detail.display.capital : data.detail.request.conditions.capital)}</dd>
          <dt>Meta de referencia</dt><dd className="data-list-numeric">{money(isProfileExperiment(data.detail) ? data.detail.display.goal : data.detail.request.conditions.goal)}</dd>
          <dt>{profileContext ? "Datos de origen" : "Historial"}</dt><dd className="font-mono">{data.detail.sources.history_id}</dd><dt>{profileContext ? "SHA-256 de datos de origen" : "SHA-256 historial"}</dt><dd className="font-mono">{data.detail.sources.history_sha256}</dd>
          {isProfileExperiment(data.detail) ? <>{data.detail.request.schema_version === 4 && <><dt>Margen objetivo</dt><dd>{profileMoney(data.detail, data.detail.request.staking.target_margin)}</dd><dt>Rondas de recuperación</dt><dd>{data.detail.request.staking.rounds}</dd><dt>Al agotar la escalera</dt><dd>{data.detail.request.staking.end_mode === "cycle" ? "Reiniciar la escalera" : "Detener la sesión"}</dd></>}<dt>Perfil</dt><dd>{data.detail.profile.profile_id} · revisión {data.detail.profile.revision} · {data.detail.profile.positions} posiciones · {data.detail.display.currency}</dd><dt>Conjunto de datos SHA-256</dt><dd className="font-mono">{data.detail.request.dataset_sha256}</dd></> : <><dt>Rankings</dt><dd className="font-mono">{data.detail.sources.rankings_id}</dd><dt>SHA-256 rankings</dt><dd className="font-mono">{data.detail.sources.rankings_sha256}</dd></>}
          <dt>Versión de código</dt><dd className="font-mono">{data.detail.sources.code_version}</dd>
        </dl>
        {batchDetail && <dl className="data-list break-all border-t border-border pt-4">
          <dt>Perfil congelado</dt><dd>{batchDetail.request.profile_id} · revisión {batchDetail.request.profile_revision} · SHA-256 {batchDetail.request.profile_sha256}</dd>
          <dt>Fuente SHA-256</dt><dd className="font-mono">{batchDetail.batch_admission.source_identity.source_sha256}</dd>
          <dt>Fuente canónica SHA-256</dt><dd className="font-mono">{batchDetail.batch_admission.source_identity.canonical_sha256}</dd>
          <dt>Filas de la fuente guardada</dt><dd>{batchDetail.batch_admission.source_identity.row_count}</dd>
          <dt>Archivo autenticado</dt><dd>{batchDetail.batch_admission.source_identity.archive_bound ? `Verificado · historial ${batchDetail.batch_admission.source_identity.archive_history_sha256} · rankings ${JSON.stringify(batchDetail.batch_admission.source_identity.archive_rank_row_ids)}` : "No aplica a esta fuente"}</dd>
          <dt>Ventana solicitada</dt><dd>{batchDetail.request.max_draws} sorteos máximos · {batchDetail.request.conditions.max_elapsed_draws ?? "sin límite"} transcurridos · {batchDetail.request.conditions.max_bet_draws ?? "sin límite"} apostados</dd>
          <dt>Límites admitidos solicitados</dt><dd><code>{JSON.stringify(batchDetail.batch_admission.requested_constraints)}</code></dd>
          <dt>Límites efectivos guardados</dt><dd><code>{JSON.stringify(batchDetail.batch_admission.effective_constraints)}</code></dd>
          <dt>Política congelada</dt><dd>Revisión {batchDetail.batch_admission.policy_revision} · <code>{JSON.stringify(batchDetail.batch_admission.policy)}</code></dd>
          <dt>Definiciones congeladas</dt><dd>{batchDetail.batch_admission.strategy_refs.map((reference) => `${reference.id} · revisión ${reference.revision} · SHA-256 ${reference.definition_sha256}`).join("; ")}</dd>
        </dl>}
      </details>
    </>}
  </div>;
}
