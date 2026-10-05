// Spanish thousands separator ("."), applied by hand: Intl es-ES skips grouping for 4-digit amounts
// and renders the DOP symbol as "DOP", neither of which is the intended "RD$2.800".
const groupThousands = (digits: string): string => digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

/** Money is always an integer DOP amount (backend contract: capital, goal, bets, balances). */
export function formatDOP(amount: number): string {
  if (!Number.isInteger(amount)) {
    throw new RangeError(`DOP amounts must be integers, got ${amount}`);
  }
  return `${amount < 0 ? "-" : ""}RD$${groupThousands(Math.abs(amount).toString())}`;
}

/** Q80 numbers are 00-99, always shown zero-padded to two digits. */
export function formatTwoDigit(value: number): string {
  if (!Number.isInteger(value) || value < 0 || value > 99) {
    throw new RangeError(`value must be an integer between 0 and 99, got ${value}`);
  }
  return value.toString().padStart(2, "0");
}
