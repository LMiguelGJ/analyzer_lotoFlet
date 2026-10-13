import { describe, expect, it } from "vitest";
import { DEFAULT_FORM, parseLaboratoryForm } from "./form-model";

const valid = { ...DEFAULT_FORM, name: "Mi laboratorio" };

describe("laboratory form model", () => {
  it("turns the prefilled fields into the exact config snapshot the API expects", () => {
    const result = parseLaboratoryForm(valid);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value).toEqual({
      name: "Mi laboratorio",
      config: {
        schema_version: 1,
        system: "transition",
        coverage: 1,
        stake_style: "bold",
        capital: 2000,
        goal: 2800,
        prizes: [80, 8, 4, 2, 1],
        window_start: "2025-09-02 05:10",
        window_end: "2026-09-25 18:20",
      },
    });
  });

  it("reports one named error per invalid field instead of failing silently", () => {
    const result = parseLaboratoryForm({ ...valid, name: "  ", coverage: "0", capital: "1.5", goal: "abc", window_start: "2025-13-01 00:00" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(Object.keys(result.errors).sort()).toEqual(["capital", "coverage", "goal", "name", "window_start"]);
    expect(result.errors.name).toMatch(/nombre/i);
  });

  it("enforces the cross-field rules the server enforces", () => {
    const parity = parseLaboratoryForm({ ...valid, system: "parity", coverage: "10" });
    expect(parity.ok === false && parity.errors.coverage).toMatch(/50/);
    const goal = parseLaboratoryForm({ ...valid, capital: "3000", goal: "2800" });
    expect(goal.ok === false && goal.errors.goal).toMatch(/mayor/);
    const prize = parseLaboratoryForm({ ...valid, coverage: "5", prize_1: "5" });
    expect(prize.ok === false && prize.errors.prize_1).toMatch(/mayor/);
    const order = parseLaboratoryForm({ ...valid, window_start: "2026-09-25 18:20", window_end: "2025-09-02 05:10" });
    expect(order.ok === false && order.errors.window_end).toMatch(/posterior/);
  });

  it("rejects names above 120 UTF-8 bytes and control characters", () => {
    expect(parseLaboratoryForm({ ...valid, name: "é".repeat(61) }).ok).toBe(false);
    expect(parseLaboratoryForm({ ...valid, name: "é".repeat(60) }).ok).toBe(true);
    expect(parseLaboratoryForm({ ...valid, name: "a\tb" }).ok).toBe(false);
  });
});
