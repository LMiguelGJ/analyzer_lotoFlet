import { describe, expect, it } from "vitest";
import { formatDOP, formatTwoDigit } from "./format";

describe("formatDOP", () => {
  it("formats a whole DOP amount with the currency symbol", () => {
    expect(formatDOP(2800)).toBe("RD$2.800");
  });

  it("formats zero", () => {
    expect(formatDOP(0)).toBe("RD$0");
  });

  it("formats negative balances", () => {
    expect(formatDOP(-500)).toBe("-RD$500");
  });

  it("rejects non-integer amounts, since the backend never sends decimals", () => {
    expect(() => formatDOP(2800.5)).toThrow(RangeError);
  });
});

describe("formatTwoDigit", () => {
  it("zero-pads single-digit numbers", () => {
    expect(formatTwoDigit(7)).toBe("07");
  });

  it("keeps two-digit numbers unpadded", () => {
    expect(formatTwoDigit(42)).toBe("42");
  });

  it("formats the boundaries 0 and 99", () => {
    expect(formatTwoDigit(0)).toBe("00");
    expect(formatTwoDigit(99)).toBe("99");
  });

  it("rejects values outside the Q80 range", () => {
    expect(() => formatTwoDigit(100)).toThrow(RangeError);
    expect(() => formatTwoDigit(-1)).toThrow(RangeError);
  });

  it("rejects non-integers", () => {
    expect(() => formatTwoDigit(4.5)).toThrow(RangeError);
  });
});
