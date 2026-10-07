import { describe, expect, it } from "vitest";
import { buildProfileRequest } from "./profile-model";
import { profileItem, datasetItem, validDraft, cyclingProfile, audazProfile, recoveryProfile, audazDataset, recoveryDataset } from "./profile-model.test";
import { draftFromSavedProfileRequest, buildSavedProfileRepeatRequest } from "./profile-repeat-model";

describe("saved profile repeat versions 1–4", () => {
  it.each([
    [cyclingProfile, datasetItem, "cycling", "q80-first-prize-cycling/v1"],
    [audazProfile, audazDataset, "audaz", "profile-audaz/v1"],
    [recoveryProfile, recoveryDataset, "recovery", "profile-recovery-ladder/v1"],
  ] as const)("hydrates and repeats %s directly without flat capability or a synthetic stake", (profile, dataset, policy, capability) => {
    const nativeProfile = { ...profile, profile_execution: { ...profile.profile_execution, staking_capabilities: [capability] } };
    const source = { ...validDraft, coverage: "1", numbers: "0", per_number_stake: "", capital: "2000", goal: "2800",
      target_margin: "12.34", rounds: "4", end_mode: "stop" as const };
    const original = buildProfileRequest(source, nativeProfile, dataset, source.start_draw, policy);
    original.conditions.max_elapsed_draws = null;
    original.conditions.duration_minutes = 45;
    const draft = draftFromSavedProfileRequest(original, nativeProfile, dataset);
    expect(draft.per_number_stake).toBe("");
    expect(buildSavedProfileRepeatRequest(draft, original, nativeProfile, dataset, source.start_draw)).toEqual(original);
    expect(nativeProfile.profile_execution.staking_capabilities).toEqual([capability]);
    expect(() => draftFromSavedProfileRequest({ ...original, selector: { ...original.selector, seed: 1 } }, nativeProfile, dataset)).toThrow();
    expect(() => draftFromSavedProfileRequest({ ...original, conditions: { ...original.conditions, capital: 1.5 } }, nativeProfile, dataset)).toThrow();
    expect(() => buildSavedProfileRepeatRequest({ ...draft, goal: "1" }, original, nativeProfile, dataset, source.start_draw)).toThrow();
  });
  it.each([
    [profileItem, datasetItem, "fixed"], [cyclingProfile, datasetItem, "cycling"],
    [audazProfile, audazDataset, "audaz"], [recoveryProfile, recoveryDataset, "recovery"],
  ] as const)("preserves schema and immutable source while changing only edited controls", (profile, dataset, policy) => {
    const sourceDraft = policy === "cycling" ? { ...validDraft, capital: "2000", goal: "2800", coverage: "2", numbers: "0, 1", per_number_stake: "" } :
      policy === "audaz" ? { ...validDraft, coverage: "1", numbers: "0", per_number_stake: "" } :
      { ...validDraft, target_margin: "12.00", rounds: "4", end_mode: "stop" };
    const original = buildProfileRequest({ ...sourceDraft, target_margin: "12", rounds: "4", end_mode: "stop" }, profile, dataset, validDraft.start_draw, policy);
    original.conditions.end_minute = Math.floor(Date.parse("2025-01-01T05:10:00Z") / 60_000) + 30;
    const draft = draftFromSavedProfileRequest(original, profile, dataset);
    const next = buildSavedProfileRepeatRequest({ ...draft, name: "Repetición", capital: "2100" }, original, profile, dataset, validDraft.start_draw);
    expect(next).toMatchObject({ schema_version: original.schema_version, name: "Repetición",
      conditions: { capital: 2100 * 10 ** profile.profile.scale, end_minute: original.conditions.end_minute }, selector: original.selector, staking: original.staking });
    expect(original.name).toBe(validDraft.name.trim());
    expect(() => draftFromSavedProfileRequest({ ...original, profile_sha256: "f".repeat(64) }, profile, dataset)).toThrow();
  });

  it.each([
    ["cycling coverage ceiling", { ...cyclingProfile, profile: { ...cyclingProfile.profile, max_coverage: 100 } }, datasetItem, "cycling", "80", Array.from({ length: 80 }, (_, index) => index).join(", ")],
    ["Audaz compatibility ceiling", audazProfile, audazDataset, "audaz", "2", "0, 1"],
  ] as const)("rejects edits outside the saved v%s policy contract", (_label, profile, dataset, policy, coverage, numbers) => {
    const draft = policy === "cycling"
      ? { ...validDraft, capital: "2000", goal: "2800", coverage: "1", numbers: "0", per_number_stake: "" }
      : { ...validDraft, coverage: "1", numbers: "0", per_number_stake: "" };
    const original = buildProfileRequest(draft, profile, dataset, validDraft.start_draw, policy);
    const hydrated = draftFromSavedProfileRequest(original, profile, dataset);
    expect(() => buildSavedProfileRepeatRequest({ ...hydrated, coverage, numbers }, original, profile, dataset,
      validDraft.start_draw)).toThrow();
  });
});
