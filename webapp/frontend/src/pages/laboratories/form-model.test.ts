import { describe, expect, it } from "vitest";
import { DEFAULT_FORM, buildDefaultForm, parseLaboratoryForm, prizeFieldsFor, systemChoices } from "./form-model";

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

  it("leaves the deadline out of the config when the field is empty and sends it when set", () => {
    const empty = parseLaboratoryForm({ ...valid, max_session_draws: "   " });
    expect(empty.ok && "max_session_draws" in empty.value.config).toBe(false);
    const set = parseLaboratoryForm({ ...valid, max_session_draws: " 30 " });
    expect(set.ok && set.value.config.max_session_draws).toBe(30);
  });

  it.each(["0", "-3", "1.5", "abc", "10001"])("refuses %s as maximum days per session", (raw) => {
    const result = parseLaboratoryForm({ ...valid, max_session_draws: raw });
    expect(result.ok).toBe(false);
    expect(!result.ok && result.errors.max_session_draws).toMatch(/entre 1 y 10000/);
  });

  it("rejects names above 120 UTF-8 bytes and control characters", () => {
    expect(parseLaboratoryForm({ ...valid, name: "é".repeat(61) }).ok).toBe(false);
    expect(parseLaboratoryForm({ ...valid, name: "é".repeat(60) }).ok).toBe(true);
    expect(parseLaboratoryForm({ ...valid, name: "a\tb" }).ok).toBe(false);
  });
});

describe("form model per list", () => {
  const leidsaOptions = {
    list: { id: "leidsa_quiniela", name: "Quiniela Leidsa", positions: 3 },
    systems: [{ id: "cold", label: "Fríos", available: true }, { id: "transition", label: "Transición", available: false, reason: "No disponible para esta lista" }],
    prizes: [60, 8, 4], window: { start: "2023-01-04 14:55", end: "2026-11-16 20:55" }, history_sha256: "e".repeat(64),
  };
  it("builds Leidsa defaults from the options and sends exactly three prizes", () => {
    const form = buildDefaultForm(leidsaOptions);
    expect([form.prize_1, form.prize_2, form.prize_3]).toEqual(["60", "8", "4"]);
    expect(form.window_start).toBe("2023-01-04 14:55");
    expect(form.system).toBe("cold");
    const result = parseLaboratoryForm({ ...form, name: "Leidsa" }, 3);
    expect(result.ok && result.value.config.prizes).toEqual([60, 8, 4]);
  });
  it("ignores unused prize fields for a three-position list but still checks the used ones", () => {
    const form = { ...buildDefaultForm(leidsaOptions), name: "Leidsa", prize_4: "x" };
    expect(parseLaboratoryForm(form, 3).ok).toBe(true);
    const bad = parseLaboratoryForm({ ...form, prize_2: "0" }, 3);
    expect(bad.ok === false && Object.keys(bad.errors)).toEqual(["prize_2"]);
  });
  it("keeps Chance Express on its archived six systems regardless of the options payload", () => {
    const choices = systemChoices({ ...leidsaOptions, list: { id: "chance_express", name: "Loteka Chance Express", positions: 5 }, systems: [] });
    expect(choices.map((choice) => choice.value)).toEqual(["transition", "cold", "select_interpretable", "mix", "ensemble", "parity"]);
    expect(prizeFieldsFor(5)).toHaveLength(5);
    expect(prizeFieldsFor(3)).toEqual(["prize_1", "prize_2", "prize_3"]);
  });
});
