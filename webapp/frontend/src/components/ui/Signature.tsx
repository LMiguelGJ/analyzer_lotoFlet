import type { ReactNode } from "react";
import { Figure, Money, type FigureVariant } from "./Data";

const DEFAULT_CAVEAT = "Esto simula escenarios; no predice ni garantiza rentabilidad.";

export interface VerdictFigure {
  label: string;
  amount: number;
  variant?: FigureVariant;
  /** "count" renders a plain figure (e.g. draws played) instead of RD$ money. */
  kind?: "money" | "count";
}

export interface VerdictProps {
  phrase: string;
  figures: readonly [VerdictFigure, VerdictFigure, VerdictFigure];
  closeReason: string;
  caveat?: string;
}

export function Verdict({ phrase, figures, closeReason, caveat = DEFAULT_CAVEAT }: VerdictProps) {
  return <section aria-label="Veredicto" className="ledger-block">
    <h2 className="ledger-verdict-title">{phrase}</h2>
    <div className="ledger-verdict-figures">
      {figures.map(({ label, amount, variant = "neutral", kind = "money" }) => <div className="ledger-stat" key={label}>
        <span className="ledger-label">{label}</span>{kind === "count" ? <Figure value={amount} variant={variant} /> : <Money amount={amount} variant={variant} />}
      </div>)}
    </div>
    <p>{closeReason}</p>
    <p className="ledger-caveat">{caveat}</p>
  </section>;
}

export interface OrderSummaryProps {
  /** null renders "Sin definir" (e.g. a draft whose input is still empty). */
  capital: number | null;
  goal: number | null;
  duration: ReactNode;
  coverage: ReactNode;
  caveat?: string;
}

export function OrderSummary({ capital, goal, duration, coverage, caveat = DEFAULT_CAVEAT }: OrderSummaryProps) {
  return <section className="ledger-block" aria-label="Resumen de la orden">
    <dl className="ledger-summary-rows">
      <div className="ledger-summary-row">
        <dt className="ledger-label">Capital inicial</dt>
        <dd className="ledger-summary-value">{capital == null ? "Sin definir" : <Money amount={capital} />}</dd>
      </div>
      <div className="ledger-summary-row">
        <dt className="ledger-label">Meta de saldo</dt>
        <dd className="ledger-summary-value">{goal == null ? "Sin definir" : <Money amount={goal} />}</dd>
      </div>
      <div className="ledger-summary-row">
        <dt className="ledger-label">Duración</dt>
        <dd className="ledger-summary-value">{typeof duration === "string" || typeof duration === "number" ? <Figure value={duration} /> : duration}</dd>
      </div>
      <div className="ledger-summary-row">
        <dt className="ledger-label">Cobertura</dt>
        <dd className="ledger-summary-value">{coverage}</dd>
      </div>
      <div className="ledger-summary-row">
        <dt className="ledger-label">Aviso</dt>
        <dd className="ledger-summary-value ledger-caveat">{caveat}</dd>
      </div>
    </dl>
  </section>;
}
