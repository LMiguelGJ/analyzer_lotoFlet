/** Decimal input is parsed as text; Number is used only after an exact safe-integer check. */
export function safeInteger(value: bigint, label: string, maximum = BigInt(Number.MAX_SAFE_INTEGER)): number {
  if (value < 0n || value > maximum) throw new Error(`${label}: el valor supera el límite admitido.`);
  return Number(value);
}

export function wholeNumber(text: string, label: string, minimum: bigint, maximum: bigint): number {
  if (!/^(0|[1-9]\d*)$/.test(text)) throw new Error(`${label}: ingresá un entero sin signo.`);
  const value = BigInt(text);
  if (value < minimum || value > maximum) throw new Error(`${label}: valor fuera del rango ${minimum}–${maximum}.`);
  return safeInteger(value, label);
}

export function moneyUnits(text: string, scale: number, label: string): number {
  if (!Number.isInteger(scale) || scale < 0 || scale > 6 || !/^(0|[1-9]\d*)(?:\.(\d+))?$/.test(text)) {
    throw new Error(`${label}: ingresá un importe decimal válido.`);
  }
  const [whole, fraction = ""] = text.split(".");
  if (fraction.length > scale) throw new Error(`${label}: máximo ${scale} decimales para esta escala.`);
  const units = BigInt(whole) * 10n ** BigInt(scale) + BigInt(fraction.padEnd(scale, "0") || "0");
  if (units < 1n || units > 1_000_000_000_000n) throw new Error(`${label}: debe ser mayor que cero y no superar 1.000.000.000.000 unidades.`);
  return safeInteger(units, label);
}

export function exactMultiplier(text: string, label: string): { numerator: number; denominator: number } {
  const match = /^(0|[1-9]\d*)(?:\.(\d+))?(?:\/(0|[1-9]\d*))?$/.exec(text);
  if (!match || (match[2] !== undefined && match[3] !== undefined)) throw new Error(`${label}: ingresá un entero, decimal o fracción a/b sin signo.`);
  const denominator = match[3] ? BigInt(match[3]) : 10n ** BigInt(match[2]?.length ?? 0);
  if (denominator === 0n) throw new Error(`${label}: el denominador debe ser mayor que cero.`);
  let numerator = BigInt(match[1]) * (match[3] ? 1n : denominator) + (match[3] ? 0n : BigInt(match[2] ?? "0"));
  let divisor = denominator;
  let remainder = numerator;
  while (divisor !== 0n) { const next = remainder % divisor; remainder = divisor; divisor = next; }
  numerator /= remainder;
  return { numerator: safeInteger(numerator, label, 1_000_000_000_000n), denominator: safeInteger(denominator / remainder, label, 1_000_000_000_000n) };
}
