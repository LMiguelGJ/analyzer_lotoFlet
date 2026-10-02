import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import { isProfileExperiment, isProfileRun } from "../../api/types";
import type { AnyRunSummary, CompareResult, ExperimentSummary, Trajectory } from "../../api/types";
import { ComparisonChart } from "../../components/ComparisonChart";
import type { ComparisonSeries } from "../../components/ComparisonChart";
import { RunTrajectory } from "../../components/RunTrajectory";
import { metricRatio } from "../../components/FinancialMetrics";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { formatDOP } from "../../lib/format";
import { profileMoney, profileOutcome } from "../../lib/profile-display";
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
  if (cause instanceof NetworkError) return "No se pudo contactar al servidor local. Esto no indica que la ejecución se haya detenido.";
  if (cause instanceof ApiError && cause.status === 404) return "Este experimento no existe o fue eliminado.";
  return "No se pudo consultar la comparación. Probá de nuevo.";
}
function nonterminal(status: string) { return status === "pending" || status === "held" || status === "running"; }

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
  const names = (ordinal: number) => data && isProfileExperiment(data.detail) ? data.detail.display.name : data && !isProfileExperiment(data.detail) ? data.detail.request.strategies[ordinal]?.name ?? `Ejecución ${ordinal + 1}` : `Ejecución ${ordinal + 1}`;
  const profileDetail = data && isProfileExperiment(data.detail) ? data.detail : null;
  const money = profileDetail ? (amount: number) => profileMoney(profileDetail, amount) : formatDOP;
  const columns: DataTableColumn<AnyRunSummary>[] = [
    { key: "strategy", header: "Estrategia", render: (run) => <Link className="text-accent underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" to={`/experimentos/${encodeURIComponent(id)}?run=${run.ordinal}&from=comparison`} aria-label={`Detalle de ${names(run.ordinal)}`}>{names(run.ordinal)}</Link> },
    { key: "status", header: "Estado de ejecución", render: (run) => <StatusLabel kind="execution" value={run.status} /> },
    { key: "balance", header: "Saldo final", render: (run) => run.result ? money(run.result.final_balance) : "—" },
    { key: "delta", header: FIELD_LABEL_DELTA, render: (run) => run.result ? money(run.result.delta) : "—" },
    { key: "wagered", header: "Total apostado", render: (run) => run.result ? money(run.result.wagered) : "—" },
    { key: "paid", header: "Total pagado", render: (run) => run.result ? money(run.result.paid) : "—" },
    { key: "net", header: "Neto", render: (run) => run.result?.net == null ? "N/A" : money(run.result.net) },
    { key: "return", header: "Retorno por peso", render: (run) => metricRatio(run.result?.return_per_wagered) },
    { key: "roi", header: "ROI neto", render: (run) => metricRatio(run.result?.roi) },
    { key: "drawdown", header: "Drawdown absoluto", render: (run) => run.result?.max_drawdown == null ? "N/A" : money(run.result.max_drawdown) },
    { key: "bets", header: profileDetail ? "Sorteos apostados" : "Apuestas realizadas", render: (run) => run.result ? isProfileRun(run) ? run.result.bet_draws : run.result.bets_count : "—" },
    ...(profileDetail ? [{ key: "elapsed", header: "Sorteos transcurridos", render: (run: AnyRunSummary) => isProfileRun(run) && run.result ? run.result.elapsed_draws : "—" },
      { key: "schema", header: "Versión del resultado", render: (run: AnyRunSummary) => isProfileRun(run) && run.result ? `Perfil v${run.result.schema_version}` : "—" }] : []),
    { key: "outcome", header: "Motivo de cierre", render: (run) => run.result ? isProfileRun(run) ? profileOutcome(run.result) : <StatusLabel kind="outcome" value={run.result.outcome} /> : "—" },
  ];
  const series: ComparisonSeries[] = runs.filter((run) => !!run.result).map((run) => ({ ordinal: run.ordinal, name: names(run.ordinal), visible: !view.hidden.includes(run.ordinal), total: isProfileRun(run) ? run.result!.bet_draws : run.result!.bets_count, points: trajectories.id === id ? (trajectories.runs[run.ordinal]?.points ?? []).map((p) => ({ ordinal: p.source_index + 1, label: p.label, balance: p.balance })) : [], reductionMethod: trajectories.id === id ? trajectories.runs[run.ordinal]?.reduction_method : undefined, initialCapital: data?.detail.request.conditions.capital, startLabel: data?.detail.request.conditions.start_draw }));
  return <div className="min-w-0 space-y-7">
    <Link to="/experimentos" className="text-sm text-accent underline">Volver a Experimentos</Link>
    {!data && !error && <p role="status">Cargando comparación…</p>}
    {error && <p role="alert">{error} <button type="button" className="text-accent underline" onClick={() => setRetry((n) => n + 1)}>Reintentar comparación</button></p>}
    {data && <>
      <div className="border-b border-border pb-5"><h2 className="font-heading text-2xl">{profileDetail ? profileDetail.display.name : data.detail.request.name}</h2><p className="mt-2 text-sm">{data.comparison.complete ? "Comparación completa" : "Comparación incompleta"} · {data.comparison.completed}/{data.comparison.requested} terminadas</p>
        <p className="mt-2 text-sm text-text-secondary">ID: <span className="font-mono">{id}</span>. {nonterminal(data.comparison.status) ? "Consultando el progreso guardado; una desconexión no detiene la ejecución." : "Estado guardado del experimento."}</p>
      </div>
      <section className="space-y-3"><h3 className="section-header">Resultados guardados</h3>
        <DataTable caption="Comparación de ejecuciones" columns={columns} rows={runs} getRowKey={(run) => String(run.ordinal)} />
        <p className="field-help">Métricas del backend por corrida guardada; ratios adimensionales, redondeo HALF_UP a seis decimales. Denominador cero: N/A. Drawdown desde el capital inicial. Un resultado guardado no completa un lote con otras corridas pendientes.</p>
        <p className="text-sm text-text-secondary">{profileDetail ? "Simulación con datos del conjunto seleccionado: no predice resultados futuros ni garantiza rentabilidad." : HISTORICAL_CAVEAT}</p>
      </section>
      <section className="min-w-0 space-y-4"><ComparisonChart series={series} formatMoney={money} onToggle={(ordinal) => updateView({ ...view, hidden: view.hidden.includes(ordinal) ? view.hidden.filter((n) => n !== ordinal) : [...view.hidden, ordinal] })} />
        {runs.filter((run) => !!run.result).map((run) => <RunTrajectory key={`${id}:${run.ordinal}`} id={id} ordinal={run.ordinal} name={names(run.ordinal)} money={money} goal={data.detail.request.conditions.goal} chart={false} onLoad={onTrajectory} />)}
      </section>
      <section className="space-y-3 text-sm"><h3 className="section-header">Condiciones y datos de origen</h3>
        <dl className="data-list break-all">
          <dt>Sorteo inicial</dt><dd>{data.detail.request.conditions.start_draw}</dd>
          <dt>Capital</dt><dd className="data-list-numeric">{money(isProfileExperiment(data.detail) ? data.detail.display.capital : data.detail.request.conditions.capital)}</dd>
          <dt>Meta de referencia</dt><dd className="data-list-numeric">{money(isProfileExperiment(data.detail) ? data.detail.display.goal : data.detail.request.conditions.goal)}</dd>
          <dt>{profileDetail ? "Datos de origen" : "Historial"}</dt><dd className="font-mono">{data.detail.sources.history_id}</dd><dt>{profileDetail ? "SHA-256 de datos de origen" : "SHA-256 historial"}</dt><dd className="font-mono">{data.detail.sources.history_sha256}</dd>
          {isProfileExperiment(data.detail) ? <><dt>Versión de solicitud</dt><dd>Perfil v{data.detail.request.schema_version}</dd>{data.detail.request.schema_version === 4 && <><dt>Margen objetivo</dt><dd>{profileMoney(data.detail, data.detail.request.staking.target_margin)}</dd><dt>Rondas de recuperación</dt><dd>{data.detail.request.staking.rounds}</dd><dt>Al agotar la escalera</dt><dd>{data.detail.request.staking.end_mode === "cycle" ? "Reiniciar la escalera" : "Detener la sesión"}</dd></>}<dt>Perfil</dt><dd>{data.detail.profile.profile_id} · revisión {data.detail.profile.revision} · {data.detail.profile.positions} posiciones · {data.detail.display.currency}</dd><dt>Conjunto de datos SHA-256</dt><dd className="font-mono">{data.detail.request.dataset_sha256}</dd></> : <><dt>Rankings</dt><dd className="font-mono">{data.detail.sources.rankings_id}</dd><dt>SHA-256 rankings</dt><dd className="font-mono">{data.detail.sources.rankings_sha256}</dd></>}
          <dt>Versión de código</dt><dd className="font-mono">{data.detail.sources.code_version}</dd>
        </dl>
        <p className="text-text-secondary">{profileDetail ? "Resultados sobre datos del conjunto seleccionado: no constituyen una validación independiente de rentabilidad ni una probabilidad de éxito." : "Resultados históricos sobre datos ya investigados: no constituyen validación independiente de rentabilidad."}</p>
      </section>
    </>}
  </div>;
}
