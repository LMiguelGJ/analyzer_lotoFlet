import type { PersistedRunConfig, RunDetail, RunOptions, RunReport } from "../../api/types";
import { formatNumber, formatPercent, formatSignedDOP } from "../../lib/format";

export function formatResultStrategy(strategy: PersistedRunConfig["strategy"], systems: RunOptions["systems"]): string {
  if (strategy.kind === "parity") return `Paridad · cobertura ${strategy.coverage}`;
  const components = strategy.components.map(({ system, percent }) => {
    const label = systems.find((candidate) => candidate.id === system)?.label ?? "Sistema no disponible";
    return `${label} ${formatNumber(percent)} %`;
  });
  return `Mezcla · ${components.length ? components.join(" + ") : "Rankings no disponibles"} · cobertura ${strategy.coverage}`;
}

function formatMeanDOP(value: number): string {
  const sign = value < 0 ? "−" : "+";
  return `${sign}RD$${formatNumber(Math.abs(value))}`;
}

export type ResultSummaryRow = [string, string];
export function resultSummaryRows(report: RunReport): ResultSummaryRow[] {
  const { totals, window } = report.summary;
  return [
    ["Apostado", formatSignedDOP(totals.wagered)],
    ["Pagado", formatSignedDOP(totals.paid)],
    ["Neto", formatSignedDOP(totals.net)],
    ["Retorno sobre lo apostado", totals.return_pct === null ? "—" : formatPercent(totals.return_pct)],
    ["Neto medio por sesión cerrada", totals.mean_net_closed === null ? "—" : formatMeanDOP(totals.mean_net_closed)],
    ["Sesiones totales", formatNumber(totals.sessions)],
    ["Metas", formatNumber(totals.goal)],
    ["Quiebras", formatNumber(totals.ruin)],
    ["Límites", formatNumber(totals.limit)],
    ["Incompletas", `${formatNumber(totals.incomplete)} · incluidas en el neto total`],
    ["Ventana efectiva", `${window.first_label} – ${window.last_label}`],
    ["Sorteos de la ventana", `${formatNumber(window.draws)} · ${formatNumber(window.ranked_draws)} con ranking`],
  ];
}

export function detailStatusCopy(detail: RunDetail): string {
  const sessions = `${formatNumber(detail.stored_sessions)} de ${formatNumber(detail.total_sessions)} sesiones guardadas`;
  const bets = `${formatNumber(detail.stored_bets)} de ${formatNumber(detail.total_bets)} apuestas guardadas`;
  if (detail.status === "complete") return `Detalle completo: ${sessions} y ${bets}.`;
  if (detail.status === "sessions_truncated") {
    const omitted = detail.total_sessions - detail.stored_sessions;
    return `Detalle truncado por el límite de almacenamiento: ${sessions}; ${formatNumber(omitted)} sesiones posteriores no se guardaron. ${bets}.`;
  }
  return `Detalle parcial: ${sessions}; ${bets}. Límite aplicado: ${formatNumber(detail.limits.sessions)} sesiones, ${formatNumber(detail.limits.bets)} apuestas o ${formatNumber(detail.limits.bytes)} bytes.`;
}

export function outcomeLabel(outcome: "goal" | "ruin" | "limit" | "incomplete"): string {
  return { goal: "Meta", ruin: "Quiebra", limit: "Límite", incomplete: "Incompleta" }[outcome];
}

export function historyOriginLabel(origin: "frozen" | "import"): string {
  return origin === "frozen" ? "Historial congelado" : "Historial importado";
}
