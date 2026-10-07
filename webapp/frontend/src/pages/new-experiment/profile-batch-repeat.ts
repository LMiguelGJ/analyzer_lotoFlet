import type { ProfileBatchExperimentSummary } from "../../api/types";
import { createBatchDraft, type BatchDraft } from "./batch-model";

export interface PreparedBatchRepeat {
  draft: BatchDraft;
  strategyTemplates: ProfileBatchExperimentSummary["request"]["strategies"];
}

export function prepareBatchRepeat(saved: ProfileBatchExperimentSummary): PreparedBatchRepeat {
  const request = saved?.request;
  const admission = saved?.batch_admission;
  if (saved?.request_kind !== "profile" || saved.request_schema_version !== 5 || request?.schema_version !== 5 ||
    request.kind !== "profile_batch" || request.source_version !== "canonical-history/v1" || saved.id.length === 0) {
    throw new Error("La simulación guardada no es un lote v5 repetible.");
  }
  const hash = /^[0-9a-f]{64}$/;
  if (!hash.test(request.profile_sha256) || !hash.test(request.dataset_sha256) ||
    saved.profile.profile_id !== request.profile_id || saved.profile.revision !== request.profile_revision ||
    !admission || !Number.isInteger(admission.policy_revision) || admission.policy_revision < 1 ||
    !admission.policy || typeof admission.policy !== "object") {
    throw new Error("Faltan identidades verificables del perfil, los datos o la política guardada.");
  }
  const source = admission.source_identity;
  if (!source || source.dataset_sha256 !== request.dataset_sha256 || !hash.test(source.source_sha256) ||
    !hash.test(source.canonical_sha256) || !Number.isSafeInteger(source.row_count) || source.row_count < 1 ||
    source.profile_id !== request.profile_id || source.profile_revision !== request.profile_revision || source.profile_sha256 !== request.profile_sha256 ||
    typeof source.archive_bound !== "boolean" || (source.archive_bound && (!source.archive_history_sha256 || !Array.isArray(source.archive_rank_row_ids)))) {
    throw new Error("La identidad de origen guardada no coincide o está incompleta.");
  }
  const requested = admission.requested_constraints;
  if (!requested || requested.max_draws !== request.max_draws || requested.max_elapsed_draws !== request.conditions.max_elapsed_draws ||
    requested.max_bet_draws !== request.conditions.max_bet_draws) {
    throw new Error("Los límites solicitados guardados no coinciden; no se usarán límites efectivos.");
  }
  if (!Array.isArray(request.strategies) || request.strategies.length < 1 || request.strategies.length > 3 ||
    !Array.isArray(admission.strategy_refs) || admission.strategy_refs.length !== request.strategies.length ||
    admission.strategy_refs.some((ref, index) => !ref.id || !Number.isInteger(ref.revision) || ref.revision < 1 || !hash.test(ref.definition_sha256) ||
      !request.strategies[index] || request.strategies[index].definition_version !== 1)) {
    throw new Error("Las estrategias guardadas no tienen referencias inmutables verificables.");
  }
  const c = request.conditions;
  const values = [c.capital, c.goal, request.max_draws, c.max_elapsed_draws, c.max_bet_draws].filter((value) => value !== null);
  if (c.schema_version !== 1 || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(c.start_draw) ||
    !Number.isSafeInteger(saved.profile.scale) || saved.profile.scale < 0 || saved.profile.scale > 6 ||
    values.some((value) => !Number.isSafeInteger(value) || value < 1) || (c.settlement !== "all" && c.settlement !== "best") ||
    (c.end_minute !== null && (!Number.isSafeInteger(c.end_minute) || c.end_minute < 1 || c.end_minute > 1_000_000_000)) ||
    (c.duration_minutes !== null && (!Number.isSafeInteger(c.duration_minutes) || c.duration_minutes < 1 || c.duration_minutes > 1_000_000_000))) {
    throw new Error("Las condiciones originales no son compatibles con este creador.");
  }
  const draft = createBatchDraft(request.dataset_sha256);
  draft.profile = { id: request.profile_id, revision: request.profile_revision, sha256: request.profile_sha256 };
  draft.strategyRefs = admission.strategy_refs.map(({ id, revision, definition_sha256 }) => ({ id, revision, definition_sha256 }));
  draft.conditions = { start_draw: c.start_draw, capital: String(c.capital / 10 ** saved.profile.scale), goal: String(c.goal / 10 ** saved.profile.scale),
    settlement: c.settlement, max_elapsed_draws: String(c.max_elapsed_draws ?? ""), max_bet_draws: String(c.max_bet_draws ?? ""), max_draws: String(request.max_draws) };
  draft.savedTimeBounds = { start_draw: c.start_draw, end_minute: c.end_minute, duration_minutes: c.duration_minutes };
  return { draft, strategyTemplates: request.strategies };
}
