import { describe, expect, it } from "vitest";
import {
  BATCH_DRAFT_VERSION,
  buildBatchBody,
  createBatchDraft,
  parseBatchDraft,
  serializeBatchDraft,
  type BatchSubmissionBody,
  type ClosedStrategyDefinition,
} from "./batch-model";

const definition: ClosedStrategyDefinition = {
  definition_version: 1,
  name: "Mi selección",
  selector: "static-numbers/v1",
  coverage: 2,
  staking: "flat-per-number/v1",
  selector_parameters: { numbers: [3, 8] },
  staking_parameters: { per_number_stake: 2 },
  closing_defaults: { settlement: "all" },
};

const baseDraft = createBatchDraft("a".repeat(64));

describe("bounded profile batch draft and request", () => {
  it("# F-UTIL-009 persists only versioned identities and editable inputs, never library/history records", () => {
    const serialized = serializeBatchDraft({ ...baseDraft, strategyRefs: [{ id: "s-1", revision: 2, definition_sha256: "b".repeat(64) }] });
    expect(serialized).toContain(`"version":${BATCH_DRAFT_VERSION}`);
    expect(serialized).not.toMatch(/\"(?:history|records|token|file|historyRows)\"/i);
    expect(parseBatchDraft(serialized)).toMatchObject({ datasetSha256: "a".repeat(64), strategyRefs: [{ id: "s-1", revision: 2 }] });
  });

  it("# F-UTIL-010 rejects malformed or unknown-version drafts instead of upgrading frozen references", () => {
    expect(parseBatchDraft('{"version":99}')).toBeNull();
    expect(parseBatchDraft('{"version":1,"datasetSha256":"bad"}')).toBeNull();
    const withUnknownField = JSON.parse(serializeBatchDraft(baseDraft)) as Record<string, unknown>;
    withUnknownField.accessToken = "not allowed in a bounded draft";
    expect(parseBatchDraft(JSON.stringify(withUnknownField))).toBeNull();
  });

  it("# F-UTIL-011 persists a bounded selected draw identity with dataset binding and rejects mismatched restored metadata", () => {
    const startDraw = "2025-01-01 08:30";
    const draft = { ...baseDraft, selectedDraw: { datasetSha256: "a".repeat(64), index: 101, draw: startDraw },
      conditions: { ...baseDraft.conditions, start_draw: startDraw } };
    expect(parseBatchDraft(serializeBatchDraft(draft))?.selectedDraw).toEqual(draft.selectedDraw);
    const mismatched = JSON.parse(serializeBatchDraft(draft)) as Record<string, unknown>;
    mismatched.selectedDraw = { datasetSha256: "c".repeat(64), index: 101, draw: startDraw };
    expect(parseBatchDraft(JSON.stringify(mismatched))).toBeNull();
    delete mismatched.selectedDraw;
    expect(parseBatchDraft(JSON.stringify(mismatched))?.selectedDraw).toBeNull();
  });

  it("# F-UTIL-012 builds the exact closed batch body with ordered immutable references and explicit shared conditions", () => {
    const body: BatchSubmissionBody = {
      schema_version: 1,
      profile: { id: "local", revision: 4, sha256: "c".repeat(64) },
      dataset_sha256: "a".repeat(64),
      strategies: [{ id: "first", revision: 2, definition_sha256: "b".repeat(64) }],
      conditions: { schema_version: 1, start_draw: "2025-01-01 08:30", capital: 100, goal: 200,
        settlement: "all", max_elapsed_draws: 300, max_bet_draws: null, end_minute: null, duration_minutes: null },
      max_draws: 300,
      client_request_id: "request-1",
    };
    expect(body.strategies.map((reference: BatchSubmissionBody["strategies"][number]) => reference.id)).toEqual(["first"]);
    const built = buildBatchBody({ ...baseDraft, profile: body.profile, strategyRefs: body.strategies,
      conditions: { start_draw: body.conditions.start_draw, capital: "100", goal: "200", settlement: "all",
        max_elapsed_draws: "300", max_bet_draws: "", max_draws: "300" } }, 0, "request-1");
    expect(built).toEqual(body);
    expect(definition.closing_defaults.settlement).toBe("all");
  });
});
