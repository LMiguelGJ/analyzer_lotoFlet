import { describe, expect, it } from "vitest";
import { formatMean } from "./mean";

describe("formatMean", () => {
  it("rounds to two decimals with the project's separators and an explicit sign", () => {
    expect(formatMean(10.28348909657321)).toBe("+RD$10,28");
    expect(formatMean(-1572.7692307692307)).toBe("−RD$1.572,77");
    expect(formatMean(1234567.891)).toBe("+RD$1.234.567,89");
    expect(formatMean(0)).toBe("+RD$0,00");
  });
  it("never shows a minus sign for a value that rounds to zero", () => {
    expect(formatMean(-0.001)).toBe("+RD$0,00");
    expect(formatMean(-0)).toBe("+RD$0,00");
  });
});
