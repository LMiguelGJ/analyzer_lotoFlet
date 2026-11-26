import { describe, expect, it } from "vitest";
import { deadlineSummary, formatAbsoluteDOP, formatAverageDays, formatPercentShare, formatReturnOnWagered, isValidLaboratoryWallet, returnOnWagered, validYearResults, yearRowPresentation } from "./result-model";

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

describe("deadline presentation", () => {
  const base = { completed: 10, incomplete: 1, goals: 6, ruins: 1, sessions_total: 11, total_wagered: 0, total_paid: 0, total_net: 0, total_steps: 0, mean_net_closed: 0 };
  it("is absent for results of laboratories without a deadline", () => {
    expect(deadlineSummary(base)).toBeNull();
  });
  it("derives the share and the average days from the closed sessions", () => {
    expect(deadlineSummary({ ...base, timeouts: 3, timeout_net: -450, goal_draws: 120 })).toEqual({
      goalsInTime: 6, timeouts: 3, ruins: 1, inTimePercent: 60, averageDaysToGoal: 20, timeoutNet: -450,
    });
    expect(formatPercentShare(60)).toBe("60,0 %");
    expect(formatAverageDays(20)).toBe("20,0 días");
  });
  it("says so when nothing can be computed", () => {
    const empty = deadlineSummary({ ...base, completed: 0, goals: 0, ruins: 0, timeouts: 0 });
    expect(empty).toMatchObject({ inTimePercent: null, averageDaysToGoal: null, timeoutNet: null });
    expect(formatPercentShare(null)).toBe("No disponible");
    expect(formatAverageDays(null)).toBe("No disponible");
  });
});

describe("result by year presentation", () => {
  const row = { year: 2019, net: 379, goals: 80, ruins: 0, timeouts: 0, sessions_closed: 80, return_pct: 7.58 };
  it("marks gains with an up arrow, losses with a down arrow and zero as even; colour is never the only cue", () => {
    expect(yearRowPresentation(row)).toEqual({ state: "gain", net: "▲ +RD$379", label: "ganancia de RD$379", percent: "+7,58 %" });
    expect(yearRowPresentation({ ...row, net: -1250, return_pct: -25 })).toEqual({ state: "loss", net: "▼ −RD$1.250", label: "pérdida de RD$1.250", percent: "−25,00 %" });
    expect(yearRowPresentation({ ...row, net: 0, return_pct: 0 })).toEqual({ state: "even", net: "= RD$0", label: "sin ganancia ni pérdida", percent: "+0,00 %" });
  });
  it("accepts only a non-empty list of well-formed rows, otherwise the table stays hidden", () => {
    expect(validYearResults([row])).toEqual([row]);
    expect(validYearResults(null)).toBeNull();
    expect(validYearResults(undefined)).toBeNull();
    expect(validYearResults([])).toBeNull();
    expect(validYearResults([{ ...row, net: 1.5 }])).toBeNull();
    expect(validYearResults([{ ...row, year: "2019" }])).toBeNull();
    expect(validYearResults([row, { year: 2020 }])).toBeNull();
  });
});
