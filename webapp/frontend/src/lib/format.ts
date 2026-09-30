const dopFormatter = new Intl.NumberFormat("es-DO", {
  style: "currency",
  currency: "DOP",
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
});

/** Money is always an integer DOP amount (backend contract: capital, goal, bets, balances). */
export function formatDOP(amount: number): string {
  if (!Number.isInteger(amount)) {
    throw new RangeError(`DOP amounts must be integers, got ${amount}`);
  }
  return dopFormatter.format(amount);
}

/** Q80 numbers are 00-99, always shown zero-padded to two digits. */
export function formatTwoDigit(value: number): string {
  if (!Number.isInteger(value) || value < 0 || value > 99) {
    throw new RangeError(`value must be an integer between 0 and 99, got ${value}`);
  }
  return value.toString().padStart(2, "0");
}
