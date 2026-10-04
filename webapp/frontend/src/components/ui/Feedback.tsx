import { useId } from "react";
import type { ReactNode } from "react";
import { Button, Disclosure } from "./Controls";

export interface EmptyStateProps {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
  hint?: string;
}

export function EmptyState({ title, description, actionLabel, onAction, hint }: EmptyStateProps) {
  const titleId = useId();
  return <section className="ledger-empty" aria-labelledby={titleId}>
    <h2 id={titleId}>{title}</h2>
    <p>{description}</p>
    {hint && <p className="ledger-hint">{hint}</p>}
    <Button variant="primary" onClick={onAction}>{actionLabel}</Button>
  </section>;
}

export interface ErrorBannerProps {
  cause: string;
  recovery: string;
  actionLabel: string;
  onAction: () => void;
  detail?: ReactNode;
}

export function ErrorBanner({ cause, recovery, actionLabel, onAction, detail }: ErrorBannerProps) {
  return <div className="ledger-error-banner" role="alert">
    <p>{cause}</p>
    <p>{recovery}</p>
    <p>Tu información se conserva.</p>
    {detail && <Disclosure summary="Detalles técnicos">{detail}</Disclosure>}
    <Button variant="secondary" onClick={onAction}>{actionLabel}</Button>
  </div>;
}

export interface LoadingProps {
  rows?: number;
  label?: string;
  className?: string;
}

export function Loading({ rows = 3, label = "Cargando información…", className = "" }: LoadingProps) {
  const count = Math.max(1, Math.floor(rows));
  return <div className={className}>
    <span className="ledger-sr-only" role="status">{label}</span>
    <div aria-hidden="true">{Array.from({ length: count }, (_, index) => <div key={index} className="ledger-skeleton-row" />)}</div>
  </div>;
}
