// Spanish thousands separator ("."), kept explicit so integer Dominican amounts are stable.
const groupThousands = (digits: string): string => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

/** Signed financial presentation. Return values are signed even when zero; -0 is normalized. */
export function formatSignedDOP(amount: number): string {
  if (!Number.isInteger(amount)) throw new RangeError(`DOP amounts must be integers, got ${amount}`);
  const sign = amount < 0 ? "−" : "+";
  return `${sign}RD$${groupThousands(Math.abs(amount).toString())}`;
}

/** Compatibility name for existing consumers; DOP amounts remain explicitly signed. */
export function formatDOP(amount: number): string {
  return formatSignedDOP(amount);
}

/** Dominican integer grouping for counts and draw labels. */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) throw new RangeError(`value must be finite, got ${value}`);
  const [integer, fraction] = Math.abs(value).toString().split(".");
  return `${value < 0 ? "−" : ""}${groupThousands(integer)}${fraction ? `,${fraction}` : ""}`;
}

/** API return_pct is already expressed in percentage points, not a 0–1 ratio. */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value)) throw new RangeError(`percentage must be finite, got ${value}`);
  const normalized = Object.is(value, -0) ? 0 : value;
  const [integer, fraction] = Math.abs(normalized).toFixed(1).split(".");
  const formatted = `${groupThousands(integer)},${fraction}`;
  return `${normalized < 0 ? "−" : "+"}${formatted} %`;
}

export type Outcome = "goal" | "ruin" | "limit" | "incomplete";
const OUTCOME_LABELS: Record<Outcome, string> = {
  goal: "Meta",
  ruin: "Quiebra",
  limit: "Límite",
  incomplete: "Incompleta",
};
export function formatOutcome(outcome: Outcome): string {
  return OUTCOME_LABELS[outcome];
}

/** Q80 numbers are 00-99, always shown zero-padded to two digits. */
export function formatTwoDigit(value: number): string {
  if (!Number.isInteger(value) || value < 0 || value > 99) {
    throw new RangeError(`value must be an integer between 0 and 99, got ${value}`);
  }
  return value.toString().padStart(2, "0");
}
