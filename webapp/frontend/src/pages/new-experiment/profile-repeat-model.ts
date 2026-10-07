import type { DatasetListing, ProfileAudazRequest, ProfileCyclingRequest, ProfileExperimentRequest, ProfileListing, ProfileRecoveryRequest } from "../../api/types";
import { draftFromProfileRequest, buildProfileRepeatRequest, initialProfileDraft, matchingDataset, validateProfileCapital, validateProfileStrategy } from "./profile-model";
import type { ProfileDraft, ProfilePolicy } from "./profile-model";

type SavedRequest = ProfileExperimentRequest | ProfileCyclingRequest | ProfileAudazRequest | ProfileRecoveryRequest;
const digest = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
function exactKeys(value: unknown, keys: string[]): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}
function formatMoney(value: number, scale: number): string {
  const factor = 10 ** scale;
  return scale ? `${Math.floor(value / factor)}.${String(value % factor).padStart(scale, "0")}` : String(value);
}
function version(value: unknown): value is SavedRequest {
  if (!exactKeys(value, ["kind", "schema_version", "name", "dataset_sha256", "profile_id", "profile_revision", "profile_sha256", "entry_policy", "conditions", "selector", "staking"])) return false;
  const conditions = value.conditions;
  const selector = value.selector;
  const staking = value.staking;
  const common = value.kind === "profile" && [1, 2, 3, 4].includes(value.schema_version as number) &&
    typeof value.name === "string" && value.name.trim().length > 0 && value.name.length <= 80 &&
    typeof value.profile_id === "string" && value.profile_id.length > 0 && Number.isSafeInteger(value.profile_revision) &&
    digest(value.profile_sha256) && digest(value.dataset_sha256) && value.entry_policy === "all_rows/v1" &&
    exactKeys(conditions, ["schema_version", "start_draw", "capital", "goal", "settlement", "max_elapsed_draws", "max_bet_draws", "end_minute", "duration_minutes"]) && conditions.schema_version === 1 &&
    exactKeys(selector, ["schema_version", "capability", "coverage", "numbers", "seed", "algorithm_version"]) && selector.schema_version === 1 &&
    typeof staking === "object" && staking !== null && !Array.isArray(staking) && (staking as Record<string, unknown>).schema_version === 1;
  if (!common) return false;
  const stake = staking as Record<string, unknown>;
  if (value.schema_version === 1) return exactKeys(stake, ["schema_version", "capability", "per_number_stake"]) && stake.capability === "flat-per-number/v1";
  if (value.schema_version === 2) return exactKeys(stake, ["schema_version", "capability"]) && stake.capability === "q80-first-prize-cycling/v1";
  if (value.schema_version === 3) return exactKeys(stake, ["schema_version", "capability"]) && stake.capability === "profile-audaz/v1";
  return exactKeys(stake, ["schema_version", "target_margin", "rounds", "end_mode"]) &&
    Number.isSafeInteger(stake.target_margin) && (stake.target_margin as number) >= 1 && (stake.target_margin as number) <= 1_000_000_000_000 &&
    Number.isSafeInteger(stake.rounds) && (stake.rounds as number) >= 1 && (stake.rounds as number) <= 10_000 && ["cycle", "stop"].includes(stake.end_mode as string);
}
function policyFor(request: SavedRequest): ProfilePolicy {
  if (request.schema_version === 2) return "cycling";
  if (request.schema_version === 3) return "audaz";
  if (request.schema_version === 4) return "recovery";
  return "fixed";
}
const safeInt = (value: unknown, minimum: number, maximum: number): value is number =>
  Number.isSafeInteger(value) && (value as number) >= minimum && (value as number) <= maximum;

/** Validate the original wire version directly; never manufacture v1 staking or capabilities. */
function validateSavedRequest(request: unknown, profile: ProfileListing, dataset: DatasetListing): asserts request is SavedRequest {
  if (!version(request)) throw new Error("La versión de la solicitud guardada no es compatible (se admiten v1–v4).");
  if (!matchingDataset(profile, dataset) || request.profile_id !== profile.profile.profile_id ||
      request.profile_revision !== profile.profile.revision || request.profile_sha256 !== profile.profile_sha256 ||
      request.dataset_sha256 !== dataset.dataset_sha256) throw new Error("La solicitud guardada no coincide con el perfil y los datos inmutables.");
  const fail = () => { throw new Error("La solicitud guardada no es compatible con las reglas nativas de su versión."); };
  const c = request.conditions;
  const s = request.selector;
  const startMinute = typeof c.start_draw === "string" ? Date.parse(`${c.start_draw.replace(" ", "T")}:00Z`) / 60_000 : NaN;
  if (typeof c.start_draw !== "string" || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(c.start_draw) || !Number.isFinite(startMinute) ||
      new Date(startMinute * 60_000).toISOString().slice(0, 16).replace("T", " ") !== c.start_draw ||
      !safeInt(c.capital, 1, 1e12) || !safeInt(c.goal, 2, 1e12) || c.goal <= c.capital ||
      !profile.profile_execution.settlements.includes(c.settlement) ||
      ![c.max_elapsed_draws, c.max_bet_draws].every((bound) => bound === null || safeInt(bound, 1, 10_000)) ||
      c.end_minute !== null && (!safeInt(c.end_minute, 1, 1e9) || c.end_minute <= startMinute) ||
      c.duration_minutes !== null && !safeInt(c.duration_minutes, 1, 1e9) ||
      !safeInt(s.coverage, 1, Math.min(1000, profile.profile.max_coverage, profile.profile.universe_size))) fail();
  if (s.capability === "static-numbers/v1") {
    if (!Array.isArray(s.numbers) || s.numbers.length !== s.coverage ||
        s.numbers.some((n) => !safeInt(n, 0, profile.profile.universe_size - 1)) || new Set(s.numbers).size !== s.numbers.length ||
        s.seed !== null || s.algorithm_version !== null) fail();
  } else if (s.capability === "seeded-random/hash-sha256-v1") {
    if (s.numbers !== null || !safeInt(s.seed, 0, Number.MAX_SAFE_INTEGER) || s.algorithm_version !== "hash-sha256-v1") fail();
  } else fail();
  if (request.schema_version === 1 && (!safeInt(request.staking.per_number_stake, profile.profile.minimum_stake, profile.profile.maximum_stake) ||
      request.staking.per_number_stake % profile.profile.stake_increment)) fail();
  // Parse only real native controls from this version. Dynamic policies have no fixed stake.
  validateProfileStrategy(hydrate(request, profile), profile, policyFor(request));
}
function hydrate(request: SavedRequest, profile: ProfileListing): ProfileDraft {
  const c = request.conditions;
  const s = request.selector;
  return { ...initialProfileDraft, name: request.name, start_draw: c.start_draw,
    capital: formatMoney(c.capital, profile.profile.scale), goal: formatMoney(c.goal, profile.profile.scale),
    max_elapsed_draws: c.max_elapsed_draws === null ? "" : String(c.max_elapsed_draws),
    max_bet_draws: c.max_bet_draws === null ? "" : String(c.max_bet_draws), settlement: c.settlement,
    selector: s.capability === "static-numbers/v1" ? "static" : "random", numbers: s.numbers?.join(", ") ?? "",
    coverage: String(s.coverage), seed: s.seed === null ? "" : String(s.seed),
    per_number_stake: request.schema_version === 1 ? formatMoney(request.staking.per_number_stake, profile.profile.scale) : "",
    target_margin: request.schema_version === 4 ? formatMoney(request.staking.target_margin, profile.profile.scale) : "",
    rounds: request.schema_version === 4 ? String(request.staking.rounds) : "",
    end_mode: request.schema_version === 4 ? request.staking.end_mode : "" };
}
export function draftFromSavedProfileRequest(request: unknown, profile: ProfileListing, dataset: DatasetListing): ProfileDraft {
  validateSavedRequest(request, profile, dataset);
  return request.schema_version === 1 ? draftFromProfileRequest(request, profile, dataset) : hydrate(request, profile);
}
export function buildSavedProfileRepeatRequest(draft: ProfileDraft, original: unknown, profile: ProfileListing,
  dataset: DatasetListing, verifiedDraw: string): SavedRequest {
  validateSavedRequest(original, profile, dataset);
  if (original.schema_version === 1) return buildProfileRepeatRequest(draft, original, profile, dataset, verifiedDraw);
  const initial = hydrate(original, profile);
  const changed = (key: keyof ProfileDraft) => draft[key] !== initial[key];
  const strategy = validateProfileStrategy(draft, profile, policyFor(original));
  const capital = validateProfileCapital(draft, profile, true);
  const result = structuredClone(original);
  if (changed("name")) result.name = capital.name;
  if (changed("start_draw")) {
    if (draft.start_draw !== verifiedDraw) throw new Error("Sorteo inicial: elegí un sorteo verificado de estos datos.");
    result.conditions.start_draw = verifiedDraw;
  }
  if (changed("capital")) result.conditions.capital = capital.capital;
  if (changed("goal")) result.conditions.goal = capital.goal;
  if (changed("max_elapsed_draws")) result.conditions.max_elapsed_draws = capital.max_elapsed_draws;
  if (changed("max_bet_draws")) result.conditions.max_bet_draws = capital.max_bet_draws;
  if (changed("settlement")) {
    if (!profile.profile_execution.settlements.includes(draft.settlement as "all" | "best")) throw new Error("La liquidación no está disponible.");
    result.conditions.settlement = draft.settlement as "all" | "best";
  }
  if (["selector", "coverage", "numbers", "seed"].some((key) => changed(key as keyof ProfileDraft))) result.selector = strategy.selector;
  if (result.schema_version === 4) {
    if (changed("target_margin")) result.staking.target_margin = strategy.targetMargin!;
    if (changed("rounds")) result.staking.rounds = strategy.rounds!;
    if (changed("end_mode")) result.staking.end_mode = draft.end_mode as "cycle" | "stop";
  }
  // Absolute/duration bounds, identity, policy and version stay on the original wire.
  validateSavedRequest(result, profile, dataset);
  return result;
}
