import type { ReactNode } from "react";
import { formatDOP } from "../../lib/format";

export type FigureVariant = "neutral" | "positive" | "negative";
export interface FigureProps {
  value: ReactNode;
  variant?: FigureVariant;
  align?: "left" | "right";
  className?: string;
}

export function Figure({ value, variant = "neutral", align = "left", className = "" }: FigureProps) {
  return <span className={`ledger-figure ${variant !== "neutral" ? `ledger-money-${variant}` : ""} ${align === "right" ? "ledger-figure-right" : ""} ${className}`.trim()}>{value}</span>;
}

export interface MoneyProps extends Omit<FigureProps, "value"> {
  amount: number;
}

export function Money({ amount, ...props }: MoneyProps) {
  return <Figure value={formatDOP(amount)} {...props} />;
}

export interface StatProps {
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  variant?: FigureVariant;
  className?: string;
}

export function Stat({ label, value, delta, variant = "neutral", className = "" }: StatProps) {
  return <div className={`ledger-stat ${className}`.trim()}>
    <span className="ledger-label">{label}</span>
    <Figure value={value} variant={variant} />
    {delta !== undefined && <span className="ledger-hint">{delta}</span>}
  </div>;
}

export type ChipVariant = "success" | "neutral" | "warning" | "danger" | "info";
export interface ChipProps {
  children: ReactNode;
  variant?: ChipVariant;
  className?: string;
}

export function Chip({ children, variant = "neutral", className = "" }: ChipProps) {
  return <span className={`ledger-chip ledger-chip-${variant} ${className}`.trim()}>{children}</span>;
}
