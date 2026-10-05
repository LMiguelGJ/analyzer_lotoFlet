import { describe, expect, it } from "vitest";
import { exactMultiplier, moneyUnits, wholeNumber } from "./profile-input";

describe("exact profile input", () => {
  it("# F-UTIL-004 reduces decimal and fractional multipliers without binary floating point", () => {
    expect(exactMultiplier("1.25", "Premio")).toEqual({ numerator: 5, denominator: 4 });
    expect(exactMultiplier("0.000000000001", "Premio")).toEqual({ numerator: 1, denominator: 1_000_000_000_000 });
    expect(exactMultiplier("60", "Premio")).toEqual({ numerator: 60, denominator: 1 });
    expect(exactMultiplier("10/20", "Premio")).toEqual({ numerator: 1, denominator: 2 });
  });
  it("# F-UTIL-005 rejects missing, invalid, negative and oversafe rational parts", () => {
    for (const value of ["", "1/", "1/0", "1.2/3", "-1", "1e2", "0.0000000000001", "9007199254740992"]) {
      expect(() => exactMultiplier(value, "Premio")).toThrow();
    }
  });
  it("# F-UTIL-006 converts human money to exact integer units at declared scale", () => {
    expect(moneyUnits("12.34", 2, "Importe")).toBe(1234);
    expect(moneyUnits("0.01", 2, "Importe")).toBe(1);
    expect(moneyUnits("1", 6, "Importe")).toBe(1_000_000);
    for (const value of ["", "0", "1.001", "1e4", "-1", "9007199254740992", "0.001"]) {
      expect(() => moneyUnits(value, 2, "Importe")).toThrow();
    }
    expect(() => moneyUnits("1000000000000", 2, "Importe")).toThrow();
  });
  it("# F-UTIL-007 enforces bounded integers before conversion to JS Number", () => {
    expect(wholeNumber("16", "Posiciones", 1n, 16n)).toBe(16);
    for (const value of ["", "0", "17", "1.0", "9007199254740992"]) {
      expect(() => wholeNumber(value, "Posiciones", 1n, 16n)).toThrow();
    }
  });
});
