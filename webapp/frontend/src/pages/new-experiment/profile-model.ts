import type { DatasetListing, ProfileAudazRequest, ProfileCyclingRequest, ProfileExperimentRequest, ProfileListing, ProfileRecoveryRequest, SettlementMode } from "../../api/types";
import { moneyUnits, wholeNumber } from "../../lib/profile-input";

export interface ProfileDraft {
  name: string; start_draw: string; capital: string; goal: string;
  max_elapsed_draws: string; max_bet_draws: string;
  settlement: SettlementMode | ""; selector: "static" | "random";
  numbers: string; coverage: string; seed: string; per_number_stake: string;
  target_margin: string; rounds: string; end_mode: "cycle" | "stop" | "";
}

export const initialProfileDraft: ProfileDraft = {
  name: "", start_draw: "", capital: "", goal: "", max_elapsed_draws: "",
  max_bet_draws: "", settlement: "", selector: "static", numbers: "",
  coverage: "", seed: "", per_number_stake: "", target_margin: "", rounds: "", end_mode: "",
};

export function matchingDataset(profile: ProfileListing, dataset: DatasetListing): boolean {
  return profile.profile_execution.ready && dataset.profile_execution.ready &&
    dataset.profile_id === profile.profile.profile_id &&
    dataset.profile_revision === profile.profile.revision &&
    dataset.profile_sha256 === profile.profile_sha256;
}

export type ProfilePolicy = "fixed" | "cycling" | "audaz" | "recovery";

type V1Request = ProfileExperimentRequest;
type JsonObject = Record<string, unknown>;
const hasKeys = (value: unknown, keys: string[]): value is JsonObject => Boolean(value && typeof value === "object" &&
  !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every((key) => key in value));
const safeInt = (value: unknown, min: number, max: number): value is number => Number.isSafeInteger(value) && (value as number) >= min && (value as number) <= max;
function formatUnits(value: number, scale: number): string {
  const digits = 10 ** scale;
  return scale ? `${Math.floor(value / digits)}.${String(value % digits).padStart(scale, "0")}` : String(value);
}
function validSavedRequest(value: unknown, profile: ProfileListing, dataset: DatasetListing): asserts value is V1Request {
  const fail = () => { throw new Error("La solicitud guardada no es compatible con este perfil y conjunto de datos."); };
  if (!hasKeys(value, ["kind", "schema_version", "name", "dataset_sha256", "profile_id", "profile_revision", "profile_sha256", "entry_policy", "conditions", "selector", "staking"]) ||
      value.kind !== "profile" || value.schema_version !== 1 || typeof value.name !== "string" || !value.name.trim() || value.name.length > 80 ||
      value.profile_id !== profile.profile.profile_id || value.profile_revision !== profile.profile.revision || value.profile_sha256 !== profile.profile_sha256 ||
      value.dataset_sha256 !== dataset.dataset_sha256 || !matchingDataset(profile, dataset) || !/^[0-9a-f]{64}$/.test(value.profile_sha256 as string) ||
      !/^[0-9a-f]{64}$/.test(value.dataset_sha256 as string) || value.entry_policy !== "all_rows/v1" ||
      !profile.profile_execution.entry_policies.includes("all_rows/v1")) fail();
  const saved = value as JsonObject;
  const c = saved.conditions as JsonObject;
  const s = saved.selector as JsonObject;
  const t = saved.staking as JsonObject;
  if (!hasKeys(c, ["schema_version", "start_draw", "capital", "goal", "settlement", "max_elapsed_draws", "max_bet_draws", "end_minute", "duration_minutes"]) ||
      c.schema_version !== 1 || typeof c.start_draw !== "string" || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(c.start_draw) ||
      !Number.isFinite(Date.parse(`${c.start_draw.replace(" ", "T")}:00Z`)) || new Date(Date.parse(`${c.start_draw.replace(" ", "T")}:00Z`)).toISOString().slice(0, 16).replace("T", " ") !== c.start_draw || !safeInt(c.capital, 1, 1e12) || !safeInt(c.goal, 2, 1e12) || c.goal <= c.capital ||
      !profile.profile_execution.settlements.includes(c.settlement as SettlementMode) ||
      ![c.max_elapsed_draws, c.max_bet_draws].every((n) => n === null || safeInt(n, 1, 10_000)) ||
      (c.end_minute !== null && (!safeInt(c.end_minute, 1, 1e9) || c.end_minute <= Date.parse(`${c.start_draw.replace(" ", "T")}:00Z`) / 60_000)) || (c.duration_minutes !== null && !safeInt(c.duration_minutes, 1, 1e9)) ||
      !hasKeys(s, ["schema_version", "capability", "coverage", "numbers", "seed", "algorithm_version"]) || s.schema_version !== 1 ||
      !safeInt(s.coverage, 1, Math.min(1000, profile.profile.max_coverage, profile.profile.universe_size)) ||
      !hasKeys(t, ["schema_version", "capability", "per_number_stake"]) || t.schema_version !== 1 || t.capability !== "flat-per-number/v1" ||
      !profile.profile_execution.staking_capabilities.includes("flat-per-number/v1") ||
      !safeInt(t.per_number_stake, profile.profile.minimum_stake, profile.profile.maximum_stake) || t.per_number_stake % profile.profile.stake_increment) fail();
  if (s.capability === "static-numbers/v1") {
    if (!profile.profile_execution.selector_capabilities.includes(s.capability) || !Array.isArray(s.numbers) || s.numbers.length !== s.coverage ||
        s.numbers.some((n: unknown) => !safeInt(n, 0, profile.profile.universe_size - 1)) || new Set(s.numbers).size !== s.numbers.length || s.seed !== null || s.algorithm_version !== null) fail();
  } else if (s.capability === "seeded-random/hash-sha256-v1") {
    if (!profile.profile_execution.selector_capabilities.includes(s.capability) || s.numbers !== null || !safeInt(s.seed, 0, Number.MAX_SAFE_INTEGER) || s.algorithm_version !== "hash-sha256-v1") fail();
  } else fail();
}

/** Hydrate only a validated saved schema-v1 wire request; returned draft is detached. */
export function draftFromProfileRequest(request: unknown, profile: ProfileListing, dataset: DatasetListing): ProfileDraft {
  validSavedRequest(request, profile, dataset);
  const c = request.conditions;
  const s = request.selector;
  return { ...initialProfileDraft, name: request.name, start_draw: c.start_draw, capital: formatUnits(c.capital, profile.profile.scale),
    goal: formatUnits(c.goal, profile.profile.scale), max_elapsed_draws: c.max_elapsed_draws === null ? "" : String(c.max_elapsed_draws),
    max_bet_draws: c.max_bet_draws === null ? "" : String(c.max_bet_draws), settlement: c.settlement,
    selector: s.capability === "static-numbers/v1" ? "static" : "random", numbers: s.numbers?.join(", ") ?? "",
    coverage: String(s.coverage), seed: s.seed === null ? "" : String(s.seed), per_number_stake: formatUnits(request.staking.per_number_stake, profile.profile.scale),
    target_margin: "", rounds: "", end_mode: "" };
}

/** Copy the v1 wire template and overlay only changed, editable draft controls. */
export function buildProfileRepeatRequest(draft: ProfileDraft, original: unknown, profile: ProfileListing,
  dataset: DatasetListing, verifiedDraw: string): V1Request {
  validSavedRequest(original, profile, dataset);
  const result = structuredClone(original);
  const initial = draftFromProfileRequest(original, profile, dataset);
  const c = result.conditions;
  const s = result.selector;
  const changed = (key: keyof ProfileDraft) => draft[key] !== initial[key];
  if (changed("name")) { if (typeof draft.name !== "string") throw new Error("Nombre inválido."); const name = draft.name.trim(); if (!name || name.length > 80) throw new Error("Nombre: ingresá entre 1 y 80 caracteres."); result.name = name; }
  if (changed("start_draw")) {
    if (draft.start_draw !== verifiedDraw || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(verifiedDraw)) throw new Error("Sorteo inicial: elegí un sorteo verificado de estos datos.");
    c.start_draw = verifiedDraw;
  }
  if (changed("capital")) c.capital = moneyUnits(draft.capital, profile.profile.scale, "Capital inicial");
  if (changed("goal")) c.goal = moneyUnits(draft.goal, profile.profile.scale, "Meta de saldo final");
  if (c.goal <= c.capital) throw new Error("La meta de saldo final debe superar al capital inicial.");
  if (changed("settlement")) { if (!profile.profile_execution.settlements.includes(draft.settlement as SettlementMode)) throw new Error("La liquidación no está disponible."); c.settlement = draft.settlement as SettlementMode; }
  if (changed("max_elapsed_draws")) c.max_elapsed_draws = draft.max_elapsed_draws ? wholeNumber(draft.max_elapsed_draws, "Sorteos transcurridos", 1n, 10_000n) : null;
  if (changed("max_bet_draws")) c.max_bet_draws = draft.max_bet_draws ? wholeNumber(draft.max_bet_draws, "Sorteos apostados", 1n, 10_000n) : null;
  const selectorChanged = changed("selector") || changed("coverage") || changed("numbers") || changed("seed");
  if (selectorChanged) {
    if (draft.selector !== "static" && draft.selector !== "random") throw new Error("Elegí una selección disponible.");
    const coverage = changed("coverage") ? wholeNumber(draft.coverage, "Cobertura", 1n, BigInt(Math.min(1000, profile.profile.max_coverage, profile.profile.universe_size))) : s.coverage;
    if (draft.selector === "static") {
      if (!profile.profile_execution.selector_capabilities.includes("static-numbers/v1")) throw new Error("La selección fija no está disponible.");
      if (typeof draft.numbers !== "string") throw new Error("Números inválidos.");
      const parts = draft.numbers.split(",").map((part) => part.trim());
      const numbers = parts.map((part) => { if (!/^(0|[1-9]\d*)$/.test(part)) throw new Error("Números inválidos."); return Number(part); });
      if (numbers.length !== coverage || numbers.some((n) => !Number.isSafeInteger(n) || n >= profile.profile.universe_size) || new Set(numbers).size !== numbers.length) throw new Error("Números inválidos para la cobertura.");
      Object.assign(s, { capability: "static-numbers/v1", coverage, numbers, seed: null, algorithm_version: null });
    } else {
      if (!profile.profile_execution.selector_capabilities.includes("seeded-random/hash-sha256-v1")) throw new Error("El azar reproducible no está disponible.");
      const seed = changed("seed") ? wholeNumber(draft.seed, "Semilla", 0n, BigInt(Number.MAX_SAFE_INTEGER)) : s.seed;
      Object.assign(s, { capability: "seeded-random/hash-sha256-v1", coverage, numbers: null, seed, algorithm_version: "hash-sha256-v1" });
    }
  }
  if (changed("per_number_stake")) {
    const stake = moneyUnits(draft.per_number_stake, profile.profile.scale, "Apuesta por número");
    if (stake < profile.profile.minimum_stake || stake > profile.profile.maximum_stake || stake % profile.profile.stake_increment) throw new Error("La apuesta por número debe respetar el perfil.");
    result.staking.per_number_stake = stake;
  }
  validSavedRequest(result, profile, dataset);
  return result;
}

export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy: "fixed"): ProfileExperimentRequest;
export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy: "cycling"): ProfileCyclingRequest;
export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy: "audaz"): ProfileAudazRequest;
export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy: "recovery"): ProfileRecoveryRequest;
export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy?: ProfilePolicy): ProfileExperimentRequest | ProfileCyclingRequest | ProfileAudazRequest | ProfileRecoveryRequest;
export function buildProfileRequest(draft: ProfileDraft, profile: ProfileListing, dataset: DatasetListing,
  verifiedDraw: string, policy: ProfilePolicy = "fixed"): ProfileExperimentRequest | ProfileCyclingRequest | ProfileAudazRequest | ProfileRecoveryRequest {
  if (!matchingDataset(profile, dataset) || !/^[0-9a-f]{64}$/.test(dataset.dataset_sha256) ||
      !/^[0-9a-f]{64}$/.test(profile.profile_sha256)) throw new Error("El perfil y los datos no coinciden o ya no están disponibles.");
  const supported = profile.profile_execution;
  const capability = policy === "cycling" ? "q80-first-prize-cycling/v1" : policy === "audaz" ? "profile-audaz/v1" : policy === "recovery" ? "profile-recovery-ladder/v1" : "flat-per-number/v1";
  if (!supported.entry_policies.includes("all_rows/v1") || !supported.staking_capabilities.includes(capability) ||
      !supported.settlements.includes(draft.settlement as SettlementMode)) throw new Error("La capacidad elegida no está disponible en el servidor.");
  const name = draft.name.trim();
  if (!name || name.length > 80) throw new Error("Nombre: ingresá entre 1 y 80 caracteres.");
  if (draft.start_draw !== verifiedDraw || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(verifiedDraw)) {
    throw new Error("Sorteo inicial: elegí un sorteo verificado de estos datos.");
  }
  const capital = moneyUnits(draft.capital, profile.profile.scale, "Capital inicial");
  const goal = moneyUnits(draft.goal, profile.profile.scale, "Meta de saldo final");
  if (goal <= capital) throw new Error("La meta de saldo final debe superar al capital inicial.");
  // An explicit elapsed bound prevents an unbounded first session from this creator.
  const max_elapsed_draws = wholeNumber(draft.max_elapsed_draws, "Sorteos transcurridos", 1n, 10_000n);
  const max_bet_draws = draft.max_bet_draws ? wholeNumber(draft.max_bet_draws, "Sorteos apostados", 1n, 10_000n) : null;
  const coverage = wholeNumber(draft.coverage, "Cobertura", 1n,
    BigInt(Math.min(1_000, profile.profile.max_coverage, profile.profile.universe_size)));
  const audazCompatibility = supported.audaz_compatibility;
  const recoveryCompatibility = supported.recovery_compatibility;
  if (policy === "audaz" && (!supported.staking_capabilities.includes("profile-audaz/v1") ||
      !audazCompatibility?.available || coverage > audazCompatibility.maximum_compatible_coverage)) {
    const maximum = audazCompatibility?.maximum_compatible_coverage ?? 0;
    throw new Error(`Audaz no está disponible para esta cobertura; el servidor admite hasta ${maximum}.`);
  }
  if (policy === "recovery" && (!recoveryCompatibility?.available || coverage > recoveryCompatibility.maximum_compatible_coverage)) {
    const maximum = recoveryCompatibility?.maximum_compatible_coverage ?? 0;
    throw new Error(`La escalera de recuperación no está disponible para esta cobertura; el servidor admite hasta ${maximum}.`);
  }
  let stake: number | undefined;
  let targetMargin: number | undefined;
  let rounds: number | undefined;
  if (policy === "fixed") {
    stake = moneyUnits(draft.per_number_stake, profile.profile.scale, "Apuesta por número");
    if (stake < profile.profile.minimum_stake || stake > profile.profile.maximum_stake || stake % profile.profile.stake_increment) {
      throw new Error("La apuesta por número debe respetar el mínimo, máximo e incremento del perfil.");
    }
  } else if (policy === "cycling" && coverage >= 80) {
    throw new Error("La cobertura Q80 debe estar entre 1 y 79 números.");
  } else if (policy === "recovery") {
    targetMargin = moneyUnits(draft.target_margin, profile.profile.scale, "Margen objetivo");
    rounds = Number(wholeNumber(draft.rounds, "Rondas de recuperación", 1n, 10_000n));
    if (draft.end_mode !== "cycle" && draft.end_mode !== "stop") throw new Error("Elegí qué hacer al completar la escalera.");
  }
  let selector: ProfileExperimentRequest["selector"];
  if (draft.selector === "static") {
    if (!supported.selector_capabilities.includes("static-numbers/v1")) throw new Error("La selección fija no está disponible.");
    const parts = draft.numbers.split(",").map((part) => part.trim());
    if (parts.length !== coverage || parts.some((part) => !/^(0|[1-9]\d*)$/.test(part))) {
      throw new Error("Números: ingresá exactamente la cobertura indicada, separados por comas.");
    }
    const numbers = parts.map(Number);
    if (numbers.some((number) => !Number.isSafeInteger(number) || number >= profile.profile.universe_size) ||
        new Set(numbers).size !== numbers.length) throw new Error("Números: usá valores distintos dentro del universo del perfil.");
    selector = { schema_version: 1, capability: "static-numbers/v1", coverage, numbers, seed: null, algorithm_version: null };
  } else {
    if (!supported.selector_capabilities.includes("seeded-random/hash-sha256-v1")) throw new Error("El azar reproducible no está disponible.");
    const seed = wholeNumber(draft.seed, "Semilla", 0n, BigInt(Number.MAX_SAFE_INTEGER));
    selector = { schema_version: 1, capability: "seeded-random/hash-sha256-v1", coverage, numbers: null,
      seed, algorithm_version: "hash-sha256-v1" };
  }
  const common = { kind: "profile" as const, name, dataset_sha256: dataset.dataset_sha256,
    profile_id: profile.profile.profile_id, profile_revision: profile.profile.revision,
    profile_sha256: profile.profile_sha256, entry_policy: "all_rows/v1",
    conditions: { schema_version: 1, start_draw: verifiedDraw, capital, goal,
      settlement: draft.settlement as SettlementMode, max_elapsed_draws, max_bet_draws,
      end_minute: null, duration_minutes: null }, selector };
  if (policy === "cycling") return { ...common, schema_version: 2, staking: { schema_version: 1, capability: "q80-first-prize-cycling/v1" } };
  if (policy === "audaz") return { ...common, schema_version: 3, staking: { schema_version: 1, capability: "profile-audaz/v1" } };
  if (policy === "recovery") return { ...common, schema_version: 4, staking: { schema_version: 1,
    target_margin: targetMargin!, rounds: rounds!, end_mode: draft.end_mode as "cycle" | "stop" } };
  return { ...common, schema_version: 1, staking: { schema_version: 1, capability: "flat-per-number/v1", per_number_stake: stake! } };
}
