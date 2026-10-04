import type { ReactNode } from "react";
import { Figure, Money, type FigureVariant } from "./Data";

export interface VerdictFigure {
  label: string;
  amount: number;
  variant?: FigureVariant;
}

export interface VerdictProps {
  phrase: string;
  figures: readonly [VerdictFigure, VerdictFigure, VerdictFigure];
  closeReason: string;
  caveat?: string;
}

export function Verdict({ phrase, figures, closeReason, caveat = "Esto simula escenarios; no predice ni garantiza rentabilidad." }: VerdictProps) {
  return <section aria-label="Veredicto" className="ledger-block">
    <h1 className="ledger-verdict-title">{phrase}</h1>
    <div className="ledger-verdict-figures">
      {figures.map(({ label, amount, variant = "neutral" }) => <div className="ledger-stat" key={label}>
        <span className="ledger-label">{label}</span><Money amount={amount} variant={variant} />
      </div>)}
    </div>
    <p>{closeReason}</p>
    <p className="ledger-caveat">{caveat}</p>
  </section>;
}

export interface OrderSummaryRow {
  label: string;
  value: ReactNode;
}

export interface OrderSummaryProps {
  capital: number;
  goal: number;
  duration: ReactNode;
  coverage: ReactNode;
}

export function OrderSummary({ capital, goal, duration, coverage }: OrderSummaryProps) {
  const rows: OrderSummaryRow[] = [
    { label: "Capital", value: <Money amount={capital} align="right" /> },
    { label: "Meta de saldo", value: <Money amount={goal} align="right" /> },
    { label: "Duración", value: duration },
    {label: "Cobertura", value: coverage},
  ];

  return <section className="ledger-block" aria-label="Resumen de la orden">
    <div className="ledger-summary-rows">
      {rows.map(({ label, value }) => <div className="ledger-summary-row" key={label}>
        <span className="ledger-label">{label}</span>
        {typeof value === "string" || typeof value === "number" ? <Figure value={value} align="right" /> : value}
      </div>)}
    </div>
    <p className="ledger-caveat">Esto simula escenarios; no predice ni garantiza rentabilidad.</p>
  </section>;
}
