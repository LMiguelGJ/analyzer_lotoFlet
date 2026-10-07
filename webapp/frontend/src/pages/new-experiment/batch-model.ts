import { moneyUnits, wholeNumber } from "../../lib/profile-input";

export const BATCH_DRAFT_VERSION = 1 as const;
export const BATCH_DRAFT_STORAGE_KEY = "profile-batch-draft-v1";

export type Settlement = "all" | "best";
export interface StrategyReference { id: string; revision: number; definition_sha256: string }
export interface ClosedStrategyDefinition {
  definition_version: 1;
  name: string;
  selector: "static-numbers/v1" | "seeded-random/hash-sha256-v1" | "archived-cold/v1" | "archived-transition/v1" | "archived-topk/v1" | "archived-parity50/v1";
  coverage: number;
  staking: "flat-per-number/v1" | "q80-first-prize-cycling/v1" | "profile-audaz/v1" | "profile-recovery-ladder/v1" | "q80-reference-audaz/v1";
  selector_parameters: { numbers?: number[]; seed?: number; system?: string };
  staking_parameters: { per_number_stake?: number; target_margin?: number; rounds?: number; end_mode?: "cycle" | "stop" };
  closing_defaults: { settlement?: Settlement; max_elapsed_draws?: number | null; max_bet_draws?: number | null; end_minute?: number | null; duration_minutes?: number | null };
}
export interface BatchDraft {
  version: typeof BATCH_DRAFT_VERSION;
  step: number;
  datasetSha256: string;
  selectedDraw: { datasetSha256: string; index: number; draw: string } | null;
  profile: { id: string; revision: number; sha256: string } | null;
  strategyRefs: StrategyReference[];
  conditions: { start_draw: string; capital: string; goal: string; settlement: Settlement | ""; max_elapsed_draws: string; max_bet_draws: string; max_draws: string };
  pending: { clientRequestId: string; frozenBody: BatchSubmissionBody } | null;
  savedTimeBounds?: { start_draw: string; end_minute: number | null; duration_minutes: number | null };
}
export interface BatchSubmissionBody {
  schema_version: 1;
  profile: { id: string; revision: number; sha256: string };
  dataset_sha256: string;
  strategies: StrategyReference[];
  conditions: { schema_version: 1; start_draw: string; capital: number; goal: number; settlement: Settlement; max_elapsed_draws: number | null; max_bet_draws: number | null; end_minute: number | null; duration_minutes: number | null };
  max_draws: number;
  client_request_id: string;
}

export function createBatchDraft(datasetSha256: string): BatchDraft {
  return { version: BATCH_DRAFT_VERSION, step: 0, datasetSha256, selectedDraw: null, profile: null, strategyRefs: [],
    conditions: { start_draw: "", capital: "", goal: "", settlement: "", max_elapsed_draws: "", max_bet_draws: "", max_draws: "" }, pending: null };
}

function canonicalDrawMinute(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const parts = match.slice(1).map(Number);
  const date = new Date(0);
  date.setUTCFullYear(parts[0], parts[1] - 1, parts[2]);
  date.setUTCHours(parts[3], parts[4], 0, 0);
  if (date.getUTCFullYear() !== parts[0] || date.getUTCMonth() !== parts[1] - 1 || date.getUTCDate() !== parts[2] ||
    date.getUTCHours() !== parts[3] || date.getUTCMinutes() !== parts[4]) return null;
  return date.getTime() / 60_000;
}

export function serializeBatchDraft(draft: BatchDraft): string {
  return JSON.stringify({ version: BATCH_DRAFT_VERSION, step: draft.step, datasetSha256: draft.datasetSha256, selectedDraw: draft.selectedDraw,
    profile: draft.profile, strategyRefs: draft.strategyRefs, conditions: draft.conditions, pending: draft.pending,
    ...(draft.savedTimeBounds ? { savedTimeBounds: draft.savedTimeBounds } : {}) });
}

function exactKeys(value: unknown, keys: string[]): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const actual = Object.keys(value);
  return actual.length === keys.length && keys.every((key) => Object.hasOwn(value, key));
}
function validIdentity(value: unknown): value is { id: string; revision: number; sha256: string } {
  return exactKeys(value, ["id", "revision", "sha256"]) && typeof value.id === "string" && Number.isInteger(value.revision) &&
    Number(value.revision) >= 1 && typeof value.sha256 === "string" && /^[0-9a-f]{64}$/.test(value.sha256);
}
function validReference(value: unknown): value is StrategyReference {
  return exactKeys(value, ["id", "revision", "definition_sha256"]) && typeof value.id === "string" && value.id.length > 0 &&
    Number.isInteger(value.revision) && Number(value.revision) >= 1 && typeof value.definition_sha256 === "string" && /^[0-9a-f]{64}$/.test(value.definition_sha256);
}
function validSubmission(value: unknown, clientRequestId: string): value is BatchSubmissionBody {
  if (!exactKeys(value, ["schema_version", "profile", "dataset_sha256", "strategies", "conditions", "max_draws", "client_request_id"]) ||
    value.schema_version !== 1 || !validIdentity(value.profile) || typeof value.dataset_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(value.dataset_sha256) ||
    typeof value.client_request_id !== "string" || value.client_request_id !== clientRequestId || value.client_request_id.length > 128 ||
    !Number.isInteger(value.max_draws) || Number(value.max_draws) < 1 || Number(value.max_draws) > 10_000 || !Array.isArray(value.strategies) ||
    value.strategies.length < 1 || value.strategies.length > 3 || !value.strategies.every(validReference) ||
    !exactKeys(value.conditions, ["schema_version", "start_draw", "capital", "goal", "settlement", "max_elapsed_draws", "max_bet_draws", "end_minute", "duration_minutes"])) return false;
  const conditions = value.conditions;
  if (typeof conditions.start_draw !== "string") return false;
  const startMinute = canonicalDrawMinute(conditions.start_draw);
  return conditions.schema_version === 1 && startMinute !== null && Number.isSafeInteger(conditions.capital) && Number(conditions.capital) > 0 &&
    Number.isSafeInteger(conditions.goal) && Number(conditions.goal) >= 2 && (conditions.settlement === "all" || conditions.settlement === "best") &&
    (conditions.max_elapsed_draws === null || Number.isInteger(conditions.max_elapsed_draws)) &&
    (conditions.max_bet_draws === null || Number.isInteger(conditions.max_bet_draws)) &&
    (conditions.end_minute === null || Number.isSafeInteger(conditions.end_minute) && Number(conditions.end_minute) >= 1 &&
      Number(conditions.end_minute) <= 1_000_000_000 && Number(conditions.end_minute) > startMinute) &&
    (conditions.duration_minutes === null || Number.isSafeInteger(conditions.duration_minutes) && Number(conditions.duration_minutes) >= 1 &&
      Number(conditions.duration_minutes) <= 1_000_000_000);
}

export function parseBatchDraft(raw: string | null): BatchDraft | null {
  if (!raw || raw.length > 32_000) return null;
  try {
    const value: unknown = JSON.parse(raw);
    const currentKeys = ["version", "step", "datasetSha256", "selectedDraw", "profile", "strategyRefs", "conditions", "pending"];
    const previousKeys = ["version", "step", "datasetSha256", "profile", "strategyRefs", "conditions", "pending"];
    const hasCurrentKeys = exactKeys(value, currentKeys);
    const hasPreviousKeys = exactKeys(value, previousKeys);
    const hasCurrentKeysWithBounds = exactKeys(value, [...currentKeys, "savedTimeBounds"]);
    const hasPreviousKeysWithBounds = exactKeys(value, [...previousKeys, "savedTimeBounds"]);
    if (!hasCurrentKeys && !hasPreviousKeys && !hasCurrentKeysWithBounds && !hasPreviousKeysWithBounds) return null;
    let savedTimeBounds: BatchDraft["savedTimeBounds"];
    if (Object.hasOwn(value, "savedTimeBounds")) {
      const bounds = value.savedTimeBounds;
      if (!exactKeys(bounds, ["start_draw", "end_minute", "duration_minutes"]) || typeof bounds.start_draw !== "string") return null;
      const originalStartMinute = canonicalDrawMinute(bounds.start_draw);
      if (originalStartMinute === null || (bounds.end_minute !== null && (!Number.isSafeInteger(bounds.end_minute) || Number(bounds.end_minute) < 1 ||
        Number(bounds.end_minute) > 1_000_000_000 || Number(bounds.end_minute) <= originalStartMinute)) ||
        (bounds.duration_minutes !== null && (!Number.isSafeInteger(bounds.duration_minutes) || Number(bounds.duration_minutes) < 1 || Number(bounds.duration_minutes) > 1_000_000_000))) return null;
      savedTimeBounds = bounds as BatchDraft["savedTimeBounds"];
    }
    if (value.version !== BATCH_DRAFT_VERSION || typeof value.datasetSha256 !== "string" || !/^[0-9a-f]{64}$/.test(value.datasetSha256) ||
      !Number.isInteger(value.step) || Number(value.step) < 0 || Number(value.step) > 4 || !Array.isArray(value.strategyRefs) || value.strategyRefs.length > 3 ||
      !value.strategyRefs.every(validReference) || (value.profile !== null && !validIdentity(value.profile)) ||
      !exactKeys(value.conditions, ["start_draw", "capital", "goal", "settlement", "max_elapsed_draws", "max_bet_draws", "max_draws"])) return null;
    const selectedDrawValue = Object.hasOwn(value, "selectedDraw") ? value.selectedDraw : null;
    if (selectedDrawValue !== null && (!exactKeys(selectedDrawValue, ["datasetSha256", "index", "draw"]) ||
      selectedDrawValue.datasetSha256 !== value.datasetSha256 || !Number.isSafeInteger(selectedDrawValue.index) || Number(selectedDrawValue.index) < 0 ||
      typeof selectedDrawValue.draw !== "string" || !/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$/.test(selectedDrawValue.draw))) return null;
    const c = value.conditions;
    if (typeof c.start_draw !== "string" || typeof c.capital !== "string" || typeof c.goal !== "string" ||
      !["", "all", "best"].includes(String(c.settlement)) || typeof c.max_elapsed_draws !== "string" || typeof c.max_bet_draws !== "string" || typeof c.max_draws !== "string" ||
      (selectedDrawValue !== null && c.start_draw !== selectedDrawValue.draw)) return null;
    let pending: BatchDraft["pending"] = null;
    if (value.pending !== null) {
      if (!exactKeys(value.pending, ["clientRequestId", "frozenBody"]) || typeof value.pending.clientRequestId !== "string" || value.pending.clientRequestId.length < 1 || value.pending.clientRequestId.length > 128 ||
        !validSubmission(value.pending.frozenBody, value.pending.clientRequestId)) return null;
      pending = { clientRequestId: value.pending.clientRequestId, frozenBody: value.pending.frozenBody };
    }
    return { version: BATCH_DRAFT_VERSION, step: Number(value.step), datasetSha256: value.datasetSha256,
      selectedDraw: selectedDrawValue as BatchDraft["selectedDraw"], profile: value.profile as BatchDraft["profile"],
      strategyRefs: value.strategyRefs, conditions: c as BatchDraft["conditions"], pending, ...(savedTimeBounds ? { savedTimeBounds } : {}) };
  } catch { return null; }
}

export function buildBatchBody(draft: BatchDraft, profileScale: number, clientRequestId: string): BatchSubmissionBody {
  if (!draft.profile || !draft.strategyRefs.length || draft.strategyRefs.length > 3) throw new Error("Elegí perfil y entre una y tres estrategias guardadas.");
  const c = draft.conditions;
  const start = c.start_draw.trim();
  const startMinute = canonicalDrawMinute(start);
  if (startMinute === null) throw new Error("Elegí un sorteo de inicio verificado.");
  const capital = moneyUnits(c.capital, profileScale, "Capital inicial");
  const goal = moneyUnits(c.goal, profileScale, "Meta de saldo final");
  if (goal <= capital) throw new Error("La meta debe superar el capital inicial.");
  if (c.settlement !== "all" && c.settlement !== "best") throw new Error("Elegí una liquidación compartida.");
  const elapsed = draft.savedTimeBounds
    ? c.max_elapsed_draws.trim() ? wholeNumber(c.max_elapsed_draws, "Sorteos transcurridos", 1n, 10_000n) : null
    : wholeNumber(c.max_elapsed_draws, "Sorteos transcurridos", 1n, 10_000n);
  const bet = c.max_bet_draws ? wholeNumber(c.max_bet_draws, "Sorteos apostados", 1n, 10_000n) : null;
  const maxDraws = wholeNumber(c.max_draws, "Presupuesto de sorteos", 1n, 10_000n);
  if (draft.savedTimeBounds) {
    const originalStart = canonicalDrawMinute(draft.savedTimeBounds.start_draw);
    const endMinute = draft.savedTimeBounds.end_minute;
    const durationMinutes = draft.savedTimeBounds.duration_minutes;
    if (originalStart === null || (endMinute !== null && (!Number.isSafeInteger(endMinute) || endMinute < 1 || endMinute > 1_000_000_000 || endMinute <= originalStart)) ||
      (durationMinutes !== null && (!Number.isSafeInteger(durationMinutes) || durationMinutes < 1 || durationMinutes > 1_000_000_000))) {
      throw new Error("Los límites de hora guardados no son válidos.");
    }
    if (endMinute !== null && endMinute <= startMinute) throw new Error("El límite de hora absoluta debe ser posterior al nuevo sorteo inicial.");
  }
  return { schema_version: 1, profile: draft.profile, dataset_sha256: draft.datasetSha256,
    strategies: draft.strategyRefs.map((reference) => ({ ...reference })),
    conditions: { schema_version: 1, start_draw: start, capital, goal, settlement: c.settlement,
      max_elapsed_draws: elapsed === null ? null : Number(elapsed), max_bet_draws: bet === null ? null : Number(bet),
      end_minute: draft.savedTimeBounds?.end_minute ?? null, duration_minutes: draft.savedTimeBounds?.duration_minutes ?? null },
    max_draws: Number(maxDraws), client_request_id: clientRequestId };
}
