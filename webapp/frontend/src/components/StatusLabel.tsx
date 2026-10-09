import type { ExperimentStatus, Outcome, RunStatus } from "../api/types";
import { Chip } from "./ui";

/**
 * Execution status (pending/running/completed/...) and session outcome
 * (goal/ruin/limit/history_exhausted) are different vocabularies (UX37).
 * They are never rendered with the same word. Text is the authoritative,
 * non-color signal: every value in EXECUTION_STATUS and every value in
 * OUTCOME has its own unique Spanish label. Shape remains metadata for
 * consumers, but is not drawn; the label text distinguishes every state.
 */

interface StatusEntry {
  label: string;
  shape: "circle" | "square" | "triangle" | "diamond" | "hexagon" | "cross" | "check";
  tone: "neutral" | "positive" | "warning" | "danger";
}

const EXECUTION_STATUS: Record<ExperimentStatus | RunStatus, StatusEntry> = {
  pending: { label: "Pendiente", shape: "circle", tone: "neutral" },
  held: { label: "Retenido", shape: "diamond", tone: "warning" },
  running: { label: "En curso", shape: "triangle", tone: "neutral" },
  // Decision 8 (plan claridad-interfaz-80-20): "completed" is an execution
  // state, not a claim that the run's goal was reached; the closing reason
  // is presented separately via the outcome vocabulary below.
  completed: { label: "Ejecución completada", shape: "check", tone: "positive" },
  cancelled: { label: "Cancelado", shape: "cross", tone: "warning" },
  not_run: { label: "No ejecutado", shape: "square", tone: "neutral" },
  interrupted: { label: "Interrumpido", shape: "hexagon", tone: "warning" },
  failed: { label: "Con error", shape: "cross", tone: "danger" },
};

const OUTCOME: Record<Outcome, StatusEntry> = {
  goal: { label: "Meta alcanzada", shape: "check", tone: "positive" },
  ruin: { label: "Quiebre", shape: "cross", tone: "danger" },
  limit: { label: "Límite de sesión", shape: "diamond", tone: "warning" },
  history_exhausted: { label: "Historial agotado", shape: "square", tone: "neutral" },
};

const CHIP_VARIANT: Record<StatusEntry["tone"], "neutral" | "success" | "warning" | "danger"> = {
  neutral: "neutral",
  positive: "success",
  warning: "neutral",
  danger: "danger",
};

interface StatusLabelProps {
  kind: "execution" | "outcome";
  value: ExperimentStatus | RunStatus | Outcome;
  className?: string;
}

export function StatusLabel({ kind, value, className }: StatusLabelProps) {
  const table = kind === "execution" ? EXECUTION_STATUS : OUTCOME;
  const entry = (table as Record<string, StatusEntry>)[value];
  if (!entry) {
    throw new Error(`unknown ${kind} status value: ${value}`);
  }

  return <Chip variant={CHIP_VARIANT[entry.tone]} className={`font-mono ${className ?? ""}`.trim()}>
    <span data-status-kind={kind} data-status-value={value} data-status-shape={entry.shape}>
      {entry.label}
    </span>
  </Chip>;
}
