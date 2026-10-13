/** Mean net per closed session: two decimals, "." thousands, "," decimals, explicit sign. */
export function formatMean(value: number): string {
  const rounded = Math.abs(value).toFixed(2);
  const sign = value < 0 && Number(rounded) !== 0 ? "−" : "+";
  const [integer, decimals] = rounded.split(".");
  return `${sign}RD$${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ".")},${decimals}`;
}
