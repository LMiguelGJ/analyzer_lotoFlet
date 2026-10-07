import { describe, expect, it } from "vitest";
import { prepareBatchRepeat } from "./profile-batch-repeat";
import type { BatchDraft } from "./batch-model";
import type { ProfileBatchExperimentSummary } from "../../api/types";

const detail = {
  request_kind: "profile", request_schema_version: 5, id: "saved-base", status: "completed", created_at: null,
  request: { schema_version: 5, kind: "profile_batch", profile_id: "p", profile_revision: 2, profile_sha256: "a".repeat(64),
    dataset_sha256: "b".repeat(64), conditions: { schema_version: 1, start_draw: "2025-01-01 08:30", capital: 500,
      goal: 900, settlement: "best", max_elapsed_draws: 12, max_bet_draws: 8, end_minute: null, duration_minutes: null },
    strategies: [{ definition_version: 1, name: "Saved", selector: "static-numbers/v1", coverage: 1, staking: "flat-per-number/v1",
      selector_parameters: { numbers: [4] }, staking_parameters: { per_number_stake: 2 }, closing_defaults: { settlement: "best" } }],
    max_draws: 10, source_version: "canonical-history/v1" },

  profile: { schema_version: 1, profile_id: "p", revision: 2, scale: 0 },
  batch_admission: { strategy_refs: [{ id: "s", revision: 3, definition_sha256: "c".repeat(64) }],
    source_identity: { dataset_sha256: "b".repeat(64), source_sha256: "d".repeat(64), canonical_sha256: "e".repeat(64), row_count: 20,
      profile_id: "p", profile_revision: 2, profile_sha256: "a".repeat(64), archive_bound: false, archive_history_sha256: null, archive_rank_row_ids: null },
    requested_constraints: { max_draws: 10, max_elapsed_draws: 12, max_bet_draws: 8 }, effective_constraints: { max_draws: 3 },
    policy_revision: 4, policy: { max_draws: 3 } },
  runs: [], display: {}, sources: {},
} as unknown as ProfileBatchExperimentSummary;

describe("saved v5 batch repetition", () => {
  it("tags a saved request with null elapsed and time bounds as a repeat template", () => {
    const unbounded = { ...detail, request: { ...detail.request, conditions: { ...detail.request.conditions, max_elapsed_draws: null } },
      batch_admission: { ...detail.batch_admission, requested_constraints: { ...detail.batch_admission.requested_constraints, max_elapsed_draws: null } } };
    const prepared = prepareBatchRepeat(unbounded);
    expect(prepared.draft.conditions.max_elapsed_draws).toBe("");
    expect((prepared.draft as BatchDraft & { savedTimeBounds?: unknown }).savedTimeBounds).toEqual({
      start_draw: "2025-01-01 08:30", end_minute: null, duration_minutes: null,
    });
  });
  it("preserves saved end and duration bounds for the draft", () => {
    const absoluteEnd = Date.parse("2025-01-01T09:00:00Z") / 60_000;
    const withTimeBounds = { ...detail, request: { ...detail.request, conditions: { ...detail.request.conditions, end_minute: absoluteEnd, duration_minutes: 30 } } };
    expect((prepareBatchRepeat(withTimeBounds).draft as BatchDraft & { savedTimeBounds?: unknown }).savedTimeBounds).toEqual({
      start_draw: "2025-01-01 08:30", end_minute: absoluteEnd, duration_minutes: 30,
    });
  });
  it("copies requested constraints, never policy-clamped effective output, and preserves immutable refs", () => {
    const result = prepareBatchRepeat(detail);
    expect(result.draft).toMatchObject({
      datasetSha256: "b".repeat(64), profile: { id: "p", revision: 2, sha256: "a".repeat(64) },
      strategyRefs: [{ id: "s", revision: 3, definition_sha256: "c".repeat(64) }], pending: null,
      conditions: { start_draw: "2025-01-01 08:30", capital: "500", goal: "900", settlement: "best",
        max_elapsed_draws: "12", max_bet_draws: "8", max_draws: "10" },
    });
    expect(result.strategyTemplates[0]).toEqual(detail.request.strategies[0]);
  });
  it.each([
    ["non-v5", { ...detail, request_schema_version: 4 }],
    ["corrupt admission", { ...detail, batch_admission: { ...detail.batch_admission, strategy_refs: [] } }],
    ["wrong requested constraints", { ...detail, batch_admission: { ...detail.batch_admission, requested_constraints: { max_draws: 3 } } }],
  ])("fails closed for %s", (_label, saved) => {
    expect(() => prepareBatchRepeat(saved as ProfileBatchExperimentSummary)).toThrow();
  });
});
