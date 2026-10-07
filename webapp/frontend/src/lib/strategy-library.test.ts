import { expect, it } from "vitest";
import type { ConfigurationSummary, ProfileBatchStrategy } from "../api/types";
import { classicLibraryEntry, filterLibraryEntries, libraryEntryKey, matchesProfileRevision, profileLibraryEntry } from "./strategy-library";

const classic: ConfigurationSummary = { id: "shared-id", name: "Mismo nombre", strategy: { name: "Fríos", selector: "system", system: "cold", coverage: 1, staking: "flat" } };
const definition: ProfileBatchStrategy = {
  id: "shared-id", name: "Mismo nombre", revision: 1, latest_revision: 2, definition_version: 1,
  definition: { definition_version: 1, name: "Mismo nombre", selector: "static-numbers/v1", coverage: 1, staking: "flat-per-number/v1", selector_parameters: { numbers: [1] }, staking_parameters: { per_number_stake: 1 }, closing_defaults: {} },
  definition_sha256: "a".repeat(64), created_at: "2026-01-01", revision_created_at: "2026-01-01",
  protected: false, preset_explanation: null, definition_valid: true, profile_context_provided: false,
  profile_compatible: null, incompatibilities: [], requirements: {}, execution_available: false, execution_unavailable_reason: null,
};

it("separates native stores and immutable revisions even when names and IDs collide", () => {
  const entries = [classicLibraryEntry(classic), profileLibraryEntry(definition), profileLibraryEntry({ ...definition, revision: 2 })];
  expect(new Set(entries.map(libraryEntryKey)).size).toBe(3);
  expect(filterLibraryEntries(entries, "mismo")).toEqual(entries);
  expect(filterLibraryEntries(entries, "shared-id")).toEqual(entries);
  expect(entries[0].kind).toBe("classic");
  expect(entries[0].revision).toBeNull();
});

it("filters only supplied pages without deduplicating, sorting or altering native data", () => {
  const entries = [profileLibraryEntry({ ...definition, id: "z" }), profileLibraryEntry({ ...definition, id: "a" })];
  expect(filterLibraryEntries(entries, "mismo")).toEqual(entries);
  expect(filterLibraryEntries(entries, "missing")).toEqual([]);
  expect(entries.map((entry) => entry.nativeId)).toEqual(["z", "a"]);
});

it("requires exact native ID, revision and server digest for latest-detail reuse", () => {
  expect(matchesProfileRevision(definition, { ...definition })).toBe(true);
  expect(matchesProfileRevision(definition, { ...definition, id: "other" })).toBe(false);
  expect(matchesProfileRevision(definition, { ...definition, revision: 2 })).toBe(false);
  expect(matchesProfileRevision(definition, { ...definition, definition_sha256: "b".repeat(64) })).toBe(false);
});
