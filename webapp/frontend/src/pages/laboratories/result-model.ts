import type { LaboratoryWallet, LaboratoryYearResult } from "../../api/laboratories";
import type { ReferenceTotals } from "../../api/referenceLabs";
import { formatNumber, formatSignedDOP } from "../../lib/format";

const percentage = new Intl.NumberFormat("es-ES", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "always",
  useGrouping: false,
});

export function isValidLaboratoryWallet(value: unknown, totalNet: number): value is LaboratoryWallet {
  if (typeof value !== "object" || value === null) return false;
  const wallet = value as Partial<LaboratoryWallet>;
  return wallet.policy === "retain-gains-top-up-v1"
    && Number.isSafeInteger(wallet.out_of_pocket) && (wallet.out_of_pocket as number) >= 0
    && Number.isSafeInteger(wallet.final_wealth) && (wallet.final_wealth as number) >= 0
    && Number.isSafeInteger(totalNet)
    && (wallet.final_wealth as number) - (wallet.out_of_pocket as number) === totalNet;
}

export function formatAbsoluteDOP(value: number | null): string {
  if (value === null || !Number.isSafeInteger(value) || value < 0) return "No disponible";
  return `RD$${formatNumber(value)}`;
}

/** Historical presentation only: includes the same incomplete sessions as net. */
export function returnOnWagered(net: number, wagered: number): number | null {
  if (wagered === 0) return null;
  const value = (net / wagered) * 100;
  return Object.is(value, -0) ? 0 : value;
}

export function formatReturnOnWagered(value: number | null): string {
  if (value === null) return "No disponible";
  return `${percentage.format(value).replace(/^-0,00$/, "+0,00").replace("-", "−")} %`;
}

/** Two decimals with a comma, like the rest of the app ("0,72"); the runtime es-DO locale would print a point. */
const ratioFormat = { format: (value: number): string => value.toFixed(2).replace(".", ",") };

/** What each peso wagered gave back (paid / wagered), or null when nothing was wagered. */
export function returnPerPeso(paid: number, wagered: number): number | null {
  return wagered === 0 ? null : paid / wagered;
}
export function formatReturnPerPeso(value: number | null): string {
  return value === null ? "Sin apuestas" : ratioFormat.format(value);
}
/** The game's built-in margin: 1 − sum(prizes)/100, in percentage points (28 for 60/8/4). */
export function houseEdgePercent(prizes: readonly number[]): number {
  return 100 - prizes.reduce((sum, prize) => sum + prize, 0);
}
export function formatHouseEdge(percent: number): string {
  return `${formatNumber(percent)} %`;
}
/** Average return per peso implied by the prizes alone: 1 − house edge. */
export function expectedReturnPerPeso(prizes: readonly number[]): string {
  return ratioFormat.format((100 - houseEdgePercent(prizes)) / 100);
}

export interface DeadlineSummary {
  goalsInTime: number;
  timeouts: number;
  ruins: number;
  /** Share (0–100) of closed sessions that reached the goal in time; null without closed sessions. */
  inTimePercent: number | null;
  /** Average draws (days on Leidsa) the successful sessions needed; null when none succeeded. */
  averageDaysToGoal: number | null;
  /** Net money across the sessions that ran out of time (usually negative). */
  timeoutNet: number | null;
}

/** Deadline figures, or null when the laboratory has no session deadline (older results). */
export function deadlineSummary(totals: ReferenceTotals): DeadlineSummary | null {
  if (totals.timeouts === undefined) return null;
  return {
    goalsInTime: totals.goals,
    timeouts: totals.timeouts,
    ruins: totals.ruins,
    inTimePercent: totals.completed === 0 ? null : (totals.goals / totals.completed) * 100,
    averageDaysToGoal: totals.goals === 0 || totals.goal_draws === undefined ? null : totals.goal_draws / totals.goals,
    timeoutNet: totals.timeout_net ?? null,
  };
}

const oneDecimal = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 1, maximumFractionDigits: 1, useGrouping: false });
export const formatPercentShare = (value: number | null): string => (value === null ? "No disponible" : `${oneDecimal.format(value)} %`);
export const formatAverageDays = (value: number | null): string => (value === null ? "No disponible" : `${oneDecimal.format(value)} días`);

const YEAR_FIELDS = ["year", "net", "goals", "ruins", "timeouts", "sessions_closed"] as const;

/** The by-year rows when the server sent a non-empty, well-formed list; null hides the table. */
export function validYearResults(value: unknown): LaboratoryYearResult[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const valid = value.every((row) => typeof row === "object" && row !== null
    && YEAR_FIELDS.every((key) => Number.isSafeInteger((row as Record<string, unknown>)[key]))
    && Number.isFinite((row as Record<string, unknown>).return_pct));
  return valid ? (value as LaboratoryYearResult[]) : null;
}

export interface YearRowPresentation {
  state: "gain" | "loss" | "even";
  /** Visible text: the arrow and sign carry the meaning so colour is never the only cue. */
  net: string;
  /** Spoken equivalent, e.g. "ganancia de RD$379". */
  label: string;
  percent: string;
}

export function yearRowPresentation(row: LaboratoryYearResult): YearRowPresentation {
  const percent = formatReturnOnWagered(row.return_pct);
  if (row.net > 0) return { state: "gain", net: `▲ ${formatSignedDOP(row.net)}`, label: `ganancia de ${formatAbsoluteDOP(row.net)}`, percent };
  if (row.net < 0) return { state: "loss", net: `▼ ${formatSignedDOP(row.net)}`, label: `pérdida de ${formatAbsoluteDOP(-row.net)}`, percent };
  return { state: "even", net: `= ${formatAbsoluteDOP(0)}`, label: "sin ganancia ni pérdida", percent };
}
