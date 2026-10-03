import { formatDOP } from "../lib/format";

export interface ComparisonPoint { ordinal: number; label: string; balance: number }
export interface ComparisonSeries { ordinal: number; name: string; visible: boolean; total: number; points: ComparisonPoint[]; reductionMethod?: string; initialCapital?: number; startLabel?: string }

const patterns = ["none", "8 5", "2 5", "12 4 2 4", "4 3 1 3"];
const colors = ["var(--color-accent, currentColor)", "var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];
const markers = ["circle", "square", "diamond", "triangle", "cross"];
function time(label: string) { return Date.parse(label.replace(" ", "T")); }

/** Connected strokes describe visual continuity only; circles are the actual saved observations. */
export function ComparisonChart({ series, onToggle, formatMoney = formatDOP }: { series: ComparisonSeries[]; onToggle: (ordinal: number) => void; formatMoney?: (amount: number) => string }) {
  series = series.map((entry) => entry.points.length && entry.initialCapital != null && entry.startLabel ? { ...entry, points: [{ ordinal: 0, label: entry.startLabel, balance: entry.initialCapital }, ...entry.points] } : entry);
  const dated = series.flatMap((entry) => entry.points.map((point) => time(point.label))).filter(Number.isFinite);
  const balances = series.flatMap((entry) => entry.points.map((point) => point.balance));
  const minTime = dated.length ? Math.min(...dated) : 0;
  const maxTime = dated.length ? Math.max(...dated) : 0;
  const low = balances.length ? Math.min(...balances) : 0;
  const high = balances.length ? Math.max(...balances) : 0;
  const x = (label: string) => 55 + ((time(label) - minTime) / (maxTime - minTime || 1)) * 700;
  const y = (balance: number) => 180 - ((balance - low) / (high - low || 1)) * 145;
  const timeLabels = series.flatMap((entry) => entry.points.map((point) => point.label)).sort((a, b) => time(a) - time(b));
  return <figure aria-label="Evolución comparada de saldos" className="min-w-0 space-y-3">
    <figcaption className="font-heading text-xl">Evolución comparada · fechas guardadas</figcaption>
    <p className="text-sm text-text-secondary">Las líneas conectan observaciones guardadas y el capital inicial; no agregan valores intermedios ni prolongan la sesión. Las trayectorias reducidas conservan inicio, fin y extremos; la reducción se declara por corrida.</p>
    <fieldset aria-label="Series visibles" className="flex flex-wrap gap-x-5 gap-y-2">
      {series.map((entry) => <label key={entry.ordinal} className="inline-flex min-h-control items-center gap-2 text-sm">
        <input type="checkbox" checked={entry.visible} onChange={() => onToggle(entry.ordinal)} aria-label={`Mostrar ${entry.name}`} className="accent-accent" />
        <svg aria-hidden="true" width="34" height="16" viewBox="0 0 34 16"><line x1="0" x2="34" y1="8" y2="8" stroke={colors[entry.ordinal % colors.length]} strokeWidth="2" strokeDasharray={patterns[entry.ordinal % patterns.length]} /></svg>
        {entry.name} · {markers[entry.ordinal % markers.length]}, {patterns[entry.ordinal % patterns.length] === "none" ? "línea continua" : "línea a trazos"}
      </label>)}
    </fieldset>
    {dated.length ? <section aria-label="Gráfico comparado desplazable" tabIndex={0} className="max-w-full overflow-x-auto border border-border-control bg-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
      <svg role="img" aria-label="Saldos por fecha y hora; datos textuales a continuación" viewBox="0 0 800 240" className="min-w-[640px] w-full h-auto">
        <line x1="55" x2="755" y1="190" y2="190" stroke="currentColor" />
        <text x="55" y="215" fontSize="12" fill="currentColor">{timeLabels[0]?.replace("T", " ")}</text>
        <text x="755" y="215" textAnchor="end" fontSize="12" fill="currentColor">{timeLabels[timeLabels.length - 1]?.replace("T", " ")}</text>
        {series.filter((entry) => entry.visible).map((entry) => {
          const points = entry.points.filter((point) => Number.isFinite(time(point.label))).sort((a, b) => time(a.label) - time(b.label));
          const pattern = patterns[entry.ordinal % patterns.length];
          const color = colors[entry.ordinal % colors.length];
          // A page gap is not evidence of a continuous saved sequence.
          const segments: ComparisonPoint[][] = [];
          for (const point of points) {
            if (!segments.length || (!entry.reductionMethod && segments[segments.length - 1].at(-1)!.ordinal + 1 !== point.ordinal)) segments.push([]);
            segments.at(-1)!.push(point);
          }
          return <g key={entry.ordinal}>
            {segments.map((segment, index) => <polyline key={index} data-testid={index === 0 ? `series-${entry.ordinal}` : undefined} points={segment.map((point) => `${x(point.label)},${y(point.balance)}`).join(" ")} fill="none" stroke={color} strokeDasharray={pattern} strokeWidth="2" />)}
            {points.map((point) => <g key={point.ordinal} transform={`translate(${x(point.label)} ${y(point.balance)})`}>
              {entry.ordinal % markers.length === 0 ? <circle r="3.5" fill={color} /> : entry.ordinal % markers.length === 1 ? <rect x="-3.5" y="-3.5" width="7" height="7" fill={color} /> : entry.ordinal % markers.length === 2 ? <path d="M0 -5 5 0 0 5 -5 0Z" fill={color} /> : entry.ordinal % markers.length === 3 ? <path d="M0 -5 5 4 -5 4Z" fill={color} /> : <path d="M-4 -4 4 4 M4 -4 -4 4" fill="none" stroke={color} strokeWidth="2" />}
            </g>)}
          </g>;
        })}
      </svg>
    </section> : <p role="status">Todavía no hay apuestas guardadas cargadas para graficar.</p>}
    <section aria-label="Datos textuales del gráfico" tabIndex={0} className="max-h-40 overflow-auto text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
      <ul className="space-y-1">{series.flatMap((entry) => entry.points.map((point) => <li key={`${entry.ordinal}:${point.ordinal}`}>{entry.name}: {point.label.replace("T", " ")} · {formatMoney(point.balance)}</li>))}</ul>
    </section>
  </figure>;
}
