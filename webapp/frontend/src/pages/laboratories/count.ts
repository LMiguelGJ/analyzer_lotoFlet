import { formatNumber } from "../../lib/format";

/** "1 corrida" / "2 corridas": Spanish plural chosen by the exact count. */
export function count(value: number, one: string, many: string): string {
  return `${formatNumber(value)} ${value === 1 ? one : many}`;
}
