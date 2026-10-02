import type { FinancialMetrics as Metrics } from "../api/types";

export function metricRatio(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "N/A" : value.toFixed(6);
}

/** Display server projections only; no financial formulas are duplicated here. */
export function FinancialMetrics({ result, money }: {
  result: Metrics & { wagered: number; paid: number };
  money: (amount: number) => string;
}) {
  return <section aria-label="Métricas financieras" className="my-4">
    <dl className="data-list">
      <dt>Total apostado</dt><dd>{money(result.wagered)}</dd>
      <dt>Total pagado</dt><dd>{money(result.paid)}</dd>
      <dt>Neto</dt><dd>{result.net == null ? "N/A" : money(result.net)}</dd>
      <dt>Retorno por peso apostado</dt><dd>{metricRatio(result.return_per_wagered)}</dd>
      <dt>ROI neto</dt><dd>{metricRatio(result.roi)}</dd>
      <dt>Máximo drawdown absoluto</dt><dd>{result.max_drawdown == null ? "N/A" : money(result.max_drawdown)}</dd>
    </dl>
    <p className="field-help">Métricas del backend por corrida guardada, no del experimento entero. Ratios adimensionales, redondeo decimal HALF_UP a seis decimales; denominador cero: N/A. Drawdown desde el capital inicial y los picos de saldo.</p>
  </section>;
}
