import { describe, expect, it } from "vitest";
import type { DatasetListing, ProfileListing } from "../../api/types";
import * as profileModel from "./profile-model";
import { buildProfileRequest, initialProfileDraft, matchingDataset } from "./profile-model";

export const profileItem = {
  profile: { schema_version: 1, profile_id: "local-game", revision: 2, universe_size: 100,
    positions: 3, allows_repeats: true, multipliers: [{ numerator: 60, denominator: 1 },
      { numerator: 10, denominator: 1 }, { numerator: 5, denominator: 1 }], currency: "DOP", scale: 2,
    stake_increment: 25, minimum_stake: 25, maximum_stake: 10000, max_coverage: 10,
    max_exposure: 20000, best_rule: "maximum-payout/v1" },
  profile_sha256: "a".repeat(64), execution_supported: false,
  profile_execution: { ready: true, selector_capabilities: ["static-numbers/v1", "seeded-random/hash-sha256-v1"],
    staking_capabilities: ["flat-per-number/v1"], entry_policies: ["all_rows/v1"],
    settlements: ["all", "best"], requires_compatible_dataset: true,
    audaz_compatibility: { available: false, maximum_compatible_coverage: 0, coverage_rule: "selected coverage must be strictly less than multiplier[0]" },
    recovery_compatibility: { available: false, maximum_compatible_coverage: 0, coverage_rule: "selected coverage must be strictly less than multiplier[0]", parameters: ["target_margin", "rounds", "end_mode"] } },
} as ProfileListing;
export const datasetItem = {
  dataset_sha256: "b".repeat(64), profile_sha256: profileItem.profile_sha256,
  profile_id: "local-game", profile_revision: 2, profile_execution: profileItem.profile_execution,
  source_id: "local-json", source_revision: "v1", records_total: 201,
} as DatasetListing;
export const validDraft = { ...initialProfileDraft, name: "  Sesión local ", start_draw: "2025-01-01 05:10",
  capital: "2000.00", goal: "2800", max_elapsed_draws: "12", max_bet_draws: "6", settlement: "best" as const,
  selector: "static" as const, numbers: "0, 1", coverage: "2", per_number_stake: "1.25" };

export const cyclingProfile = { ...profileItem,
  profile: { ...profileItem.profile, positions: 5, scale: 0, stake_increment: 1,
    minimum_stake: 1, max_coverage: 79, multipliers: [80, 8, 4, 2, 1].map((numerator) => ({ numerator, denominator: 1 })) },
  profile_execution: { ...profileItem.profile_execution,
    staking_capabilities: ["flat-per-number/v1", "q80-first-prize-cycling/v1"] },
} as ProfileListing;

export const audazProfile = { ...profileItem,
  profile: { ...profileItem.profile, profile_id: "rational-game", positions: 2, currency: "EUR", scale: 2,
    multipliers: [{ numerator: 5, denominator: 4 }, { numerator: 3, denominator: 2 }], max_coverage: 8 },
  profile_execution: { ...profileItem.profile_execution,
    staking_capabilities: ["flat-per-number/v1", "profile-audaz/v1"],
    audaz_compatibility: { available: true, maximum_compatible_coverage: 1,
      coverage_rule: "selected coverage must be strictly less than multiplier[0]" } },
} as ProfileListing;
export const audazDataset = { ...datasetItem, profile_id: "rational-game", profile_sha256: audazProfile.profile_sha256,
  profile_execution: audazProfile.profile_execution } as DatasetListing;

export const recoveryProfile = { ...profileItem,
  profile: { ...profileItem.profile, profile_id: "rational-recovery", positions: 2, currency: "EUR", scale: 2,
    multipliers: [{ numerator: 5, denominator: 2 }, { numerator: 3, denominator: 2 }], max_coverage: 4,
    stake_increment: 5, minimum_stake: 5, maximum_stake: 5000, max_exposure: 10000 },
  profile_execution: { ...profileItem.profile_execution,
    staking_capabilities: ["flat-per-number/v1", "profile-recovery-ladder/v1"],
    recovery_compatibility: { available: true, maximum_compatible_coverage: 2,
      coverage_rule: "selected coverage must be strictly less than multiplier[0]", parameters: ["target_margin", "rounds", "end_mode"] } },
} as ProfileListing;
export const recoveryDataset = { ...datasetItem, profile_id: "rational-recovery", profile_sha256: recoveryProfile.profile_sha256,
  profile_execution: recoveryProfile.profile_execution } as DatasetListing;

describe("native profile step validation", () => {
  it("validates Strategy without future source or capital inputs", () => {
    const strategyOnly = { ...validDraft, name: "", start_draw: "", capital: "", goal: "", max_elapsed_draws: "", settlement: "" as const };
    expect(profileModel.validateProfileStrategy(strategyOnly, profileItem, "fixed").stake).toBe(125);
    expect(() => profileModel.validateProfileStrategy({ ...strategyOnly, numbers: "0,0" }, profileItem, "fixed")).toThrow(/Números/);
    expect(() => profileModel.validateProfileStrategy({ ...strategyOnly, per_number_stake: "1.26" }, profileItem, "fixed")).toThrow(/apuesta por número/i);
    expect(() => profileModel.validateProfileStrategy({ ...strategyOnly, selector: "random", seed: "-1" }, profileItem, "fixed")).toThrow(/Semilla/);
    expect(() => profileModel.validateProfileStrategy({ ...strategyOnly, target_margin: "12", rounds: "10001", end_mode: "stop" }, recoveryProfile, "recovery")).toThrow(/Rondas/);
  });
  it("validates exact native money and limits at Capital, retaining nullable repeat bounds", () => {
    expect(profileModel.validateProfileCapital(validDraft, profileItem)).toMatchObject({ capital: 200000, goal: 280000, max_elapsed_draws: 12 });
    expect(() => profileModel.validateProfileCapital({ ...validDraft, capital: "2000.001" }, profileItem)).toThrow(/decimales/);
    expect(() => profileModel.validateProfileCapital({ ...validDraft, goal: "2000" }, profileItem)).toThrow(/superar/);
    expect(() => profileModel.validateProfileCapital({ ...validDraft, max_elapsed_draws: "10001" }, profileItem)).toThrow(/Sorteos/);
    expect(() => profileModel.validateProfileCapital({ ...validDraft, max_bet_draws: "1.5" }, profileItem)).toThrow(/Sorteos/);
    expect(profileModel.validateProfileCapital({ ...validDraft, max_elapsed_draws: "" }, profileItem, true).max_elapsed_draws).toBeNull();
  });
});

describe("profile request v1 builder", () => {
  it("hydrates saved v1 requests for repeat without losing time conditions", () => {
    const request = buildProfileRequest(validDraft, profileItem, datasetItem, validDraft.start_draw);
    request.conditions.end_minute = Math.floor(Date.parse(`${request.conditions.start_draw.replace(" ", "T")}:00Z`) / 60_000) + 30;
    request.conditions.duration_minutes = 45;
    request.conditions.max_elapsed_draws = null;
    expect(typeof profileModel.draftFromProfileRequest).toBe("function");
    const draft = profileModel.draftFromProfileRequest(request, profileItem, datasetItem);
    expect(profileModel.buildProfileRepeatRequest(draft, request, profileItem, datasetItem, validDraft.start_draw)).toEqual(request);
    const before = structuredClone(request);
    const edited = profileModel.buildProfileRepeatRequest({ ...draft, name: "Nuevo", capital: "2100.00", coverage: "3",
      numbers: "0, 1, 2", per_number_stake: "1.50" }, request, profileItem, datasetItem, validDraft.start_draw);
    expect(edited).toMatchObject({ name: "Nuevo", conditions: { capital: 210000, end_minute: request.conditions.end_minute, duration_minutes: 45, max_elapsed_draws: null },
      selector: { coverage: 3, numbers: [0, 1, 2] }, staking: { per_number_stake: 150 } });
    expect(request).toEqual(before);
    expect(draft.name).toBe(request.name);
    expect(() => profileModel.draftFromProfileRequest({ ...request, schema_version: 2 }, profileItem, datasetItem)).toThrow();
    expect(() => profileModel.draftFromProfileRequest(request, profileItem, { ...datasetItem, dataset_sha256: "c".repeat(64) })).toThrow();
  });
  it("preserves nullable seeded selector fields and rejects edits that do not match verified draw", () => {
    const request = buildProfileRequest({ ...validDraft, selector: "random", seed: "0" }, profileItem, datasetItem, validDraft.start_draw);
    const draft = profileModel.draftFromProfileRequest(request, profileItem, datasetItem);
    expect(profileModel.buildProfileRepeatRequest(draft, request, profileItem, datasetItem, "different draw")).toEqual(request);
    expect(() => profileModel.buildProfileRepeatRequest({ ...draft, start_draw: "2025-01-02 05:10" }, request,
      profileItem, datasetItem, validDraft.start_draw)).toThrow(/Sorteo/);
    expect(profileModel.buildProfileRepeatRequest({ ...draft, start_draw: "2025-01-02 05:10" }, request,
      profileItem, datasetItem, "2025-01-02 05:10").conditions.start_draw).toBe("2025-01-02 05:10");
    expect(profileModel.buildProfileRepeatRequest({ ...draft, seed: "7" }, request, profileItem, datasetItem,
      validDraft.start_draw).selector).toEqual({ ...request.selector, seed: 7 });
  });
  it("# F-UTIL-020 builds explicit Q80 cycling without a fixed stake and rejects absent capability", () => {
    const draft = { ...validDraft, capital: "2000", goal: "2800", per_number_stake: "" };
    const request = buildProfileRequest(draft, cyclingProfile, datasetItem, draft.start_draw, "cycling");
    expect(request.schema_version).toBe(2);
    expect(request.staking).toEqual({ schema_version: 1, capability: "q80-first-prize-cycling/v1" });
    expect(JSON.stringify(request)).not.toContain("per_number_stake");
    expect(() => buildProfileRequest(draft, profileItem, datasetItem, draft.start_draw, "cycling")).toThrow(/capacidad/);
    expect(() => buildProfileRequest({ ...draft, coverage: "80" }, cyclingProfile, datasetItem, draft.start_draw, "cycling")).toThrow();
  });
  it("# F-UTIL-021 uses server binding, explicit fixed selector and integer money units without legacy envelope", () => {
    expect(buildProfileRequest(validDraft, profileItem, datasetItem, validDraft.start_draw)).toEqual({
      kind: "profile", schema_version: 1, name: "Sesión local", dataset_sha256: "b".repeat(64),
      profile_id: "local-game", profile_revision: 2, profile_sha256: "a".repeat(64), entry_policy: "all_rows/v1",
      conditions: { schema_version: 1, start_draw: validDraft.start_draw, capital: 200000, goal: 280000,
        settlement: "best", max_elapsed_draws: 12, max_bet_draws: 6, end_minute: null, duration_minutes: null },
      selector: { schema_version: 1, capability: "static-numbers/v1", coverage: 2, numbers: [0, 1],
        seed: null, algorithm_version: null },
      staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: 125 },
    });
  });
  it("# F-UTIL-022 builds generic Audaz schema 3 without a fixed stake using server rational-payout compatibility", () => {
    const draft = { ...validDraft, coverage: "1", numbers: "0", per_number_stake: "" };
    const request = buildProfileRequest(draft, audazProfile, { ...datasetItem,
      profile_id: "rational-game", profile_sha256: audazProfile.profile_sha256,
      profile_execution: audazProfile.profile_execution }, draft.start_draw, "audaz");
    expect(request.schema_version).toBe(3);
    expect(request.staking).toEqual({ schema_version: 1, capability: "profile-audaz/v1" });
    expect(JSON.stringify(request)).not.toContain("per_number_stake");
    expect(() => buildProfileRequest({ ...draft, coverage: "2" }, audazProfile, { ...datasetItem,
      profile_id: "rational-game", profile_sha256: audazProfile.profile_sha256,
      profile_execution: audazProfile.profile_execution }, draft.start_draw, "audaz")).toThrow(/hasta 1/);
    expect(() => buildProfileRequest(draft, { ...audazProfile, profile_execution: {
      ...audazProfile.profile_execution, audaz_compatibility: { available: false, maximum_compatible_coverage: 0,
        coverage_rule: "selected coverage must be strictly less than multiplier[0]" } } },
      { ...datasetItem, profile_id: "rational-game", profile_sha256: audazProfile.profile_sha256,
        profile_execution: audazProfile.profile_execution }, draft.start_draw, "audaz")).toThrow(/no está disponible/);
  });
  it.each(["cycle", "stop"] as const)("# F-UTIL-023 builds schema-4 recovery for a rational non-Q80 profile with %s exhaustion", (end_mode) => {
    const draft = { ...validDraft, coverage: "2", numbers: "0,1", per_number_stake: "", target_margin: "12.34", rounds: "4", end_mode };
    const request = buildProfileRequest(draft, recoveryProfile, recoveryDataset, draft.start_draw, "recovery");
    expect(request).toMatchObject({ schema_version: 4, selector: { coverage: 2 },
      staking: { schema_version: 1, target_margin: 1234, rounds: 4, end_mode } });
    expect(JSON.stringify(request)).not.toContain("per_number_stake");
  });
  it("# F-UTIL-023 rejects recovery coverage outside server-derived rational compatibility and missing parameters", () => {
    const base = { ...validDraft, per_number_stake: "", target_margin: "10", rounds: "3", end_mode: "stop" as const };
    expect(() => buildProfileRequest({ ...base, coverage: "3", numbers: "0,1,2" }, recoveryProfile, recoveryDataset, base.start_draw, "recovery")).toThrow(/hasta 2/);
    expect(() => buildProfileRequest({ ...base, rounds: "10001" }, recoveryProfile, recoveryDataset, base.start_draw, "recovery")).toThrow(/Rondas/);
    expect(() => buildProfileRequest({ ...base, end_mode: "" }, recoveryProfile, recoveryDataset, base.start_draw, "recovery")).toThrow(/completar la escalera/);
    expect(() => buildProfileRequest(base, { ...recoveryProfile, profile_execution: { ...recoveryProfile.profile_execution,
      staking_capabilities: ["flat-per-number/v1"], recovery_compatibility: { available: false, maximum_compatible_coverage: 0,
        coverage_rule: "selected coverage must be strictly less than multiplier[0]", parameters: [] } } }, recoveryDataset, base.start_draw, "recovery")).toThrow(/capacidad/);
  });
  it("# F-UTIL-024 builds deterministic random only with explicit safe seed and algorithm", () => {
    const request = buildProfileRequest({ ...validDraft, selector: "random", seed: "9007199254740991" }, profileItem, datasetItem, validDraft.start_draw);
    expect(request.selector).toEqual({ schema_version: 1, capability: "seeded-random/hash-sha256-v1",
      coverage: 2, numbers: null, seed: Number.MAX_SAFE_INTEGER, algorithm_version: "hash-sha256-v1" });
    expect(() => buildProfileRequest({ ...validDraft, selector: "random", seed: "9007199254740992" }, profileItem, datasetItem, validDraft.start_draw)).toThrow(/Semilla/);
  });
  it("# F-UTIL-025 rejects stale/mismatched binding, draw, unsupported capability and settlement", () => {
    expect(matchingDataset(profileItem, { ...datasetItem, profile_sha256: "c".repeat(64) })).toBe(false);
    expect(() => buildProfileRequest(validDraft, profileItem, { ...datasetItem, profile_revision: 3 }, validDraft.start_draw)).toThrow();
    expect(() => buildProfileRequest(validDraft, profileItem, datasetItem, "")).toThrow(/Sorteo/);
    expect(() => buildProfileRequest(validDraft, { ...profileItem, profile_execution: { ...profileItem.profile_execution, selector_capabilities: [] } }, datasetItem, validDraft.start_draw)).toThrow(/selección fija/);
    expect(() => buildProfileRequest({ ...validDraft, settlement: "" }, profileItem, datasetItem, validDraft.start_draw)).toThrow(/capacidad/);
  });
  it.each([
    [{ ...validDraft, numbers: "0, 0" }, /Números/],
    [{ ...validDraft, numbers: "0, 100" }, /Números/],
    [{ ...validDraft, per_number_stake: "1.26" }, /apuesta por número/i],
    [{ ...validDraft, per_number_stake: "100.01" }, /apuesta por número/i],
    [{ ...validDraft, capital: "9007199254740992" }, /Capital/],
    [{ ...validDraft, max_elapsed_draws: "" }, /Sorteos transcurridos/],
    [{ ...validDraft, goal: "1000" }, /meta/i],
  ])("# F-UTIL-026 rejects invalid admission inputs", (draft, message) => {
    expect(() => buildProfileRequest(draft, profileItem, datasetItem, validDraft.start_draw)).toThrow(message);
  });
});
