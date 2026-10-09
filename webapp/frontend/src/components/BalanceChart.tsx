import { formatDOP } from "../lib/format";

interface Point { ordinal: number; balance: number }

/** Only loaded, persisted bet balances are plotted. No missing interval is interpolated. */
export function BalanceChart({ points, goal, total, formatMoney = formatDOP, initialCapital }: { points: Point[]; goal: number; total: number; formatMoney?: (amount: number) => string; initialCapital?: number; reductionMethod?: string }) {
  if (total === 0) return <p role="status">Todavía no hay sorteos jugados para mostrar.</p>;
  const plotted = initialCapital == null ? points : [{ ordinal: 0, balance: initialCapital }, ...points];
  const values = [...plotted.map((point) => point.balance), goal];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const y = (value: number) => 170 - ((value - low) / (high - low || 1)) * 140;
  const x = (index: number) => 35 + ((index - (initialCapital == null ? 1 : 0)) / Math.max(total - (initialCapital == null ? 1 : 0), 1)) * 540;
  const segments: Point[][] = [];
  for (const point of plotted) {
    if (!segments.length || segments[segments.length - 1][segments[segments.length - 1].length - 1].ordinal !== point.ordinal - 1) segments.push([]);
    segments[segments.length - 1].push(point);
  }
  return <figure className="my-5 min-w-0">
    <figcaption className="mb-2 text-sm">Evolución del saldo · {points.length} de {total} sorteos</figcaption>
    <svg role="img" aria-label="Gráfico de saldos registrados y meta; datos textuales a continuación" viewBox="0 0 610 200" className="h-auto w-full max-w-[800px]">
      {[30, 100, 170].map((lineY) => <line key={lineY} x1="35" x2="575" y1={lineY} y2={lineY} stroke="var(--bf-rule)" strokeWidth="1" />)}
      <line x1="35" x2="575" y1={y(goal)} y2={y(goal)} stroke="var(--bf-legend-dim)" strokeDasharray="2 4" strokeWidth="1" />
      {segments.map((segment) => <polyline key={segment[0].ordinal} points={segment.map((point) => `${x(point.ordinal)},${y(point.balance)}`).join(" ")} fill="none" stroke="var(--bf-legend)" strokeWidth="1" />)}
      {plotted.map((point) => <circle key={point.ordinal} cx={x(point.ordinal)} cy={y(point.balance)} r="2" fill="var(--bf-legend)" />)}
      {plotted.length > 0 && <text x={x(plotted[plotted.length - 1].ordinal)} y={Math.max(16, y(plotted[plotted.length - 1].balance) - 8)} textAnchor="end" fill="var(--bf-legend)" fontSize="12">Saldo · {formatMoney(plotted[plotted.length - 1].balance)}</text>}
      <text x="575" y={Math.max(16, y(goal) - 8)} textAnchor="end" fill="var(--bf-legend-dim)" fontSize="12">Meta · {formatMoney(goal)}</text>
    </svg>
    <p className="mt-2 text-sm">Meta de saldo: <span className="font-mono tabular-nums">{formatMoney(goal)}</span></p>
    <div className="max-h-40 overflow-y-auto border-y border-border" role="region" aria-label="Saldos registrados por sorteo">
      <table className="w-full border-collapse text-sm"><tbody>
        {points.map((point) => <tr key={point.ordinal} className="border-b border-border last:border-0"><th scope="row" className="py-2 text-left font-normal">Sorteo {point.ordinal}</th><td className="py-2 text-right font-mono tabular-nums">{formatMoney(point.balance)}</td></tr>)}
      </tbody></table>
    </div>
  </figure>;
}
