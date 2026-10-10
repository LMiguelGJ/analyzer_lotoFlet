import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
}

export function Button({ variant = "secondary", className = "", type = "button", loading = false, disabled, ...props }: ButtonProps) {
  // Keep one primary action per screen; loading also prevents duplicate submissions.
  return <button type={type} className={`ledger-button ledger-button-${variant} ${className}`.trim()} {...props} disabled={disabled || loading} aria-busy={loading || props["aria-busy"]} />;
}

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  detail?: string;
}

export function Field({ id, label, hint, error, detail, className = "", "aria-describedby": externalDescribedBy, "aria-invalid": externalInvalid, ...inputProps }: FieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const detailId = detail ? `${id}-detail` : undefined;
  const describedBy = [externalDescribedBy, hintId, errorId, detailId].filter(Boolean).join(" ") || undefined;
  const isChoice = inputProps.type === "checkbox" || inputProps.type === "radio";
  const choiceDisabled = isChoice && inputProps.disabled === true;
  const input = <input
    id={id}
    className={`ledger-control ${isChoice ? "ledger-choice-control" : ""}`.trim()}
    aria-invalid={error ? true : externalInvalid}
    aria-describedby={describedBy}
    {...inputProps}
  />;
  return <div className={`ledger-field ${isChoice ? "ledger-field-choice" : ""} ${className}`.trim()}>
    {isChoice ? <label className={`ledger-label ledger-choice-label ${choiceDisabled ? "is-disabled" : ""}`.trim()} htmlFor={id}>{input}<span>{label}</span></label> : <>
      <label className="ledger-label" htmlFor={id}>{label}</label>
      {input}
    </>}
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
