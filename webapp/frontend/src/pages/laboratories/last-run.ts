import type { LaboratoryLastRun } from "../../api/laboratories";
import { formatSignedDOP } from "../../lib/format";
import { formatAbsoluteDOP } from "./result-model";

export type LastRunState = "gain" | "loss" | "even" | "none";
export interface LastRunPresentation {
  state: LastRunState;
  /** Visible text: the arrow/sign carries the meaning so colour is never the only cue. */
  text: string;
  /** Spoken equivalent, e.g. "Último resultado: ganancia de RD$1.234". */
  label: string;
}

export function lastRunPresentation(lastRun: LaboratoryLastRun | null | undefined): LastRunPresentation {
  if (!lastRun || !Number.isSafeInteger(lastRun.total_net)) {
    return { state: "none", text: "Sin corridas", label: "Último resultado: sin corridas guardadas" };
  }
  const net = lastRun.total_net;
  if (net > 0) return { state: "gain", text: `▲ ${formatSignedDOP(net)}`, label: `Último resultado: ganancia de ${formatAbsoluteDOP(net)}` };
  if (net < 0) return { state: "loss", text: `▼ ${formatSignedDOP(net)}`, label: `Último resultado: pérdida de ${formatAbsoluteDOP(-net)}` };
  return { state: "even", text: `= ${formatAbsoluteDOP(0)}`, label: "Último resultado: sin ganancia ni pérdida (RD$0)" };
}
