import { formatDOP } from "../lib/format";

interface Point { ordinal: number; balance: number }

/** Only loaded, persisted bet balances are plotted. No missing interval is interpolated. */
export function BalanceChart({ points, goal, total }: { points: Point[]; goal: number; total: number }) {
  if (total === 0) return <p>No hay apuestas registradas para graficar.</p>;
  const values = [...points.map((point) => point.balance), goal];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const y = (value: number) => 170 - ((value - low) / (high - low || 1)) * 140;
  const x = (index: number) => 35 + ((index - 1) / Math.max(total - 1, 1)) * 540;
  const segments: Point[][] = [];
  for (const point of points) {
    if (!segments.length || segments[segments.length - 1][segments[segments.length - 1].length - 1].ordinal !== point.ordinal - 1) segments.push([]);
    segments[segments.length - 1].push(point);
  }
  return <figure className="my-6 min-w-0">
    <figcaption className="mb-2 font-mono text-sm">Evolución del saldo · {points.length} de {total} apuestas cargadas{points.length < total ? " (gráfico incompleto: navegá las páginas para ver otros tramos)" : ""}</figcaption>
    <svg role="img" aria-label="Gráfico de saldos registrados y meta; datos textuales a continuación" viewBox="0 0 610 200" className="h-auto w-full max-w-[800px] border border-border-control bg-surface">
      <line x1="35" x2="575" y1={y(goal)} y2={y(goal)} stroke="currentColor" strokeDasharray="5 5" />
      {segments.map((segment) => <polyline key={segment[0].ordinal} points={segment.map((point) => `${x(point.ordinal)},${y(point.balance)}`).join(" ")} fill="none" stroke="var(--color-accent, currentColor)" strokeWidth="2" />)}
      {points.map((point) => <circle key={point.ordinal} cx={x(point.ordinal)} cy={y(point.balance)} r="4" fill="currentColor" />)}
    </svg>
    <p className="mt-2 text-sm">Meta: {formatDOP(goal)} (línea de referencia)</p>
    <ul className="max-h-32 overflow-y-auto text-sm text-text-secondary" aria-label="Saldos registrados por apuesta">
      {points.map((point) => <li key={point.ordinal}>Apuesta {point.ordinal}: {formatDOP(point.balance)}</li>)}
    </ul>
  </figure>;
}
