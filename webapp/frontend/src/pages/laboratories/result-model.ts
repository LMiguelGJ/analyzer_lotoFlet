import type { LaboratoryWallet } from "../../api/laboratories";
import { formatNumber } from "../../lib/format";

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
