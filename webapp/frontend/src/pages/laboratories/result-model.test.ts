import { describe, expect, it } from "vitest";
import { formatAbsoluteDOP, formatReturnOnWagered, isValidLaboratoryWallet, returnOnWagered } from "./result-model";

describe("certified wallet presentation", () => {
  const wallet = { policy: "retain-gains-top-up-v1", out_of_pocket: 2000, final_wealth: 2800 } as const;
  it("accepts only known-policy safe non-negative values matching the existing net", () => {
    expect(isValidLaboratoryWallet(wallet, 800)).toBe(true);
    expect(isValidLaboratoryWallet({ ...wallet, policy: "unknown" }, 800)).toBe(false);
    expect(isValidLaboratoryWallet({ ...wallet, out_of_pocket: -1 }, 800)).toBe(false);
    expect(isValidLaboratoryWallet({ ...wallet, final_wealth: Number.MAX_SAFE_INTEGER + 1 }, 800)).toBe(false);
    expect(isValidLaboratoryWallet({ ...wallet, final_wealth: 2801 }, 800)).toBe(false);
    expect(isValidLaboratoryWallet(undefined, 800)).toBe(false);
  });
  it("formats absolute amounts without a sign and refuses invalid amounts", () => {
    expect(formatAbsoluteDOP(2000)).toBe("RD$2.000");
    expect(formatAbsoluteDOP(0)).toBe("RD$0");
    expect(formatAbsoluteDOP(-1)).toBe("No disponible");
    expect(formatAbsoluteDOP(Number.MAX_SAFE_INTEGER + 1)).toBe("No disponible");
    expect(formatAbsoluteDOP(null)).toBe("No disponible");
  });
});

describe("historical return presentation", () => {
  it.each([
    [-1482496, 30303350, "−4,89 %"],
    [50, 100, "+50,00 %"],
    [0, 100, "+0,00 %"],
    [-0, 100, "+0,00 %"],
    [-1, 1000000, "+0,00 %"],
    [0, 0, "No disponible"],
  ])("formats %s over %s as %s", (net, wagered, expected) => {
    expect(formatReturnOnWagered(returnOnWagered(net, wagered))).toBe(expected);
    if (wagered === 0) expect(returnOnWagered(net, wagered)).toBeNull();
    else expect(Object.is(returnOnWagered(net, wagered), -0)).toBe(false);
  });
  it("divides before multiplying, without an overflowing intermediate", () => {
    expect(returnOnWagered(Number.MAX_VALUE, Number.MAX_VALUE)).toBe(100);
  });
});
