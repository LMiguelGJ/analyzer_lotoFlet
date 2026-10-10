import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { getRun, getRunOptions } from "../../api/runs";
import type { RunOptions, RunReport } from "../../api/types";
import { formatNumber, formatSignedDOP } from "../../lib/format";
import { ErrorBanner, Loading } from "../../components/ui/Feedback";
import { detailStatusCopy, formatResultStrategy, historyOriginLabel, resultSummaryRows } from "./result-model";
import { RunSessions } from "./RunSessions";
import "./runs.css";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  return "No se pudo contactar al servidor local. Revisá la conexión e intentá de nuevo.";
}
function createdLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat("es-DO", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function ResultPage() {
  const { id = "" } = useParams();
  return <ResultContent key={id} runId={id} />;
}

function ResultContent({ runId }: { runId: string }) {
  const [report, setReport] = useState<RunReport | null>(null);
  const [systems, setSystems] = useState<RunOptions["systems"]>([]);
  const [reportError, setReportError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [catalogReady, setCatalogReady] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setReport(null); setReportError(null); setLoading(true);
    getRun(runId, { signal: controller.signal }).then((loaded) => {
      if (!current) return;
      if (loaded.id !== runId) throw new Error("La respuesta no corresponde a esta corrida.");
      setReport(loaded);
    }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) setReportError(errorMessage(error));
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; controller.abort(); };
  }, [runId, revision]);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    setSystems([]); setCatalogFailed(false); setCatalogReady(false);
    getRunOptions({ signal: controller.signal }).then((options) => {
      if (current) { setSystems(options.systems); setCatalogReady(true); }
    }).catch((error: unknown) => {
      if (current && !(error instanceof Error && error.name === "AbortError")) { setCatalogFailed(true); setCatalogReady(true); }
    });
    return () => { current = false; controller.abort(); };
  }, [runId]);

  if (loading) return <section className="runs-page"><h2>Resultado de corrida</h2><Loading label="Cargando resultado…" rows={5} /></section>;
  if (reportError || !report) return <section className="runs-page" aria-labelledby="result-error-title"><h2 id="result-error-title">Resultado de corrida</h2><ErrorBanner cause="No se pudo cargar esta corrida." recovery={reportError ?? "No recibimos el informe solicitado."} actionLabel="Reintentar" onAction={() => setRevision((value) => value + 1)} /><Link className="link" to="/corridas">Volver a Corridas</Link></section>;

  const { config, summary } = report;
  const totals = summary.totals;
  const strategy = catalogReady ? formatResultStrategy(config.strategy, systems) : "Cargando catálogo de sistemas…";
  const unavailableCatalogEntry = config.strategy.kind === "mix" && config.strategy.components.some(({ system }) => !systems.some((entry) => entry.id === system));
  return <section className="runs-page result-page" aria-labelledby="result-title">
    <header className="runs-heading result-heading"><div><h2 id="result-title">{report.name}</h2><p>{strategy}</p></div><div className="result-actions"><Link className="ledger-button ledger-button-secondary" to="/corridas">Volver a Corridas</Link><Link className="ledger-button ledger-button-primary" to={`/corridas/nueva?base=${encodeURIComponent(report.id)}`}>Repetir con cambios</Link></div></header>

    <section className="result-ledger" aria-labelledby="result-ledger-title"><h3 id="result-ledger-title">Balance de la corrida</h3><table className="result-summary"><tbody>{resultSummaryRows(report).map(([label, value]) => {
      const isNet = label === "Neto";
      const negative = isNet && totals.net < 0;
      return <tr key={label} className={isNet ? "result-net-row" : undefined}><th scope="row">{label}</th><td className={`${isNet ? "result-net-value" : ""} ${negative ? "is-negative" : ""}`.trim()}>{negative && <span className="result-word">Pérdida · </span>}{value}{label === "Neto" && totals.net > 0 && <span className="result-word"> · ganancia</span>}{label === "Retorno sobre lo apostado" && totals.return_pct !== null && <span className="result-word">{totals.return_pct < 0 ? " · retorno negativo" : totals.return_pct > 0 ? " · retorno positivo" : " · sin retorno"}</span>}</td></tr>;
    })}</tbody></table><p className="result-incomplete-note">El neto total incluye las sesiones incompletas. El neto medio usa solo sesiones cerradas.</p></section>

    <section className="result-config" aria-labelledby="result-config-title"><h3 id="result-config-title">Reglas y procedencia guardadas</h3><dl>
      <div><dt>Reglas</dt><dd>{config.rules.positions} posiciones · premios {config.rules.prizes.map((prize) => formatSignedDOP(prize)).join(" / ")} · números 00–99 · se permiten repeticiones</dd></div>
      <div><dt>Apuesta mínima</dt><dd>{formatSignedDOP(config.rules.minimum_stake)} por número</dd></div>
      <div><dt>Estrategia y cobertura</dt><dd>{strategy}</dd></div>
      <div><dt>Condiciones</dt><dd>Capital {formatSignedDOP(config.conditions.capital)} · meta {formatSignedDOP(config.conditions.goal)} · duración máxima {config.conditions.max_draws === null ? "sin límite" : `${formatNumber(config.conditions.max_draws)} sorteos`}</dd></div>
      <div><dt>Ventana solicitada</dt><dd>{config.window.start_date ?? "Inicio disponible"} – {config.window.end_date ?? "Fin disponible"}</dd></div>
      <div><dt>Fuente del historial</dt><dd>{historyOriginLabel(config.history.origin)} · SHA-256 <span className="runs-sha">{config.history.sha256}</span></dd></div>
      <div><dt>Ventana efectiva</dt><dd>{summary.window.first_label} – {summary.window.last_label}; {formatNumber(summary.window.draws)} sorteos evaluados</dd></div>
      <div><dt>Cobertura de rankings</dt><dd>{formatNumber(summary.window.ranked_draws)} de {formatNumber(summary.window.draws)} sorteos tienen ranking. La mezcla solo opera donde hay ranking; Paridad usa toda la ventana.</dd></div>
      <div><dt>Motor y fecha</dt><dd>Motor v{summary.engine_version} · corrida creada {createdLabel(report.created_at)}</dd></div>
    </dl>
    {catalogFailed && <p className="runs-warning">No se pudo cargar el catálogo actual. Los sistemas desconocidos se muestran como “Sistema no disponible”, sin exponer sus identificadores.</p>}
    {!catalogFailed && unavailableCatalogEntry && <p className="runs-warning">Uno o más sistemas guardados ya no están disponibles en el catálogo; se muestran como “Sistema no disponible”.</p>}
    <p className="runs-warning">Este informe describe lo ocurrido en el historial. No es una predicción ni garantiza resultados futuros.</p>
    <p className="result-detail-status">{detailStatusCopy(summary.detail)}</p>
    <p className="result-storage-cap">Límites de almacenamiento: {formatNumber(summary.detail.limits.sessions)} sesiones, {formatNumber(summary.detail.limits.bets)} apuestas y {formatNumber(summary.detail.limits.bytes)} bytes.</p>
    </section>

    <RunSessions key={runId} runId={runId} />
  </section>;
}
