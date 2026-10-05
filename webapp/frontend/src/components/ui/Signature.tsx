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

function SummaryCell({ label, children }: { label: string; children: ReactNode }) {
  return <div className="ledger-summary-cell">
    <span className="ledger-label">{label}</span>
    {typeof children === "string" || typeof children === "number" ? <Figure value={children} /> : children}
  </div>;
}

export function OrderSummary({ capital, goal, duration, coverage, caveat = DEFAULT_CAVEAT }: OrderSummaryProps) {
  return <section className="ledger-block" aria-label="Resumen de la orden">
    <div className="ledger-summary-cells">
      <SummaryCell label="Capital">{capital == null ? "Sin definir" : <Money amount={capital} />}</SummaryCell>
      <SummaryCell label="Meta de saldo">{goal == null ? "Sin definir" : <Money amount={goal} />}</SummaryCell>
      <SummaryCell label="Duración">{duration}</SummaryCell>
    </div>
    <div className="ledger-summary-selection">
      <span className="ledger-label">Cobertura</span>
      <p>{coverage}</p>
    </div>
    <p className="ledger-caveat">{caveat}</p>
  </section>;
}
