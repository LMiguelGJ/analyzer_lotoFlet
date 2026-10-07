import { describe, expect, it } from "vitest";
import { applyHistoricalStrategyDraft, historicalStrategyToDraft, strategyDraftFromBacktest } from "./historical-strategy-compatibility";
import type { BacktestDraft } from "./backtest-model";

const saved = (overrides: object = {}) => ({
  name: " Mi método ", selector: "system", system: "cold", components: null,
  coverage: 17, staking: "ladder", ...overrides,
} as never);

describe("historical strategy compatibility", () => {
  it("adapts only historical-compatible configurations without losing their strategy fields", () => {
    const draft = historicalStrategyToDraft(saved());
    expect(draft).toMatchObject({ name: " Mi método ", selector: "system", system: "cold", coverage: "17", staking: "ladder", components: [] });
    const backtest = { name: "Run", parity: false, system: "cold", strategyName: " Mi método ", coverage: "17", staking: "ladder" } as BacktestDraft;
    expect(strategyDraftFromBacktest(backtest)).toMatchObject({ name: " Mi método ", selector: "system", system: "cold", coverage: "17", staking: "ladder", components: [] });
    expect(applyHistoricalStrategyDraft({ ...backtest, numbers: "80" }, draft!)).toMatchObject({ parity: false, system: "cold", strategyName: " Mi método ", coverage: "17", staking: "ladder", numbers: "80" });
  });

  it.each([
    saved({ selector: "blend", components: [{ system: "cold", weight: 100 }] }),
    saved({ selector: "random" }), saved({ system: "other" }), saved({ selector: "parity", system: "cold", coverage: 50 }),
    saved({ selector: "parity", system: null, components: [], coverage: 17 }),
    saved({ selector: "system", components: [{ system: "cold", weight: 100 }] }),
  ])("rejects unsupported or malformed saved strategies", (strategy) => {
    expect(historicalStrategyToDraft(strategy)).toBeNull();
  });

  it.each([1, 17, 49, 50])("preserves historical parity coverage %s through the library, editor and backtest draft", (coverage) => {
    const strategy = historicalStrategyToDraft(saved({ selector: "parity", system: null, coverage }));
    expect(strategy).toMatchObject({ name: " Mi método ", selector: "parity", coverage: String(coverage), system: "" });
    const current = { name: "Run", parity: false, system: "cold", coverage: "1", staking: "flat", numbers: "100" } as BacktestDraft;
    const backtest = applyHistoricalStrategyDraft(current, strategy!)!;
    expect(backtest).toMatchObject({ name: "Run", strategyName: " Mi método ", parity: true, coverage: String(coverage), staking: "ladder" });
    expect(strategyDraftFromBacktest(backtest)).toEqual(strategy);
  });

  it.each([0, -1, 17.5, 51, NaN, Infinity, -Infinity])("rejects invalid parity coverage %s in saved strategies and editor updates", (coverage) => {
    expect(historicalStrategyToDraft(saved({ selector: "parity", system: null, coverage }))).toBeNull();
    const current = { numbers: "100", parity: true, coverage: "17" } as BacktestDraft;
    const strategy = { id: 1, name: "Paridad", selector: "parity", system: "", components: [], coverage: String(coverage), staking: "flat" } as const;
    expect(applyHistoricalStrategyDraft(current, { ...strategy, components: [] })).toBeNull();
  });

  it("rejects parity coverage beyond the native game and retains structural rejection", () => {
    const parity = saved({ selector: "parity", system: null, coverage: 17 });
    expect(historicalStrategyToDraft(parity, 17)).not.toBeNull();
    expect(historicalStrategyToDraft(parity, 16)).toBeNull();
    expect(historicalStrategyToDraft(saved({ staking: "other" }))).toBeNull();
    const strategy = historicalStrategyToDraft(parity)!;
    const current = { numbers: "16", parity: true, coverage: "1" } as BacktestDraft;
    expect(applyHistoricalStrategyDraft(current, strategy)).toBeNull();
    expect(applyHistoricalStrategyDraft({ ...current, numbers: "100" }, { ...strategy, system: "cold" })).toBeNull();
    expect(applyHistoricalStrategyDraft({ ...current, numbers: "100" }, { ...strategy, components: [{ system: "cold", weight: "100" }] })).toBeNull();
  });
});
