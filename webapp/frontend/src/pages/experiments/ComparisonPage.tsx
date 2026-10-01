import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient, ApiError, NetworkError } from "../../api/client";
import type { Bet, CompareResult, ExperimentSummary, RunSummary } from "../../api/types";
import { ComparisonChart } from "../../components/ComparisonChart";
import type { ComparisonPoint, ComparisonSeries } from "../../components/ComparisonChart";
import { DataTable } from "../../components/DataTable";
import type { DataTableColumn } from "../../components/DataTable";
import { StatusLabel } from "../../components/StatusLabel";
import { formatDOP } from "../../lib/format";
import { FIELD_LABEL_DELTA, HISTORICAL_CAVEAT } from "../../lib/ui-labels";

const PAGE = 100;
// Session context is bounded to five series of at most five pages, even if more pages are viewed.
const SAVED_POINTS = 500;
type SavedView = { hidden: number[]; series: Record<number, ComparisonPoint[]> };
function storageKey(id: string) { return `comparison-view:${id}`; }
function readView(id: string): SavedView {
  try {
    const raw = sessionStorage.getItem(storageKey(id));
    if (!raw || raw.length > 300000) return { hidden: [], series: {} };
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return { hidden: [], series: {} };
    const view = parsed as SavedView;
    const hidden = Array.isArray(view.hidden) ? view.hidden.filter((n) => Number.isInteger(n) && n >= 0 && n < 5).slice(0, 5) : [];
    const series: SavedView["series"] = {};
    for (let i = 0; i < 5; i++) {
      const points = view.series?.[i];
      if (Array.isArray(points) && points.length <= SAVED_POINTS && points.every((p, index) => p && p.ordinal === index && typeof p.label === "string" && p.label.length < 80 && Number.isFinite(p.balance))) series[i] = points;
    }
    return { hidden, series };
  } catch { return { hidden: [], series: {} }; }
}
function saveView(id: string, view: SavedView) {
  const bounded: SavedView = { hidden: view.hidden.slice(0, 5), series: {} };
  for (let i = 0; i < 5; i++) if (view.series[i]) bounded.series[i] = view.series[i].slice(0, SAVED_POINTS);
  try { sessionStorage.setItem(storageKey(id), JSON.stringify(bounded)); } catch { /* Storage may be unavailable; the view still works in memory. */ }
}
function errorText(cause: unknown) {
  if (cause instanceof NetworkError) return "No se pudo contactar al servidor local. Esto no indica que la ejecución se haya detenido.";
  if (cause instanceof ApiError && cause.status === 404) return "Este experimento no existe o fue eliminado.";
  return "No se pudo consultar la comparación. Probá de nuevo.";
}
function replayError(cause: unknown) {
  if (cause instanceof NetworkError) return "No se pudo contactar al servidor local. Los datos ya cargados siguen visibles.";
  if (cause instanceof ApiError && cause.status === 404) return "La ejecución o el experimento ya no existe.";
  if (cause instanceof ApiError && cause.status === 409) return "La reproducción todavía no está disponible.";
  return "No se pudo cargar esta página. Probá de nuevo.";
}
function nonterminal(status: string) { return status === "pending" || status === "held" || status === "running"; }

interface Paired { detail: ExperimentSummary; comparison: CompareResult }
function SeriesReplay({ id, run, name, saved, onPoints }: { id: string; run: RunSummary; name: string; saved: ComparisonPoint[]; onPoints: (ordinal: number, points: ComparisonPoint[]) => void }) {
  const [points, setPoints] = useState<ComparisonPoint[]>(saved);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const total = run.result?.bets_count ?? 0;
  const offset = points.length;
  useEffect(() => {
    if (!run.result || !total || offset >= total || (offset > 0 && retry === 0)) return;
    let live = true;
    setLoading(true); setError("");
    void apiClient.getReplay(id, run.ordinal, offset, PAGE).then((response) => {
      if (!live) return;
      if (response.offset !== offset || !response.items.length) { setError("La página guardada no coincide con lo solicitado."); setLoading(false); return; }
      const next = [...points, ...response.items.map((bet: Bet, index) => ({ ordinal: offset + index, label: bet.label, balance: bet.balance }))];
      setPoints(next); onPoints(run.ordinal, next); setLoading(false);
    }).catch((cause: unknown) => { if (live) { setError(replayError(cause)); setLoading(false); } });
    return () => { live = false; };
  // Only explicit demand triggers subsequent pages. The initial page is requested on mount.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, run.ordinal, retry]);
  return <div className="flex flex-wrap items-center gap-3 text-sm" aria-label={`Carga de ${name}`}>
    <span>{name}: {points.length}/{total} cargadas</span>
    {loading && <span role="status">Cargando {name}…</span>}
    {error && <span role="alert" aria-label={`Error de ${name}`}>{error} <button type="button" className="text-accent underline" onClick={() => setRetry((n) => n + 1)}>Reintentar {name}</button></span>}
    {!loading && !error && points.length < total && <button type="button" className="btn btn-secondary hover:bg-field" onClick={() => setRetry((n) => n + 1)}>Cargar más de {name}</button>}
  </div>;
}

export function ComparisonPage() {
  const { id = "" } = useParams();
  const [pair, setPair] = useState<Paired | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<SavedView>(() => readView(id));
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
  const names = (ordinal: number) => data?.detail.request.strategies[ordinal]?.name ?? `Ejecución ${ordinal + 1}`;
  const columns: DataTableColumn<RunSummary>[] = [
    { key: "strategy", header: "Estrategia", render: (run) => <Link className="text-accent underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" to={`/experimentos/${encodeURIComponent(id)}?run=${run.ordinal}&from=comparison`} aria-label={`Detalle de ${names(run.ordinal)}`}>{names(run.ordinal)}</Link> },
    { key: "status", header: "Estado de ejecución", render: (run) => <StatusLabel kind="execution" value={run.status} /> },
    { key: "balance", header: "Saldo final", render: (run) => run.result ? formatDOP(run.result.final_balance) : "—" },
    { key: "delta", header: FIELD_LABEL_DELTA, render: (run) => run.result ? formatDOP(run.result.delta) : "—" },
    { key: "bets", header: "Apuestas realizadas", render: (run) => run.result ? run.result.bets_count : "—" },
    { key: "outcome", header: "Motivo de cierre", render: (run) => run.result ? <StatusLabel kind="outcome" value={run.result.outcome} /> : "—" },
  ];
  const series: ComparisonSeries[] = runs.filter((run) => !!run.result).map((run) => ({ ordinal: run.ordinal, name: names(run.ordinal), visible: !view.hidden.includes(run.ordinal), total: run.result!.bets_count, points: view.series[run.ordinal] ?? [] }));
  return <div className="min-w-0 space-y-7">
    <Link to="/experimentos" className="text-sm text-accent underline">Volver a Experimentos</Link>
    {!data && !error && <p role="status">Cargando comparación…</p>}
    {error && <p role="alert">{error} <button type="button" className="text-accent underline" onClick={() => setRetry((n) => n + 1)}>Reintentar comparación</button></p>}
    {data && <>
      <div className="border-b border-border pb-5"><h2 className="font-heading text-2xl">{data.detail.request.name}</h2><p className="mt-2 text-sm">{data.comparison.complete ? "Comparación completa" : "Comparación incompleta"} · {data.comparison.completed}/{data.comparison.requested} terminadas</p>
        <p className="mt-2 text-sm text-text-secondary">ID: <span className="font-mono">{id}</span>. {nonterminal(data.comparison.status) ? "Consultando el progreso guardado; una desconexión no detiene la ejecución." : "Estado guardado del experimento."}</p>
      </div>
      <section className="space-y-3"><h3 className="section-header">Resultados guardados</h3>
        <DataTable caption="Comparación de ejecuciones" columns={columns} rows={runs} getRowKey={(run) => String(run.ordinal)} />
        <p className="text-sm text-text-secondary">{HISTORICAL_CAVEAT}</p>
      </section>
      <section className="min-w-0 space-y-4"><ComparisonChart series={series} onToggle={(ordinal) => updateView({ ...view, hidden: view.hidden.includes(ordinal) ? view.hidden.filter((n) => n !== ordinal) : [...view.hidden, ordinal] })} />
        {runs.filter((run) => !!run.result).map((run) => <SeriesReplay key={`${id}:${run.ordinal}`} id={id} run={run} name={names(run.ordinal)} saved={view.series[run.ordinal] ?? []} onPoints={(ordinal, points) => setView((current) => {
          const next = { ...current, series: { ...current.series, [ordinal]: points } };
          saveView(id, next); return next;
        })} />)}
      </section>
      <section className="space-y-3 text-sm"><h3 className="section-header">Condiciones y datos de origen</h3>
        <dl className="data-list break-all">
          <dt>Sorteo inicial</dt><dd>{data.detail.request.conditions.start_draw}</dd>
          <dt>Capital</dt><dd className="data-list-numeric">{formatDOP(data.detail.request.conditions.capital)}</dd>
          <dt>Meta de referencia</dt><dd className="data-list-numeric">{formatDOP(data.detail.request.conditions.goal)}</dd>
          <dt>Historial</dt><dd className="font-mono">{data.detail.sources.history_id}</dd><dt>SHA-256 historial</dt><dd className="font-mono">{data.detail.sources.history_sha256}</dd>
          <dt>Rankings</dt><dd className="font-mono">{data.detail.sources.rankings_id}</dd><dt>SHA-256 rankings</dt><dd className="font-mono">{data.detail.sources.rankings_sha256}</dd>
          <dt>Versión de código</dt><dd className="font-mono">{data.detail.sources.code_version}</dd>
        </dl>
        <p className="text-text-secondary">Resultados históricos sobre datos ya investigados: no constituyen validación independiente de rentabilidad.</p>
      </section>
    </>}
  </div>;
}
