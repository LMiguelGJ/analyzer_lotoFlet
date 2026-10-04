import type { ExperimentStatus, Outcome, RunStatus } from "../api/types";
import { Chip } from "./ui";

/**
 * Execution status (pending/running/completed/...) and session outcome
 * (goal/ruin/limit/history_exhausted) are different vocabularies (UX37).
 * They are never rendered with the same word. Text is the authoritative,
 * non-color signal: every value in EXECUTION_STATUS and every value in
 * OUTCOME has its own unique Spanish label. The shape glyph is a supporting
 * cue, not a guarantee of uniqueness - related states in the same tone
 * family (e.g. cancelled/failed) may intentionally share a shape, since the
 * label text is what actually distinguishes them.
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

const SHAPE_PATH: Record<StatusEntry["shape"], string> = {
  circle: "M6 1a5 5 0 1 0 0 10A5 5 0 0 0 6 1Z",
  square: "M1.5 1.5h9v9h-9z",
  triangle: "M6 1 11 10.5H1z",
  diamond: "M6 1 11 6 6 11 1 6z",
  hexagon: "M3.5 1h5L11 6l-2.5 5h-5L1 6z",
  cross: "M1.6 1.6 10.4 10.4M10.4 1.6 1.6 10.4",
  check: "M1.5 6.2 4.5 9.5 10.5 2.5",
};

const CHIP_VARIANT: Record<StatusEntry["tone"], "neutral" | "success" | "warning" | "danger"> = {
  neutral: "neutral",
  positive: "success",
  warning: "warning",
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
    <span className="inline-flex items-center gap-1.5" data-status-kind={kind} data-status-value={value} data-status-shape={entry.shape}>
      <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true" className="shrink-0">
        <path d={SHAPE_PATH[entry.shape]} fill={entry.shape === "cross" || entry.shape === "check" ? "none" : "currentColor"} stroke="currentColor" strokeWidth="1.2" />
      </svg>
      {entry.label}
    </span>
  </Chip>;
}
