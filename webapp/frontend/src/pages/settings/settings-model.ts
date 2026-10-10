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
