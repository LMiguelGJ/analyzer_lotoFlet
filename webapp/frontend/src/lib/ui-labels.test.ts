import { describe, expect, it } from "vitest";
import type { SelectorKind, SettlementMode, StakingStyle } from "../api/types";
import {
  FIELD_HELP_DELTA,
  FIELD_HELP_SEED,
  FIELD_LABEL_DELTA,
  FIELD_LABEL_SEED,
  FIELD_LABEL_SETTLEMENT,
  FIELD_LABEL_STAKING,
  HISTORICAL_CAVEAT,
  SELECTOR_LABELS,
  SETTLEMENT_LABELS,
  STAKING_DESCRIPTIONS,
  STAKING_LABELS,
} from "./ui-labels";

const SELECTOR_VALUES: SelectorKind[] = ["system", "blend", "random", "parity"];
const STAKING_VALUES: StakingStyle[] = ["flat", "ladder", "bold"];
const SETTLEMENT_VALUES: SettlementMode[] = ["all", "best"];

describe("ui-labels", () => {
  it("is exhaustive for every SelectorKind value", () => {
    expect(Object.keys(SELECTOR_LABELS).sort()).toEqual([...SELECTOR_VALUES].sort());
  });

  it.each(SELECTOR_VALUES)("gives selector %s a non-empty label distinct from its raw key", (key) => {
    expect(SELECTOR_LABELS[key]).toBeTruthy();
    expect(SELECTOR_LABELS[key]).not.toBe(key);
  });

  it("is exhaustive for every StakingStyle label and description", () => {
    expect(Object.keys(STAKING_LABELS).sort()).toEqual([...STAKING_VALUES].sort());
    expect(Object.keys(STAKING_DESCRIPTIONS).sort()).toEqual([...STAKING_VALUES].sort());
  });

  it.each(STAKING_VALUES)("gives staking %s a non-empty label distinct from its raw key", (key) => {
    expect(STAKING_LABELS[key]).toBeTruthy();
    expect(STAKING_LABELS[key]).not.toBe(key);
  });

  it.each(STAKING_VALUES)("gives staking %s a non-empty description", (key) => {
    expect(STAKING_DESCRIPTIONS[key]).toBeTruthy();
  });

  it("is exhaustive for every SettlementMode value", () => {
    expect(Object.keys(SETTLEMENT_LABELS).sort()).toEqual([...SETTLEMENT_VALUES].sort());
  });

  it.each(SETTLEMENT_VALUES)("gives settlement %s a non-empty label distinct from its raw key", (key) => {
    expect(SETTLEMENT_LABELS[key]).toBeTruthy();
    expect(SETTLEMENT_LABELS[key]).not.toBe(key);
  });

  it("keeps the seed range, shared-per-draw scope and reproducibility together", () => {
    expect(FIELD_HELP_SEED).toContain("repetir la selección aleatoria con las mismas condiciones");
    expect(FIELD_HELP_SEED).toContain("0 a 9.007.199.254.740.991");
    expect(FIELD_HELP_SEED).toContain("por sorteo entre todas las estrategias");
  });

  it("exposes non-empty field-label constants fixed by the plan", () => {
    for (const value of [
      FIELD_LABEL_STAKING,
      FIELD_LABEL_SETTLEMENT,
      FIELD_LABEL_SEED,
      FIELD_HELP_SEED,
      FIELD_LABEL_DELTA,
      FIELD_HELP_DELTA,
      HISTORICAL_CAVEAT,
    ]) {
      expect(value).toBeTruthy();
    }
  });
});
