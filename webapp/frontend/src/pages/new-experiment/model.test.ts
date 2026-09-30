import { describe, expect, it } from "vitest";
import { buildRequest, buildStrategy, draftFromRequest, draftFromStrategy, initialConditions, integer, newStrategy, normalizeStrategyName, trimName, validateConditions, validateStrategies } from "./model";
import type { Catalog } from "../../api/types";
import nameCases from "../../../../backend/tests/fixtures/strategy_name_cases.json";

const catalog: Catalog = { game: { name: "Quiniela 80", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true }, systems: { transition: "Transición", cold: "Fríos" }, selectors: ["system", "blend", "random", "parity"], coverages: [1, 5, 10, 20, 25, 30, 40, 50], parity_coverage: 50, starting_draws: ["2025-09-02 05:10"], starting_draws_total: 1, sources: { history_sha256: "", rankings_sha256: "", history_id: "", rankings_id: "", code_version: "" } };
const valid = { ...initialConditions, name: "Ejemplo", start_draw: "2025-09-02 05:10", capital: "2000", goal: "2800", seed: "0" };
const draws = [valid.start_draw];

describe("wire contract validation", () => {
  it("round-trips one library strategy without substituting the library name", () => {
    const strategy = { name: "Estrategia", selector: "blend" as const, components: [{ system: "transition", weight: 60 }, { system: "cold", weight: 40 }], coverage: 10, staking: "bold" as const };
    const draft = draftFromStrategy(strategy, 7);
    expect(draft).toMatchObject({ id: 7, name: "Estrategia", components: [{ weight: "60" }, { weight: "40" }] });
    expect(buildStrategy(draft, catalog)).toEqual(strategy);
  });
  it("prefills every saved request field and all mix components without rounding or mutating the source", () => {
    const request = buildRequest({ ...valid, max_minutes: "90", seed: "9007199254740991" }, [
      { ...newStrategy(1), name: "Mix", selector: "blend", coverage: "10", staking: "bold", components: [{ system: "transition", weight: "60" }, { system: "cold", weight: "40" }] },
    ], catalog);
    const snapshot = JSON.stringify(request);
    const draft = draftFromRequest(request);
    expect(draft.conditions).toEqual({ ...valid, max_minutes: "90", seed: "9007199254740991" });
    expect(draft.strategies[0]).toMatchObject({ name: "Mix", selector: "blend", coverage: "10", staking: "bold", components: [{ system: "transition", weight: "60" }, { system: "cold", weight: "40" }] });
    draft.strategies[0].components[0].weight = "70";
    expect(JSON.stringify(request)).toBe(snapshot);
  });
  it("rejects decimals, exponents, negatives, overflow, invalid ranked start and equal final goal", () => {
    expect(integer("1.1", 0n, 10n)).toBeNull();
    expect(integer("1e2", 0n, 100n)).toBeNull();
    expect(integer("-1", 0n, 100n)).toBeNull();
    expect(validateConditions({ ...valid, start_draw: "2025-09-02 05:15", capital: "2.5", goal: "2800", max_minutes: "0", max_bets: "10000001", seed: "9007199254740992" }, draws)).toMatchObject({ start_draw: expect.any(String), capital: expect.any(String), max_minutes: expect.any(String), max_bets: expect.any(String), seed: expect.any(String) });
    expect(validateConditions({ ...valid, goal: "2000" }, draws).goal).toMatch(/superar/);
    expect(validateConditions(valid, draws)).toEqual({});
  });
  it("accepts the max safe integer seed, sends it as a JSON number and rejects one above it", () => {
    const conditions = { ...valid, seed: "9007199254740991" };
    expect(validateConditions(conditions, draws)).toEqual({});
    const strategy = { ...newStrategy(1), name: "Una", system: "transition" };
    expect(buildRequest(conditions, [strategy], catalog).conditions.seed).toBe(9007199254740991);
    expect(validateConditions({ ...valid, seed: "9007199254740992" }, draws).seed).toEqual(expect.any(String));
  });
  it("round-trips the entered seed through a backend-shaped JSON response", () => {
    const entered = 9007199254740991;
    const responseBody = JSON.stringify({ conditions: { seed: entered } });
    const parsed: { conditions: { seed: number } } = JSON.parse(responseBody);
    expect(parsed.conditions.seed).toBe(entered);
  });
  it("agrees with the backend's duplicate-name verdict for every case in the shared fixture", () => {
    for (const testCase of nameCases as { category: string; a: string; b: string; duplicate: boolean }[]) {
      const equal = normalizeStrategyName(testCase.a) === normalizeStrategyName(testCase.b);
      expect(equal, testCase.category).toBe(testCase.duplicate);
      const first = { ...newStrategy(1), name: testCase.a, system: "transition" };
      const second = { ...newStrategy(2), name: testCase.b, system: "transition" };
      const errors = validateStrategies([first, second], catalog);
      expect(!!errors["strategies.1.name"], testCase.category).toBe(testCase.duplicate);
    }
  });
  it("trims a stored name with the same explicit charset used for duplicate detection, keeping BOM/NEL as-is", () => {
    // U+FEFF and U+0085 are excluded from the shared trim charset on both sides, so
    // buildRequest must not fall back to JS's built-in trim(), which strips U+FEFF.
    expect(trimName("\uFEFFName")).toBe("\uFEFFName");
    expect(trimName("\x85Name")).toBe("\x85Name");
    expect(trimName("\tName\t")).toBe("Name");
    const strategy = { ...newStrategy(1), name: "\uFEFFUna", system: "transition" };
    const built = buildRequest({ ...valid }, [strategy], catalog);
    expect(built.strategies[0].name).toBe("\uFEFFUna");
    expect(built.name).toBe(valid.name);
  });
  it("rejects duplicate names, six strategies, invalid mix sums and repeated systems", () => {
    const first = { ...newStrategy(1), name: " Una ", system: "transition" };
    expect(validateStrategies([first, { ...first, id: 2, name: "una" }], catalog)["strategies.1.name"]).toMatch(/único/);
    expect(validateStrategies(Array.from({ length: 6 }, (_, i) => ({ ...first, id: i, name: `n${i}` })), catalog).strategies).toMatch(/1 y 5/);
    const blend = { ...first, selector: "blend" as const, components: [{ system: "transition", weight: "60" }, { system: "transition", weight: "30" }] };
    const errors = validateStrategies([blend], catalog);
    expect(errors["strategies.0.components"]).toMatch(/100/);
    expect(errors["strategies.0.components.1.system"]).toMatch(/distinto/);
  });
});
