import { describe, expect, it } from "vitest";
import { optionsFixture, runFixture } from "./test-fixtures";
import { createInitialRunForm, formatStrategyLabel, parseIntegerInput, resizePrizes, validateRunForm, toCreateRunRequest } from "./run-model";

describe("run form model", () => {
  it("uses API defaults and fills extra position prizes with one", () => {
    const form = createInitialRunForm(optionsFixture);
    expect(form.positions).toBe("3");
    expect(form.prizes).toEqual(["60", "10", "5"]);
    expect(resizePrizes(["60", "10", "5"], 5)).toEqual(["60", "10", "5", "1", "1"]);
  });

  it("preserves valid entered prizes across position resizing", () => {
    expect(resizePrizes(["12", "", "3", "4"], 3)).toEqual(["12", "", "3"]);
    expect(resizePrizes(["12", "3"], 4)).toEqual(["12", "3", "1", "1"]);
  });

  it.each([["", null], ["1.2", null], ["2e2", null], [" 2", null], ["0", 0], ["20", 20]])("validates raw integer input %j without truncation", (value, expected) => {
    expect(parseIntegerInput(value as string)).toEqual(expected);
  });

  it("validates capitals, goals, percentages, date order and strict numeric fields", () => {
    const form = createInitialRunForm(optionsFixture);
    expect(validateRunForm(form, optionsFixture).errors).toEqual({});
    expect(validateRunForm({ ...form, capital: "19", coverage: "10", minimumStake: "2" }, optionsFixture).errors.capital).toMatch(/cobertura/);
    expect(validateRunForm({ ...form, goal: "2000" }, optionsFixture).errors.goal).toMatch(/superior/);
    expect(validateRunForm({ ...form, components: [{ system: "transition", percent: "50" }, { system: "cold", percent: "40" }] }, optionsFixture).errors.components).toMatch(/100/);
    expect(validateRunForm({ ...form, startDate: "2026-03-02", endDate: "2026-03-01" }, optionsFixture).errors.endDate).toMatch(/posterior/);
    expect(validateRunForm({ ...form, startDate: "2025-02-30" }, optionsFixture).errors.startDate).toMatch(/fecha válida/);
    expect(validateRunForm({ ...form, components: [{ system: "transition", percent: "60" }, { system: "transition", percent: "40" }] }, optionsFixture).errors.components).toMatch(/repitas/);
    expect(validateRunForm({ ...form, maxDraws: "" }, optionsFixture).errors.maxDraws).toBeUndefined();
    expect(validateRunForm({ ...form, maxDraws: "2.5" }, optionsFixture).errors.maxDraws).toBeDefined();
  });

  it("submits parity without mix components and pins the selected history SHA", () => {
    const form = { ...createInitialRunForm(optionsFixture), kind: "parity" as const, historySha: optionsFixture.history.sha256 };
    const result = validateRunForm(form, optionsFixture);
    expect(result.errors).toEqual({});
    expect(toCreateRunRequest(form, optionsFixture)).toMatchObject({ strategy: { kind: "parity", components: [], coverage: 10 }, history_sha256: optionsFixture.history.sha256 });
  });

  it("translates strategy IDs from the API catalog and avoids exposing unknown IDs", () => {
    expect(formatStrategyLabel(runFixture.config.strategy, optionsFixture.systems)).toBe("Transición 60 % + Fríos 40 % · 10 números");
    expect(formatStrategyLabel({ kind: "parity", components: [], coverage: 10 }, optionsFixture.systems)).toBe("Paridad · 10 números");
    expect(formatStrategyLabel({ kind: "mix", components: [{ system: "stale-secret-id", percent: 100 }], coverage: 3 }, optionsFixture.systems)).toBe("Sistema no disponible 100 % · 3 números");
  });

  it("clones a saved configuration including its history fingerprint", () => {
    const form = createInitialRunForm(optionsFixture, runFixture);
    expect(form.name).toBe(runFixture.name);
    expect(form.historySha).toBe(runFixture.config.history.sha256);
    expect(form.positions).toBe("3");
  });
});
