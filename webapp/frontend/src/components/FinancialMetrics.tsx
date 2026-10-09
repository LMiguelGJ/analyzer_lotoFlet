import type { FinancialMetrics as Metrics } from "../api/types";
import { Disclosure, Figure, SectionHeader } from "./ui";

export function metricRatio(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "N/D" : value.toFixed(6);
}

/** Display server projections only; no financial formulas are duplicated here. */
export function FinancialMetrics({ result, money, omitNet = false }: {
  result: Metrics & { wagered: number; paid: number };
  money: (amount: number) => string;
  /** The caller already shows the net result as part of the outcome. */
  omitNet?: boolean;
}) {
  return <section aria-label="Métricas financieras" className="financial-metrics-plate my-6">
    <SectionHeader title="Resumen financiero" />
    <dl className="data-list financial-metrics-list">
      <dt>Total apostado</dt><dd className="data-list-numeric min-w-0">{money(result.wagered)}</dd>
      <dt>Total pagado</dt><dd className="data-list-numeric min-w-0">{money(result.paid)}</dd>
      {!omitNet && <><dt>Neto</dt><dd className="data-list-numeric min-w-0">{result.net == null ? "No disponible" : <span className="ledger-figure">{money(result.net)}</span>}</dd></>}
      <dt>Retorno por peso apostado</dt><dd className="data-list-numeric min-w-0"><Figure value={metricRatio(result.return_per_wagered)} /></dd>
      <dt>Cambio sobre lo apostado</dt><dd className="data-list-numeric min-w-0"><Figure value={metricRatio(result.roi)} /></dd>
      <dt>Máximo de saldo perdido desde un pico</dt><dd className="data-list-numeric min-w-0">{result.max_drawdown == null ? "No disponible" : <Figure value={money(result.max_drawdown)} />}</dd>
    </dl>
    <Disclosure summary="Detalles técnicos" className="mt-2">
      <p className="field-help">Las métricas provienen del servidor para esta corrida guardada. El ROI y los ratios usan redondeo HALF_UP a seis decimales; «N/D» corresponde a una razón no disponible.</p>
    </Disclosure>
  </section>;
}
