const CANONICAL_POSITIVE = /^[1-9][0-9]{0,18}$/;
const SQLITE_MAX = 9223372036854775807n;
const ENGLISH_INTEGER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function quotaInputError(value: string): string | null {
  if (!CANONICAL_POSITIVE.test(value)) return "Ingresá bytes como un entero decimal positivo, sin ceros iniciales.";
  if (BigInt(value) > SQLITE_MAX) return "La cuota supera el máximo admitido.";
  return null;
}

export function remainingBytes(quota: string, used: string): string {
  const difference = BigInt(quota) - BigInt(used);
  return (difference > 0n ? difference : 0n).toString();
}

export function formatExactBytes(value: string): string {
  return `${ENGLISH_INTEGER.format(BigInt(value))} bytes`;
}

export function formatDiskBytes(value: number): string {
  if (!Number.isFinite(value) || value < 0 || !Number.isInteger(value)) return "Precisión no disponible";
  if (!Number.isSafeInteger(value)) return `Valor aproximado: ≈ ${ENGLISH_INTEGER.format(value)} bytes`;
  return formatExactBytes(value.toString());
}

const MB = 1024n * 1024n;
const GB = 1024n * MB;
const tenths = (value: bigint): string => {
  const whole = value / 10n;
  const tenth = value % 10n;
  return tenth === 0n ? whole.toString() : `${whole},${tenth}`;
};

/** Plain-language size ("12,5 MB", "1,2 GB") for non-technical display. */
export function formatSize(value: string): string {
  const bytes = BigInt(value);
  if (bytes === 0n) return "0 MB";
  if (bytes >= GB) return `${tenths(bytes * 10n / GB)} GB`;
  if (bytes < MB / 10n) return "menos de 0,1 MB";
  return `${tenths(bytes * 10n / MB)} MB`;
}

/** Share of the limit already used, 0–100 (whole number, rounded up so a nearly full bar never reads as free). */
export function usagePercent(used: string, limit: string): number {
  const total = BigInt(limit);
  if (total <= 0n) return 100;
  const percent = (BigInt(used) * 100n + total - 1n) / total;
  return Number(percent > 100n ? 100n : percent);
}

/** Megabytes shown in the quota editor: at most two decimals, no trailing zeros. */
export function bytesToMbInput(bytes: string): string {
  const hundredths = BigInt(bytes) * 100n / MB;
  const whole = hundredths / 100n;
  const fraction = (hundredths % 100n).toString().padStart(2, "0").replace(/0+$/, "");
  return fraction ? `${whole},${fraction}` : whole.toString();
}

const MB_INPUT = /^(\d{1,12})(?:[.,](\d{1,2}))?$/;

/** Converts the editor value (MB, comma or dot decimal) to the canonical byte string the API expects. */
export function mbInputToBytes(input: string): string | null {
  const match = MB_INPUT.exec(input.trim());
  if (!match) return null;
  const hundredths = BigInt(match[1]) * 100n + BigInt((match[2] ?? "").padEnd(2, "0") || "0");
  const bytes = hundredths * MB / 100n;
  return bytes > 0n ? bytes.toString() : null;
}

export function quotaMbError(input: string): string | null {
  if (input.trim() === "") return "Escribí cuántos MB querés permitir.";
  const bytes = mbInputToBytes(input);
  if (bytes === null) return "Escribí un número de MB mayor que 0, con hasta dos decimales.";
  return quotaInputError(bytes) === null ? null : "El límite supera el máximo admitido.";
}

export const MAX_PRIZE = 10000;
export const PRIZE_ERROR = "Cada premio debe ser un número entero mayor que 0 y como máximo 10000.";

/** Parses the prize fields; null when any is not an integer between 1 and 10000. */
export function parsePrizes(drafts: string[]): number[] | null {
  const values = drafts.map((draft) => (/^\d{1,6}$/.test(draft.trim()) ? Number(draft.trim()) : NaN));
  return values.every((value) => Number.isInteger(value) && value >= 1 && value <= MAX_PRIZE) ? values : null;
}

const ORDINALS = ["1.er", "2.º", "3.er", "4.º", "5.º"];
export function positionLabel(index: number): string {
  return `${ORDINALS[index] ?? `${index + 1}.º`} número`;
}
