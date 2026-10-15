const percentage = new Intl.NumberFormat("es-ES", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "always",
  useGrouping: false,
});

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
