import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
}

export function Button({ variant = "secondary", className = "", type = "button", ...props }: ButtonProps) {
  // Keep one primary action per screen; consumers choose the single action that advances the task.
  return <button type={type} className={`ledger-button ledger-button-${variant} ${className}`.trim()} {...props} />;
}

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  detail?: string;
}

export function Field({ id, label, hint, error, detail, className = "", ...inputProps }: FieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const detailId = detail ? `${id}-detail` : undefined;
  const describedBy = [hintId, errorId, detailId].filter(Boolean).join(" ") || undefined;
  return <div className={`ledger-field ${className}`.trim()}>
    <label className="ledger-label" htmlFor={id}>{label}</label>
    <input id={id} className="ledger-control" aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...inputProps} />
    {hint && <p id={hintId} className="ledger-hint">{hint}</p>}
    {error && <p id={errorId} className="ledger-error">{error}</p>}
    {detail && <p id={detailId} className="ledger-hint">{detail}</p>}
  </div>;
}

export interface DisclosureProps {
  summary: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

export function Disclosure({ summary, children, defaultOpen, className = "" }: DisclosureProps) {
  // Technical internals live here; financial truth never does.
  return <details className={`ledger-disclosure ${className}`.trim()} open={defaultOpen}>
    <summary className="ledger-label">{summary}</summary>
    <div>{children}</div>
  </details>;
}
